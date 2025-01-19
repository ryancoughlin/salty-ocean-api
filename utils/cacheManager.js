const CONFIG = require("../config/waveModelConfig");

// NDBC updates every 30 minutes at :26 and :56 past the hour
const NDBC_UPDATE_MINUTES = [26, 56];

const BUFFER_TIME = 5 * 60; // 5 minutes in seconds
const MODEL_DELAY = 5 * 60; // 5 minutes delay after model run

/**
 * Calculate TTL until next NDBC update
 */
const getNDBCCacheDuration = () => {
  const now = new Date();
  const currentMinute = now.getMinutes();
  const nextUpdate =
    NDBC_UPDATE_MINUTES.find((min) => min > currentMinute) ||
    NDBC_UPDATE_MINUTES[0];

  const minutesUntilUpdate =
    nextUpdate > currentMinute
      ? nextUpdate - currentMinute
      : 60 - currentMinute + nextUpdate;

  return minutesUntilUpdate * 60 + 60; // Add 60s buffer
};

/**
 * Calculates cache duration based on NOAA wave model run times
 */
function getModelRunCacheDuration() {
  const now = new Date();
  const currentHour = now.getUTCHours();
  const currentMinute = now.getUTCMinutes();

  // Find next model run hour (00, 06, 12, 18)
  const modelRuns = CONFIG.modelRuns.hours.map((h) => parseInt(h));
  const nextRun = modelRuns.find((hour) => hour > currentHour) || modelRuns[0];

  // Calculate hours until next run + availability delay
  let hoursUntilNextRun =
    nextRun > currentHour ? nextRun - currentHour : 24 - currentHour + nextRun;
  hoursUntilNextRun +=
    CONFIG.modelRuns.availableAfter[nextRun.toString().padStart(2, "0")];

  // Convert to seconds and subtract elapsed minutes
  return Math.min(
    (hoursUntilNextRun * 60 - currentMinute) * 60,
    CONFIG.cache.hours * 3600
  );
}

// Cache types and their TTL calculators
const CACHE_TYPES = {
  waveModel: {
    keyPrefix: "wave_model",
    getTTL: getModelRunCacheDuration,
  },
  buoyData: {
    keyPrefix: "ndbc_buoy",
    getTTL: getNDBCCacheDuration,
  },
};

/**
 * Get time until next NDBC update, accounting for buffer time
 */
const getTimeToNextNDBCUpdate = () => {
  const now = new Date();
  const currentMinute = now.getMinutes();
  const currentSecond = now.getSeconds();

  // Find next update minute
  const nextUpdateMinute =
    NDBC_UPDATE_MINUTES.find(
      (min) =>
        // Add buffer to avoid fetching too close to update
        currentMinute < min - BUFFER_TIME / 60
    ) || NDBC_UPDATE_MINUTES[0];

  // Calculate seconds until next update
  let secondsToNextUpdate;
  if (nextUpdateMinute > currentMinute) {
    secondsToNextUpdate =
      (nextUpdateMinute - currentMinute) * 60 - currentSecond;
  } else {
    // Next update is in the next hour
    secondsToNextUpdate =
      (60 - currentMinute + nextUpdateMinute) * 60 - currentSecond;
  }

  return secondsToNextUpdate;
};

/**
 * Get time until next wave model run is available
 */
const getTimeToNextModelRun = () => {
  const now = new Date();
  const currentHour = now.getUTCHours();
  const currentMinute = now.getUTCMinutes();
  const currentSecond = now.getUTCSeconds();

  // Find next model run hour
  const nextRun = CONFIG.modelRuns.hours
    .map((hour) => ({
      hour: parseInt(hour),
      availableAt: parseInt(hour) + CONFIG.modelRuns.availableAfter[hour],
    }))
    .find((run) => {
      const adjustedHour = currentHour + currentMinute / 60;
      // Add buffer to avoid fetching too close to next run
      return adjustedHour < run.availableAt - BUFFER_TIME / 3600;
    }) || {
    hour: parseInt(CONFIG.modelRuns.hours[0]),
    availableAt:
      24 + parseInt(CONFIG.modelRuns.availableAfter[CONFIG.modelRuns.hours[0]]),
  };

  // Calculate seconds until next run is available
  let secondsToNextRun;
  if (nextRun.availableAt > currentHour) {
    secondsToNextRun =
      (nextRun.availableAt - currentHour) * 3600 -
      currentMinute * 60 -
      currentSecond;
  } else {
    // Next run is tomorrow
    secondsToNextRun =
      (24 - currentHour + nextRun.availableAt) * 3600 -
      currentMinute * 60 -
      currentSecond;
  }

  return secondsToNextRun;
};

/**
 * Get cache TTL and key for a data type
 */
const getCacheConfig = (type, identifier) => {
  const cacheType = CACHE_TYPES[type];
  if (!cacheType) {
    return {
      key: identifier,
      ttl: CONFIG.cache.hours * 3600,
    };
  }

  let ttl;
  switch (type) {
    case "buoyData":
      ttl = getTimeToNextNDBCUpdate();
      break;
    case "waveModel":
      ttl = getTimeToNextModelRun();
      break;
    default:
      ttl = CONFIG.cache.hours * 3600;
  }

  return {
    key: `${cacheType.keyPrefix}_${identifier}`,
    ttl,
    nextUpdate: new Date(Date.now() + ttl * 1000).toISOString(),
  };
};

module.exports = {
  getCacheConfig,
  getModelRunCacheDuration,
  getNDBCCacheDuration,
};
