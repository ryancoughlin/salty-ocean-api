const axios = require('axios');
const fs = require('fs').promises;
const path = require('path');
const cheerio = require('cheerio');
const { logger } = require('../utils/logger');

const NDBC_ACTIVE_STATIONS_URL = 'https://www.ndbc.noaa.gov/data/latest_obs/latest_obs.txt';
const OUTPUT_FILE = path.join(__dirname, '../data/ndbc-stations.geojson');

/**
 * Fetches and parses the list of active NDBC stations
 */
async function fetchActiveStations() {
  try {
    logger.info('Fetching active NDBC stations...');
    const response = await axios.get(NDBC_ACTIVE_STATIONS_URL);
    const lines = response.data.split('\n');

    // Skip header lines (first 2 lines)
    const stations = lines.slice(2)
      .map(line => {
        const parts = line.trim().split(/\s+/);
        if (parts.length < 6) return null;

        // Parse station data (format: STN  LAT     LON   YYYY MM DD hh mm TYPE)
        const [id, lat, lon, ...rest] = parts;
        
        // Only include stations with valid coordinates
        if (!isValidCoordinate(lat) || !isValidCoordinate(lon)) return null;

        // Only include standard NDBC stations (5-digit IDs starting with 4 or 3)
        if (!id.match(/^[34]\d{4}$/)) return null;

        return {
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: [parseFloat(lon), parseFloat(lat)]
          },
          properties: {
            id,
            name: null, // Will be populated later
            type: 'buoy',
            hasRealTimeData: true
          }
        };
      })
      .filter(station => station !== null);

    logger.info(`Found ${stations.length} NDBC stations`);
    return stations;
  } catch (error) {
    logger.error('Error fetching active stations:', error);
    throw error;
  }
}

/**
 * Validates a coordinate value
 */
function isValidCoordinate(value) {
  const num = parseFloat(value);
  return !isNaN(num) && Math.abs(num) <= 180;
}

/**
 * Extracts clean station name from the full title
 * @param {string} fullTitle - The full station title
 * @param {string} stationId - The station ID
 * @returns {string} - Clean station name
 */
function extractStationName(fullTitle, stationId) {
  // Remove the station ID and any RSS image text
  let name = fullTitle.replace(/<img.*?>/g, '').trim();
  
  // Handle case with two dashes (e.g., "Station NTKM3 - 8449130 - Nantucket Island, MA")
  if (name.split('-').length > 2) {
    name = name.split('-').slice(2).join('-').trim();
  } else {
    // Handle single dash case (e.g., "Station 44073 - CO2 Gulf of Maine Buoy")
    name = name.split('-').slice(1).join('-').trim();
  }

  // Remove "Station {ID}" prefix if still present
  name = name.replace(new RegExp(`^Station ${stationId}\\s*`), '').trim();
  
  // Clean up common prefixes we don't want
  const unwantedPrefixes = ['CO2', 'NDBC', 'TABS'];
  for (const prefix of unwantedPrefixes) {
    if (name.startsWith(prefix)) {
      name = name.substring(prefix.length).trim();
    }
  }

  // Remove any leading/trailing dashes and whitespace
  name = name.replace(/^[-\s]+|[-\s]+$/g, '').trim();

  return name || stationId;
}

/**
 * Fetches station metadata from NDBC
 */
async function getStationMetadata(stationId) {
  try {
    const response = await axios.get(`https://www.ndbc.noaa.gov/station_page.php?station=${stationId}`);
    const $ = cheerio.load(response.data);
    
    // Look for the station name in the h1 tag
    let name = null;
    const h1Text = $('h1').first().text().trim();
    
    if (h1Text) {
      name = extractStationName(h1Text, stationId);
    }

    // If no name found in h1, try the title tag as fallback
    if (!name || name === stationId) {
      const titleText = $('title').text().trim();
      if (titleText) {
        name = extractStationName(titleText, stationId);
      }
    }

    return {
      name: name || stationId,
      owner: 'NDBC',
      type: 'buoy'
    };
  } catch (error) {
    logger.warn(`Could not fetch metadata for station ${stationId}:`, error.message);
    return {
      name: stationId,
      owner: 'NDBC',
      type: 'buoy'
    };
  }
}

/**
 * Verifies that a station has the required data fields and recent data
 */
async function verifyStationData(stationId) {
  try {
    const response = await axios.get(`https://www.ndbc.noaa.gov/data/realtime2/${stationId}.txt`);
    const lines = response.data.split('\n');
    
    // Check headers for required fields
    const headers = lines[0].toLowerCase().split(/\s+/);
    const requiredFields = ['wvht', 'dpd', 'mwd', 'wspd', 'wdir'];
    
    const hasRequiredFields = requiredFields.every(field => headers.includes(field));
    
    // Check if we have recent data (within last 24 hours)
    if (lines.length > 2) {
      const dataLine = lines[2].split(/\s+/);
      if (dataLine.length >= 5) {
        const [year, month, day, hour] = dataLine.slice(0, 4).map(Number);
        const dataTime = new Date(Date.UTC(year, month - 1, day, hour));
        const now = new Date();
        const hoursSinceUpdate = (now - dataTime) / (1000 * 60 * 60);
        
        return hasRequiredFields && hoursSinceUpdate <= 24;
      }
    }
    
    return false;
  } catch (error) {
    logger.warn(`Could not verify data for station ${stationId}:`, error.message);
    return false;
  }
}

/**
 * Main function to export station data
 */
async function exportStations() {
  try {
    // Fetch all active stations
    const stations = await fetchActiveStations();
    
    // Verify each station has the required data
    logger.info('Verifying station data...');
    const verifiedStations = [];
    
    for (const station of stations) {
      const hasRequiredData = await verifyStationData(station.properties.id);
      if (hasRequiredData) {
        // Fetch station metadata
        const metadata = await getStationMetadata(station.properties.id);
        station.properties.name = metadata.name;
        station.properties.owner = metadata.owner;
        station.properties.type = metadata.type;
        
        verifiedStations.push(station);
        logger.info(`Verified station ${station.properties.id} - ${station.properties.name}`);
      }
    }

    // Sort stations by ID
    verifiedStations.sort((a, b) => a.properties.id.localeCompare(b.properties.id));

    // Create GeoJSON FeatureCollection
    const geojson = {
      type: 'FeatureCollection',
      features: verifiedStations
    };

    // Create data directory if it doesn't exist
    await fs.mkdir(path.dirname(OUTPUT_FILE), { recursive: true });

    // Write to file
    await fs.writeFile(
      OUTPUT_FILE,
      JSON.stringify(geojson, null, 2)
    );

    logger.info(`Successfully exported ${verifiedStations.length} NDBC stations to ${OUTPUT_FILE}`);
    return verifiedStations;
  } catch (error) {
    logger.error('Error exporting stations:', error);
    throw error;
  }
}

// Run if called directly
if (require.main === module) {
  exportStations()
    .then(() => process.exit(0))
    .catch(error => {
      logger.error('Script failed:', error);
      process.exit(1);
    });
}

module.exports = {
  exportStations,
  fetchActiveStations,
  verifyStationData
}; 