const { AppError } = require("../../middlewares/errorHandler");
const { logger } = require("../../utils/logger");
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
      throw new AppError(404, "No station found near coordinates");
    }
    res.status(200).json(station);
  } catch (error) {
    next(error);
  }
};

/**
 * Get tide predictions for a station
 */
const getStationPredictions = async (req, res, next) => {
  const { stationId } = req.params;
  const { startDate, endDate } = req.query;

  try {
    const predictions = await tideService.getTidePredictions(
      stationId,
      startDate,
      endDate
    );
    res.status(200).json(predictions);
  } catch (error) {
    next(error);
  }
};

module.exports = {
  getAllStations,
  getClosestStation,
  getStationPredictions,
};
