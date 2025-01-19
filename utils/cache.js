const NodeCache = require("node-cache");
const { logger } = require("./logger");

// Cache configuration
const DEFAULT_TTL = 30 * 60; // 30 minutes
const CHECK_PERIOD = 60; // Check for expired keys every 60 seconds

// Initialize cache with configuration
const cache = new NodeCache({
  stdTTL: DEFAULT_TTL,
  checkperiod: CHECK_PERIOD,
  useClones: false,
  deleteOnExpire: true,
  maxKeys: 1000, // Limit maximum number of keys
});

// Cache statistics
let cacheHits = 0;
let cacheMisses = 0;

// Monitor cache events
cache.on("expired", (key, value) => {
  logger.debug(`Cache key expired: ${key}`);
});

cache.on("del", (key, value) => {
  logger.debug(`Cache key deleted: ${key}`);
});

cache.on("flush", () => {
  logger.info("Cache flushed");
});

/**
 * Get a value from cache with stale-while-revalidate pattern
 * @param {string} key - Cache key
 * @param {Function} fetchFn - Function to fetch fresh data if cache miss
 * @param {number} [ttl] - Time to live in seconds
 * @returns {Promise<{data: any, fromCache: boolean}>}
 */
async function getOrSet(key, fetchFn, ttl = DEFAULT_TTL) {
  try {
    const value = cache.get(key);

    if (value !== undefined) {
      cacheHits++;
      return value;
    }

    cacheMisses++;
    const freshData = await fetchFn();

    if (freshData !== undefined && freshData !== null) {
      cache.set(key, freshData, ttl);
    }

    return freshData;
  } catch (error) {
    logger.error(`Cache error for key ${key}:`, error);
    throw error;
  }
}

/**
 * Get a value directly from cache without fetching
 * @param {string} key - Cache key
 * @returns {any} Cached value or undefined if not found
 */
function getCache(key) {
  const value = cache.get(key);
  if (value !== undefined) {
    cacheHits++;
    return value;
  }
  cacheMisses++;
  return undefined;
}

/**
 * Get cache statistics
 * @returns {Object} Cache statistics
 */
function getStats() {
  const stats = cache.getStats();
  return {
    ...stats,
    hits: cacheHits,
    misses: cacheMisses,
    hitRate: cacheHits / (cacheHits + cacheMisses) || 0,
    keys: cache.keys(),
    memoryUsage: process.memoryUsage().heapUsed,
  };
}

/**
 * Clear all cache entries
 */
function clearCache() {
  cache.flushAll();
  cacheHits = 0;
  cacheMisses = 0;
}

/**
 * Delete a specific cache entry
 * @param {string} key - Cache key to delete
 */
function deleteCache(key) {
  cache.del(key);
}

module.exports = {
  getOrSet,
  getCache,
  getStats,
  clearCache,
  deleteCache,
  DEFAULT_TTL,
};
