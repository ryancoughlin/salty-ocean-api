const { logger } = require('./logger');
const CONFIG = require('../config/waveModelConfig');

// Cache types and their TTL calculators
const CACHE_TYPES = {
    waveModel: {
        keyPrefix: 'wave_model',
        getTTL: getModelRunCacheDuration
    },
    buoyData: {
        keyPrefix: 'ndbc_buoy',
        getTTL: getNDBCCacheDuration
    }
};

/**
 * Calculates cache duration based on NOAA wave model run times
 * Memoized to recalculate only once per minute for performance
 */
const getModelRunCacheDuration = (() => {
    let cachedDuration = null;
    let lastCalculated = 0;
    const RECALCULATE_INTERVAL = 60000; // 1 minute
    
    const calculate = () => {
        const now = new Date();
        const currentHour = now.getUTCHours();
        const currentMinute = now.getUTCMinutes();

        // Find next model run hour (00, 06, 12, 18)
        const modelRuns = CONFIG.modelRuns.hours.map(h => parseInt(h));
        const nextRun = modelRuns.find(hour => hour > currentHour) || modelRuns[0];
        
        // Calculate hours until next run + availability delay
        let hoursUntilNextRun = nextRun > currentHour ? 
            nextRun - currentHour : 
            (24 - currentHour) + nextRun;
        hoursUntilNextRun += CONFIG.modelRuns.availableAfter[nextRun.toString().padStart(2, '0')];
        
        // Convert to seconds and subtract elapsed minutes
        return Math.min(
            (hoursUntilNextRun * 60 - currentMinute) * 60,
            CONFIG.cache.hours * 3600
        );
    };
    
    return () => {
        const now = Date.now();
        if (!cachedDuration || now - lastCalculated > RECALCULATE_INTERVAL) {
            cachedDuration = calculate();
            lastCalculated = now;
            logger.debug('Recalculated model run cache duration', { 
                cacheDuration: cachedDuration,
                nextCalculation: new Date(now + RECALCULATE_INTERVAL).toISOString()
            });
        }
        return cachedDuration;
    };
})();

// NDBC updates every 30 minutes at :26 and :56 past the hour
const NDBC_UPDATE_MINUTES = [26, 56];

/**
 * Calculate TTL until next NDBC update
 */
const getNDBCCacheDuration = () => {
    const now = new Date();
    const currentMinute = now.getMinutes();
    const nextUpdate = NDBC_UPDATE_MINUTES.find(min => min > currentMinute) || NDBC_UPDATE_MINUTES[0];
    
    const minutesUntilUpdate = nextUpdate > currentMinute ? 
        nextUpdate - currentMinute : 
        (60 - currentMinute) + nextUpdate;
    
    return (minutesUntilUpdate * 60) + 60; // Add 60s buffer
};

/**
 * Get cache TTL and key for a data type
 */
const getCacheConfig = (type, identifier) => {
    const cacheType = CACHE_TYPES[type];
    if (!cacheType) {
        return {
            key: identifier,
            ttl: CONFIG.cache.hours * 3600
        };
    }
    
    return {
        key: `${cacheType.keyPrefix}_${identifier}`,
        ttl: cacheType.getTTL()
    };
};

module.exports = {
    getCacheConfig
}; 