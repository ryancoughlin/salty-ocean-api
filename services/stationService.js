// services/stationService.js
const { logger } = require('../utils/logger');
const fs = require('fs').promises;
const path = require('path');

let stations = null;

const loadStations = async () => {
  if (stations === null) {
    const stationsPath = path.join(__dirname, '../data/ndbc-stations.geojson');
    const data = await fs.readFile(stationsPath, 'utf8');
    const geojson = JSON.parse(data);
    stations = geojson.features.map(feature => ({
      stationId: feature.properties.id,
      name: feature.properties.name,
      location: feature.geometry,
      type: feature.properties.type,
      hasRealTimeData: feature.properties.hasRealTimeData
    }));
  }
  return stations;
};

const calculateDistance = (lat1, lon1, lat2, lon2) => {
  const R = 6371; // Earth's radius in km
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
           Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
           Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
};

const fetchClosestStation = async (lat, lon) => {
  try {
    logger.info(`Fetching closest station for lat: ${lat}, lon: ${lon}`);
    const allStations = await loadStations();
    
    let closest = null;
    let minDistance = Infinity;
    
    for (const station of allStations) {
      const [stationLon, stationLat] = station.location.coordinates;
      const distance = calculateDistance(lat, lon, stationLat, stationLon);
      
      if (distance < minDistance) {
        minDistance = distance;
        closest = { ...station, distance };
      }
    }
    
    if (!closest || closest.distance > 100) { // 100km max distance
      logger.warn('No station found within 100km of the specified location');
      return null;
    }

    logger.info(`Found station: ${closest.name} at distance: ${closest.distance.toFixed(2)}km`);
    return closest;
  } catch (error) {
    logger.error('Error in fetchClosestStation:', error);
    throw error;
  }
};

const fetchAllStations = async () => {
  try {
    logger.info('Fetching all stations');
    const allStations = await loadStations();
    logger.info(`Found ${allStations.length} stations`);
    return allStations;
  } catch (error) {
    logger.error('Error in fetchAllStations:', error);
    throw error;
  }
};

const fetchStationById = async (stationId) => {
  try {
    logger.info(`Fetching station by ID: ${stationId}`);
    const allStations = await loadStations();
    const station = allStations.find(s => s.stationId === stationId);
    
    if (!station) {
      logger.warn(`No station found with ID: ${stationId}`);
      return null;
    }

    logger.info(`Found station: ${station.name}`);
    return station;
  } catch (error) {
    logger.error('Error in fetchStationById:', error);
    throw error;
  }
};

module.exports = {
  fetchClosestStation,
  fetchAllStations,
  fetchStationById,
};
