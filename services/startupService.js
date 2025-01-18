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
    logger.info("🚀 Starting data initialization...");

    // 1. Load station data first (fast)
    await ndbcService.loadStations();
    logger.info("✅ Station data loaded");

    // 2. Start prefetch process and wait for it to complete
    logger.info("🌊 Starting data prefetch for all buoys...");
    const result = await prefetchAllBuoyData(ndbcService);

    logger.info("✅ Initial prefetch completed:", {
      totalStations: result.totalStations,
      successful: result.successCount,
      failed: result.failureCount,
      duration: ((result.endTime - result.startTime) / 1000).toFixed(1) + "s",
    });

    // 3. Schedule next prefetch based on wave model run times
    scheduleNextPrefetch();

    return {
      status: "ready",
      prefetchStats: {
        totalStations: result.totalStations,
        successful: result.successCount,
        failed: result.failureCount,
      },
    };
  } catch (error) {
    logger.error("❌ Error during initialization:", error);
    // Don't throw - we want the app to start even if initialization fails
    return {
      status: "degraded",
      error: error.message,
      prefetchStats: {
        totalStations: 0,
        successful: 0,
        failed: 0,
      },
    };
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
