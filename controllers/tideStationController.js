const { AppError } = require("../middlewares/errorHandler");
const { logger } = require("../utils/logger");
const tideService = require("../services/tideService");

/**
 * Get all tide stations
 */
const getAllStations = async (req, res, next) => {
  try {
    const stations = tideService.getAllStations();
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

  if (!lat || !lon) {
    throw new AppError(400, "Latitude and longitude are required");
  }

  try {
    const station = tideService.findClosestStation(
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
 * Get tide station predictions
 */
const getStationPredictions = async (req, res, next) => {
  const { stationId } = req.params;
  const { startDate, endDate } = req.query;

  if (!startDate || !endDate) {
    throw new AppError(400, "Start date and end date are required");
  }

  try {
    const tideData = await tideService.getTidePredictions(
      stationId,
      startDate,
      endDate
    );

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
  getStationPredictions,
};
