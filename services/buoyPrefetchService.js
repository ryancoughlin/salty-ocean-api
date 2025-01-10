const { logger } = require('../utils/logger');
const { getOrSet } = require('../utils/cache');
const waveModelService = require('../services/waveModelService');
const { getCacheConfig } = require('../utils/cacheManager');

const EAST_COAST_BOUNDS = {
  north: 45.0,  // Maine
  south: 25.0,  // Southern Florida
  west: -82.0,  // Inland boundary
  east: -65.0   // Atlantic boundary
};

const BATCH_SIZE = 5; // Number of concurrent requests
const BATCH_DELAY = 1000; // 1 second delay between batches

let currentStatus = null;

const isEastCoastStation = (station) => {
  // GeoJSON format is [longitude, latitude]
  const coordinates = station.location?.coordinates;
  if (!coordinates) {
    logger.debug(`No coordinates found for station: ${station.id}`);
    return false;
  }
  const [longitude, latitude] = coordinates;
  
  logger.debug(`Checking station ${station.id} at [${longitude}, ${latitude}]:`);
  logger.debug(`Latitude check: ${EAST_COAST_BOUNDS.south} <= ${latitude} <= ${EAST_COAST_BOUNDS.north}`);
  logger.debug(`Longitude check: ${EAST_COAST_BOUNDS.west} <= ${longitude} <= ${EAST_COAST_BOUNDS.east}`);
  
  const latitudeInRange = latitude >= EAST_COAST_BOUNDS.south && latitude <= EAST_COAST_BOUNDS.north;
  const longitudeInRange = longitude >= EAST_COAST_BOUNDS.west && longitude <= EAST_COAST_BOUNDS.east;
  
  const isEastCoast = latitudeInRange && longitudeInRange;
  
  if (isEastCoast) {
    logger.debug(`Found East Coast station: ${station.id}`);
  } else {
    logger.debug(`Station ${station.id} excluded: lat in range: ${latitudeInRange}, lon in range: ${longitudeInRange}`);
  }
  
  return isEastCoast;
};

const updateStatus = (updates) => {
  if (!currentStatus) return;
  currentStatus = {
    ...currentStatus,
    ...updates,
    lastUpdated: Date.now()
  };
  
  const progress = ((currentStatus.processedCount / currentStatus.totalStations) * 100).toFixed(1);
  logger.info(`Prefetch progress: ${progress}% (${currentStatus.processedCount}/${currentStatus.totalStations})`);
  logger.info(`Success: ${currentStatus.successCount}, Failed: ${currentStatus.failureCount}`);
};

const processBatch = async (stations, ndbcService) => {
  const results = await Promise.all(
    stations.map(async (station) => {
      try {
        const buoyConfig = getCacheConfig('buoyData', station.id);
        const buoyData = await getOrSet(
          buoyConfig.key,
          () => ndbcService.fetchBuoyData(station.id),
          buoyConfig.ttl
        );
        
        // Also prefetch wave model forecast if we have coordinates
        if (buoyData && station.location?.coordinates) {
          const [longitude, latitude] = station.location.coordinates;
          
          try {
            const forecastConfig = getCacheConfig('waveModel', `${latitude}_${longitude}`);
            await getOrSet(
              forecastConfig.key,
              () => waveModelService.getPointForecast(latitude, longitude),
              forecastConfig.ttl
            );
            logger.debug(`✓ Wave forecast prefetched for station ${station.id}`);
          } catch (forecastError) {
            logger.warn(`Failed to prefetch wave forecast for station ${station.id}:`, forecastError);
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
            error: error.message || 'Unknown error'
          });
          updateStatus({});
        }
        
        logger.error(`✗ Station ${station.id} prefetch failed:`, error);
        return { 
          station: station.id, 
          success: false, 
          error: error.message || 'Unknown error'
        };
      }
    })
  );
  return results;
};

const getPrefetchStatus = () => currentStatus;

const prefetchEastCoastBuoyData = async (ndbcService) => {
  try {
    logger.info('🚀 Starting East Coast buoy data prefetch');
    const startTime = Date.now();

    const eastCoastStations = ndbcService.stations.filter(isEastCoastStation);
    logger.info(`📍 Found ${eastCoastStations.length} East Coast stations to prefetch`);

    currentStatus = {
      status: 'running',
      startTime,
      totalStations: eastCoastStations.length,
      processedCount: 0,
      successCount: 0,
      failureCount: 0,
      lastUpdated: startTime,
      errors: []
    };

    for (let i = 0; i < eastCoastStations.length; i += BATCH_SIZE) {
      const batch = eastCoastStations.slice(i, i + BATCH_SIZE);
      logger.info(`⏳ Processing batch ${Math.floor(i/BATCH_SIZE) + 1}/${Math.ceil(eastCoastStations.length/BATCH_SIZE)}`);
      await processBatch(batch, ndbcService);

      if (i + BATCH_SIZE < eastCoastStations.length) {
        await new Promise(resolve => setTimeout(resolve, BATCH_DELAY));
      }
    }

    const endTime = Date.now();
    const duration = (endTime - startTime) / 1000;

    currentStatus = {
      ...currentStatus,
      status: 'completed',
      endTime
    };

    logger.info('✅ Prefetch completed:');
    logger.info(`📊 Summary:
    - Duration: ${duration.toFixed(1)}s
    - Total Stations: ${currentStatus.totalStations}
    - Successful: ${currentStatus.successCount}
    - Failed: ${currentStatus.failureCount}
    - Success Rate: ${((currentStatus.successCount / currentStatus.totalStations) * 100).toFixed(1)}%`);

    if (currentStatus.errors.length > 0) {
      logger.warn('⚠️ Failed stations:', currentStatus.errors);
    }

    return currentStatus;
  } catch (error) {
    const errorStatus = {
      status: 'failed',
      startTime: Date.now(),
      endTime: Date.now(),
      totalStations: 0,
      processedCount: 0,
      successCount: 0,
      failureCount: 0,
      lastUpdated: Date.now(),
      errors: [{ station: 'system', error: error.message || 'Unknown error' }]
    };
    currentStatus = errorStatus;
    logger.error('❌ Error during East Coast prefetch:', error);
    throw error;
  }
};

module.exports = {
  prefetchEastCoastBuoyData,
  getPrefetchStatus
}; 