const { logger } = require("../utils/logger");
const ndbcService = require("./ndbcService");
const { prefetchAllBuoyData } = require("./buoyPrefetchService");
const { getModelRunCacheDuration } = require("../utils/cacheManager");
const CONFIG = require("../config/waveModelConfig");

/**
 * Initialize data on app startup
 */
async function initializeData() {
  try {
    logger.info("🚀 Starting initial data prefetch...");

    // Wait for NDBC service to load stations
    await ndbcService.loadStations();

    // Start prefetch process
    const result = await prefetchAllBuoyData(ndbcService);

    logger.info("✅ Initial prefetch completed:", {
      totalStations: result.totalStations,
      successful: result.successCount,
      failed: result.failureCount,
      duration: ((result.endTime - result.startTime) / 1000).toFixed(1) + "s",
    });

    // Schedule next prefetch based on wave model run times
    scheduleNextPrefetch();

    return result;
  } catch (error) {
    logger.error("❌ Error during initial data prefetch:", error);
    // Don't throw - we want the app to start even if prefetch fails
    return null;
  }
}

/**
 * Schedule next prefetch based on wave model run times
 */
function scheduleNextPrefetch() {
  const ttl = getModelRunCacheDuration();
  const nextRunMs = ttl * 1000;

  logger.info(
    `Scheduling next prefetch in ${(nextRunMs / 1000 / 60).toFixed(1)} minutes`
  );

  setTimeout(async () => {
    try {
      logger.info("Starting scheduled prefetch...");
      await prefetchAllBuoyData(ndbcService);
      scheduleNextPrefetch(); // Schedule next run
    } catch (error) {
      logger.error("Error during scheduled prefetch:", error);
      scheduleNextPrefetch(); // Retry on next model run
    }
  }, nextRunMs);
}

module.exports = {
  initializeData,
};
