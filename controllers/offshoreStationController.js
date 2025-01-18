const { AppError } = require("../middlewares/errorHandler");
const { logger } = require("../utils/logger");
const ndbcService = require("../services/ndbcService");
const offshoreStationService = require("../services/offshoreStationService");
const { getModelRunCacheDuration } = require("../utils/cacheManager");

/**
 * Get all offshore stations
 */
const getAllStations = async (req, res, next) => {
  try {
    const stations = await ndbcService.getAllStations();
    res.status(200).json(stations);
  } catch (error) {
    next(error);
  }
};

/**
 * Get closest offshore station to coordinates
 */
const getClosestStation = async (req, res, next) => {
  const { lat, lon } = req.query;
  try {
    const station = await ndbcService.findClosestStation(
      parseFloat(lat),
      parseFloat(lon)
    );
    if (!station) {
      throw new AppError(404, "No station found near coordinates");
    }
    res.status(200).json(station);
  } catch (error) {
    next(error);
  }
};

/**
 * Get station data by ID
 */
const getStationData = async (req, res, next) => {
  const startTime = Date.now();
  const { stationId } = req.params;

  try {
    // Get cache duration from cache manager
    const cacheDuration = getModelRunCacheDuration();
    res.set("Cache-Control", `public, max-age=${cacheDuration}`);
    res.set("Vary", "Accept-Encoding");

    // Get station data with forecast
    const data = await offshoreStationService.getStationData(stationId);

    // Remove null values and send response
    const cleanResponse = JSON.parse(JSON.stringify(data));
    res.status(200).json(cleanResponse);
  } catch (error) {
    logger.error(`Error processing station data request`, {
      stationId,
      error: error.message,
      stack: error.stack,
      statusCode: error.statusCode || 500,
      duration: Date.now() - startTime,
    });
    next(error);
  }
};

module.exports = {
  getAllStations,
  getClosestStation,
  getStationData,
};
