const { logger } = require('../utils/logger');
const ndbcService = require('./ndbcService');
const { prefetchEastCoastBuoyData } = require('./buoyPrefetchService');

/**
 * Initialize data on app startup
 */
async function initializeData() {
    try {
        logger.info('🚀 Starting initial data prefetch...');
        
        // Wait for NDBC service to load stations
        await ndbcService.loadStations();
        
        // Start prefetch process
        const result = await prefetchEastCoastBuoyData(ndbcService);
        
        logger.info('✅ Initial prefetch completed:', {
            totalStations: result.totalStations,
            successful: result.successCount,
            failed: result.failureCount,
            duration: ((result.endTime - result.startTime) / 1000).toFixed(1) + 's'
        });
        
        return result;
    } catch (error) {
        logger.error('❌ Error during initial data prefetch:', error);
        // Don't throw - we want the app to start even if prefetch fails
        return null;
    }
}

module.exports = {
    initializeData
}; 