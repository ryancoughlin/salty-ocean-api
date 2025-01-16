const axios = require("axios");
const { logger } = require("../utils/logger");
const { formatTimestamp } = require("../utils/formatters");
const tideStations = require("../data/tide-stations.json");
const NodeCache = require("node-cache");

const NOAA_COOPS_API =
  "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter";
const CACHE_TTL = 60 * 60; // 1 hour cache
const predictionCache = new NodeCache({
  stdTTL: CACHE_TTL,
  checkperiod: 120,
  useClones: false,
});

// Rough distance in km per degree at 45° latitude
const KM_PER_DEG_LAT = 111;
const KM_PER_DEG_LON = 78;

/**
 * Get all tide stations
 */
function getAllStations() {
  return tideStations;
}

/**
 * Find closest tide station to coordinates using efficient filtering
 */
function findClosestStation(lat, lon) {
  if (!tideStations.length) {
    return null;
  }

  // First pass: Find stations within rough bounding box (much faster than Haversine)
  const searchRadiusKm = 500; // Adjust based on your needs
  const latRange = searchRadiusKm / KM_PER_DEG_LAT;
  const lonRange = searchRadiusKm / (KM_PER_DEG_LON * Math.cos(toRad(lat)));

  const candidates = tideStations.filter((station) => {
    const [sLon, sLat] = station.location.coordinates;
    return Math.abs(lat - sLat) <= latRange && Math.abs(lon - sLon) <= lonRange;
  });

  // If no stations in range, fall back to all stations
  const stationsToCheck = candidates.length ? candidates : tideStations;

  // Second pass: Calculate exact distances only for candidates
  return stationsToCheck.reduce((closest, station) => {
    const [sLon, sLat] = station.location.coordinates;
    const distance = calculateDistance(lat, lon, sLat, sLon);

    if (!closest || distance < closest.distance) {
      return { ...station, distance };
    }
    return closest;
  }, null);
}

/**
 * Calculate distance between two points using Haversine formula
 */
function calculateDistance(lat1, lon1, lat2, lon2) {
  const R = 6371; // Earth's radius in km
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) *
      Math.cos(toRad(lat2)) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function toRad(deg) {
  return deg * (Math.PI / 180);
}

/**
 * Get tide predictions with improved caching and error handling
 */
async function getTidePredictions(stationId, startDate, endDate) {
  const cacheKey = `${stationId}-${startDate}-${endDate}`;

  // Try cache first
  const cachedData = predictionCache.get(cacheKey);
  if (cachedData) {
    logger.debug(`Cache hit for tide predictions: ${cacheKey}`);
    return cachedData;
  }

  // Calculate dynamic TTL based on prediction window
  const predictionStart = new Date(startDate);
  const now = new Date();
  const hoursInFuture = (predictionStart - now) / (1000 * 60 * 60);

  // Shorter cache for immediate predictions, longer for future
  const dynamicTTL = Math.max(
    CACHE_TTL,
    hoursInFuture > 24 ? CACHE_TTL * 2 : CACHE_TTL
  );

  try {
    const params = {
      station: stationId,
      begin_date: formatDate(new Date(startDate)),
      end_date: formatDate(new Date(endDate)),
      product: "predictions",
      datum: "MLLW",
      units: "english",
      time_zone: "gmt",
      format: "json",
      interval: "hilo",
    };

    // Implement retry logic
    const response = await retryWithBackoff(() =>
      axios.get(NOAA_COOPS_API, {
        params,
        timeout: 5000, // 5 second timeout
      })
    );

    if (!response.data?.predictions) {
      logger.warn(`No tide predictions available for station ${stationId}`);
      return [];
    }

    const predictions = response.data.predictions.map((prediction) => ({
      time: formatTimestamp(prediction.t),
      height: Number(prediction.v),
      type: prediction.type,
    }));

    const station = tideStations.find((s) => s.id === stationId);
    const result = {
      predictions,
      metadata: {
        station: station?.name || "Unknown",
        state: station?.state || "Unknown",
      },
    };

    predictionCache.set(cacheKey, result, dynamicTTL);
    return result;
  } catch (error) {
    logger.error(
      `Error fetching tide predictions for station ${stationId}:`,
      error
    );
    throw error;
  }
}

/**
 * Retry failed requests with exponential backoff
 */
async function retryWithBackoff(fn, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      if (i === maxRetries - 1) throw error;
      const delay = Math.min(1000 * Math.pow(2, i), 5000);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }
}

/**
 * Format date for NOAA API (YYYYMMDD)
 */
function formatDate(date) {
  return date.toISOString().split("T")[0].replace(/-/g, "");
}

module.exports = {
  getAllStations,
  findClosestStation,
  getTidePredictions,
};
