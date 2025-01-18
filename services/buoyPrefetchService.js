const { logger } = require("../utils/logger");
const { getOrSet } = require("../utils/cache");
const waveModelService = require("../services/waveModelService");
const { getCacheConfig } = require("../utils/cacheManager");
const CONFIG = require("../config/waveModelConfig");

// Constants for batch processing
const BATCH_SIZE = 5;
const BATCH_DELAY = 1000;

let currentStatus = null;

const isStationInModelBounds = (station) => {
  const coordinates = station.location?.coordinates;
  if (!coordinates) {
    logger.debug(`No coordinates found for station: ${station.id}`);
    return false;
  }
  const [longitude, latitude] = coordinates;

  // Normalize longitude to 0-360 range for comparison
  const normalizedLon = longitude < 0 ? longitude + 360 : longitude;

  // Check if station is within any model's grid
  return Object.entries(CONFIG.models).some(([modelId, model]) => {
    const inLatRange =
      latitude >= model.grid.lat.start && latitude <= model.grid.lat.end;
    const inLonRange =
      normalizedLon >= model.grid.lon.start &&
      normalizedLon <= model.grid.lon.end;

    if (inLatRange && inLonRange) {
      return true;
    }
    return false;
  });
};

const updateStatus = (updates) => {
  if (!currentStatus) return;
  currentStatus = {
    ...currentStatus,
    ...updates,
    lastUpdated: Date.now(),
  };

  const progress = (
    (currentStatus.processedCount / currentStatus.totalStations) *
    100
  ).toFixed(1);
  logger.info(
    `Prefetch progress: ${progress}% (${currentStatus.processedCount}/${currentStatus.totalStations})`
  );
  logger.info(
    `Success: ${currentStatus.successCount}, Failed: ${currentStatus.failureCount}`
  );
};

const processBatch = async (stations, ndbcService) => {
  const results = await Promise.all(
    stations.map(async (station) => {
      try {
        const buoyConfig = getCacheConfig("buoyData", station.id);
        const buoyData = await getOrSet(
          buoyConfig.key,
          () => ndbcService.fetchBuoyData(station.id),
          buoyConfig.ttl
        );

        // Prefetch wave model forecast if station has coordinates and is within model bounds
        if (buoyData && station.location?.coordinates) {
          const [longitude, latitude] = station.location.coordinates;

          if (isStationInModelBounds(station)) {
            try {
              const forecastConfig = getCacheConfig(
                "waveModel",
                `${latitude}_${longitude}`
              );
              await getOrSet(
                forecastConfig.key,
                () => waveModelService.getPointForecast(latitude, longitude),
                forecastConfig.ttl
              );
              logger.debug(
                `✓ Wave forecast prefetched for station ${station.id}`
              );
            } catch (forecastError) {
              logger.warn(
                `Failed to prefetch wave forecast for station ${station.id}:`,
                forecastError
              );
            }
          }
        }

        if (currentStatus) {
          currentStatus.successCount++;
          currentStatus.processedCount++;
          updateStatus({});
        }

        logger.debug(`✓ Station ${station.id} prefetched successfully`);
        return { station: station.id, success: true };
      } catch (error) {
        if (currentStatus) {
          currentStatus.failureCount++;
          currentStatus.processedCount++;
          currentStatus.errors.push({
            station: station.id,
            error: error.message || "Unknown error",
          });
          updateStatus({});
        }

        logger.error(`✗ Station ${station.id} prefetch failed:`, error);
        return {
          station: station.id,
          success: false,
          error: error.message || "Unknown error",
        };
      }
    })
  );

  return results;
};

const getPrefetchStatus = () => currentStatus;

const prefetchAllBuoyData = async (ndbcService) => {
  try {
    logger.info("🚀 Starting buoy data prefetch");
    const startTime = Date.now();

    // Filter stations that are within any model's bounds
    const stationsInBounds = ndbcService.stations.filter(
      isStationInModelBounds
    );

    currentStatus = {
      status: "running",
      startTime,
      totalStations: stationsInBounds.length,
      processedCount: 0,
      successCount: 0,
      failureCount: 0,
      lastUpdated: startTime,
      errors: [],
    };

    for (let i = 0; i < stationsInBounds.length; i += BATCH_SIZE) {
      const batch = stationsInBounds.slice(i, i + BATCH_SIZE);
      logger.info(
        `⏳ Processing batch ${Math.floor(i / BATCH_SIZE) + 1}/${Math.ceil(
          stationsInBounds.length / BATCH_SIZE
        )}`
      );
      await processBatch(batch, ndbcService);

      if (i + BATCH_SIZE < stationsInBounds.length) {
        await new Promise((resolve) => setTimeout(resolve, BATCH_DELAY));
      }
    }

    const endTime = Date.now();
    const duration = (endTime - startTime) / 1000;

    currentStatus = {
      ...currentStatus,
      status: "completed",
      endTime,
    };

    logger.info("✅ Prefetch completed:");
    logger.info(`📊 Summary:
        - Duration: ${duration.toFixed(1)}s
        - Total Stations: ${currentStatus.totalStations}
        - Successful: ${currentStatus.successCount}
        - Failed: ${currentStatus.failureCount}
        - Success Rate: ${(
          (currentStatus.successCount / currentStatus.totalStations) *
          100
        ).toFixed(1)}%`);

    if (currentStatus.errors.length > 0) {
      logger.warn("⚠️ Failed stations:", currentStatus.errors);
    }

    return currentStatus;
  } catch (error) {
    const errorStatus = {
      status: "failed",
      startTime: Date.now(),
      endTime: Date.now(),
      totalStations: 0,
      processedCount: 0,
      successCount: 0,
      failureCount: 0,
      lastUpdated: Date.now(),
      errors: [{ station: "system", error: error.message || "Unknown error" }],
    };
    currentStatus = errorStatus;
    logger.error("❌ Error during prefetch:", error);
    throw error;
  }
};

module.exports = {
  prefetchAllBuoyData,
  getPrefetchStatus,
};
