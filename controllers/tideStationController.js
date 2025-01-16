const { AppError } = require("../middlewares/errorHandler");
const { logger } = require("../utils/logger");
const tideService = require("../services/tideService");

/**
 * Get all tide stations
 */
const getAllStations = async (req, res, next) => {
  try {
    const stations = await tideService.getAllStations();
    res.status(200).json(stations);
  } catch (error) {
    next(error);
  }
};

/**
 * Get closest tide station to coordinates
 */
const getClosestStation = async (req, res, next) => {
  const { lat, lon } = req.query;
  try {
    const station = await tideService.findClosestStation(
      parseFloat(lat),
      parseFloat(lon)
    );
    if (!station) {
      throw new AppError(404, "No tide station found near coordinates");
    }
    res.status(200).json(station);
  } catch (error) {
    next(error);
  }
};

/**
 * Get tide station data by ID
 */
const getStationData = async (req, res, next) => {
  const { stationId } = req.params;
  const { startDate, endDate } = req.query;

  try {
    const tideData = await tideService.getTidePredictions(
      stationId,
      startDate,
      endDate
    );
    if (!tideData) {
      throw new AppError(404, "Tide data not found");
    }

    const response = {
      id: stationId,
      predictions: tideData.predictions,
      metadata: tideData.metadata,
      units: {
        height: "ft",
        time: "UTC",
      },
    };

    res.status(200).json(response);
  } catch (error) {
    logger.error(`Error processing tide station request`, {
      stationId,
      error: error.message,
      stack: error.stack,
    });
    next(error);
  }
};

module.exports = {
  getAllStations,
  getClosestStation,
  getStationData,
};
