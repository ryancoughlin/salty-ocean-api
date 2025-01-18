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

    // Only wait for stations to load, don't block on prefetch
    await ndbcService.loadStations();
    logger.info("✅ Station data loaded, starting background prefetch");

    // Start prefetch process in background
    prefetchAllBuoyData(ndbcService)
      .then((result) => {
        logger.info("✅ Initial prefetch completed:", {
          totalStations: result.totalStations,
          successful: result.successCount,
          failed: result.failureCount,
          duration:
            ((result.endTime - result.startTime) / 1000).toFixed(1) + "s",
        });
        // Schedule next prefetch based on wave model run times
        scheduleNextPrefetch();
      })
      .catch((error) => {
        logger.error("❌ Error during initial prefetch:", error);
        // Retry prefetch on next model run
        scheduleNextPrefetch();
      });

    return { status: "initialized" };
  } catch (error) {
    logger.error("❌ Error during initialization:", error);
    // Don't throw - we want the app to start even if initialization fails
    return { status: "failed", error: error.message };
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
