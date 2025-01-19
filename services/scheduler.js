const { logger } = require("../utils/logger");
const { prefetchAllBuoyData } = require("./buoyPrefetchService");
const ndbcService = require("./ndbcService");
const { getModelRunCacheDuration } = require("../utils/cacheManager");
const CONFIG = require("../config/waveModelConfig");

let prefetchTimer = null;

/**
 * Calculate next model run time
 */
const getNextModelRun = () => {
  const now = new Date();
  const currentHour = now.getUTCHours();
  const currentMinute = now.getUTCMinutes();

  // Find next model run hour (00, 06, 12, 18)
  const nextRun = CONFIG.modelRuns.hours
    .map((hour) => ({
      hour: parseInt(hour),
      availableAt: parseInt(hour) + CONFIG.modelRuns.availableAfter[hour],
    }))
    .find((run) => {
      const adjustedHour = currentHour + currentMinute / 60;
      return adjustedHour < run.availableAt;
    }) || {
    hour: parseInt(CONFIG.modelRuns.hours[0]),
    availableAt:
      24 + parseInt(CONFIG.modelRuns.availableAfter[CONFIG.modelRuns.hours[0]]),
  };

  return nextRun;
};

/**
 * Schedule next prefetch based on model run times
 */
const scheduleNextPrefetch = () => {
  // Clear any existing timer
  if (prefetchTimer) {
    clearTimeout(prefetchTimer);
  }

  const nextRun = getNextModelRun();
  const now = new Date();
  const currentHour = now.getUTCHours();
  const currentMinute = now.getUTCMinutes();

  // Calculate milliseconds until next run
  let msUntilNextRun;
  if (nextRun.availableAt > currentHour) {
    msUntilNextRun =
      ((nextRun.availableAt - currentHour) * 3600 - currentMinute * 60) * 1000;
  } else {
    // Next run is tomorrow
    msUntilNextRun =
      ((24 - currentHour + nextRun.availableAt) * 3600 - currentMinute * 60) *
      1000;
  }

  // Add 5 minutes buffer to ensure model data is available
  msUntilNextRun += 5 * 60 * 1000;

  logger.info(
    `Next prefetch scheduled for ${new Date(
      Date.now() + msUntilNextRun
    ).toISOString()}`
  );
  logger.info(
    `Time until next prefetch: ${(msUntilNextRun / 1000 / 60).toFixed(
      1
    )} minutes`
  );

  // Schedule next prefetch
  prefetchTimer = setTimeout(async () => {
    try {
      logger.info("Starting scheduled prefetch...");
      await prefetchAllBuoyData(ndbcService);
      scheduleNextPrefetch(); // Schedule next run
    } catch (error) {
      logger.error("Error during scheduled prefetch:", error);
      // Retry in 5 minutes if there's an error
      setTimeout(() => scheduleNextPrefetch(), 5 * 60 * 1000);
    }
  }, msUntilNextRun);

  // Keep track of timer in case we need to clean up
  return prefetchTimer;
};

/**
 * Start the prefetch scheduler
 */
const startScheduler = () => {
  logger.info("Starting prefetch scheduler...");
  return scheduleNextPrefetch();
};

/**
 * Stop the prefetch scheduler
 */
const stopScheduler = () => {
  if (prefetchTimer) {
    clearTimeout(prefetchTimer);
    prefetchTimer = null;
    logger.info("Prefetch scheduler stopped");
  }
};

// Handle process termination
process.on("SIGTERM", () => {
  logger.info("SIGTERM received, stopping scheduler...");
  stopScheduler();
});

process.on("SIGINT", () => {
  logger.info("SIGINT received, stopping scheduler...");
  stopScheduler();
});

module.exports = {
  startScheduler,
  stopScheduler,
  scheduleNextPrefetch,
};
