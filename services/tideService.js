const axios = require("axios");
const { logger } = require("../utils/logger");
const { formatTimestamp } = require("../utils/formatters");
const tideStations = require("../data/tide-stations.json");
const NodeCache = require("node-cache");
const rateLimit = require("axios-rate-limit");

const NOAA_COOPS_API =
  "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter";

// Cache configuration
const CACHE_TTL = 60 * 60; // 1 hour base cache
const MAX_CACHE_SIZE = 1000; // Maximum number of items in cache
const predictionCache = new NodeCache({
  stdTTL: CACHE_TTL,
  checkperiod: 120,
  useClones: false,
  maxKeys: MAX_CACHE_SIZE,
});

// Rate limited axios instance
const http = rateLimit(axios.create(), {
  maxRequests: 10,
  perMilliseconds: 1000,
  maxRPS: 10,
});

// Constants
const KM_PER_DEG_LAT = 111;
const KM_PER_DEG_LON = 78;
const MAX_PREDICTION_DAYS = 30;
const SEARCH_RADIUS_KM = 500;

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

  // Validate coordinates
  if (!isValidCoordinate(lat, lon)) {
    throw new Error("Invalid coordinates");
  }

  // First pass: Find stations within rough bounding box
  const latRange = SEARCH_RADIUS_KM / KM_PER_DEG_LAT;
  const lonRange = SEARCH_RADIUS_KM / (KM_PER_DEG_LON * Math.cos(toRad(lat)));

  const candidates = tideStations.filter((station) => {
    const [sLon, sLat] = station.location.coordinates;
    return Math.abs(lat - sLat) <= latRange && Math.abs(lon - sLon) <= lonRange;
  });

  // Second pass: Calculate exact distances only for candidates
  const stationsToCheck = candidates.length ? candidates : tideStations;
  return findNearestStation(stationsToCheck, lat, lon);
}

/**
 * Find the nearest station from a list
 */
function findNearestStation(stations, lat, lon) {
  return stations.reduce((closest, station) => {
    const [sLon, sLat] = station.location.coordinates;
    const distance = calculateDistance(lat, lon, sLat, sLon);

    if (!closest || distance < closest.distance) {
      return { ...station, distance };
    }
    return closest;
  }, null);
}

/**
 * Validate geographic coordinates
 */
function isValidCoordinate(lat, lon) {
  return lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
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
  // Validate dates
  const validatedDates = validateDateRange(startDate, endDate);
  if (!validatedDates.isValid) {
    throw new Error(validatedDates.error);
  }

  const { start, end } = validatedDates;
  const cacheKey = `${stationId}-${start.toISOString()}-${end.toISOString()}`;

  // Try cache first
  const cachedData = predictionCache.get(cacheKey);
  if (cachedData) {
    logger.debug(`Cache hit for tide predictions: ${cacheKey}`);
    return cachedData;
  }

  // Calculate dynamic TTL based on prediction window
  const dynamicTTL = calculateCacheTTL(start);

  try {
    const params = {
      station: stationId,
      begin_date: formatDate(start),
      end_date: formatDate(end),
      product: "predictions",
      datum: "MLLW",
      units: "english",
      time_zone: "gmt",
      format: "json",
      interval: "hilo",
    };

    // Implement retry logic with rate limiting
    const response = await retryWithBackoff(() =>
      http.get(NOAA_COOPS_API, {
        params,
        timeout: 5000,
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

    // Only cache if we have predictions
    if (predictions.length > 0) {
      predictionCache.set(cacheKey, result, dynamicTTL);
    }

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
 * Validate and normalize date range
 */
function validateDateRange(startDate, endDate) {
  try {
    const start = new Date(startDate);
    const end = new Date(endDate);
    const now = new Date();

    // Check for valid dates
    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
      return { isValid: false, error: "Invalid date format" };
    }

    // Check date range
    const daysDiff = (end - start) / (1000 * 60 * 60 * 24);
    if (daysDiff > MAX_PREDICTION_DAYS) {
      return {
        isValid: false,
        error: `Date range cannot exceed ${MAX_PREDICTION_DAYS} days`,
      };
    }

    // Check if dates are in the past
    if (start < now) {
      return { isValid: false, error: "Start date cannot be in the past" };
    }

    if (end <= start) {
      return { isValid: false, error: "End date must be after start date" };
    }

    return { isValid: true, start, end };
  } catch (error) {
    return { isValid: false, error: "Invalid date format" };
  }
}

/**
 * Calculate cache TTL based on prediction window
 */
function calculateCacheTTL(predictionStart) {
  const now = new Date();
  const hoursInFuture = (predictionStart - now) / (1000 * 60 * 60);

  // Scale cache duration based on how far in future the prediction is
  if (hoursInFuture > 72) {
    return CACHE_TTL * 4; // Cache for 4 hours if > 3 days in future
  } else if (hoursInFuture > 24) {
    return CACHE_TTL * 2; // Cache for 2 hours if > 1 day in future
  }
  return CACHE_TTL; // Default 1 hour cache
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

      // Check if we should retry based on error type
      if (!isRetryableError(error)) throw error;

      const delay = Math.min(1000 * Math.pow(2, i), 5000);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }
}

/**
 * Determine if an error should trigger a retry
 */
function isRetryableError(error) {
  if (!error.response) return true; // Network errors should retry
  const { status } = error.response;
  return status >= 500 || status === 429; // Retry on server errors and rate limits
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
