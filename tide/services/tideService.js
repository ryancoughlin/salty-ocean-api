const axios = require("axios");
const { logger } = require("../../utils/logger");
const { getOrSet } = require("../../utils/cache");
const { AppError } = require("../../middlewares/errorHandler");

// Constants
const REQUEST_TIMEOUT = 10000; // 10 seconds
const STATIONS_API_URL =
  "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json";
const PREDICTIONS_API_URL =
  "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter";

async function getStations() {
  try {
    const response = await axios.get(STATIONS_API_URL, {
      timeout: REQUEST_TIMEOUT,
    });

    if (!response.data?.stations) {
      throw new Error("Invalid response from NOAA API");
    }

    return response.data.stations.filter((station) => station.tidal === true);
  } catch (error) {
    logger.error("Error fetching stations:", error.message);
    throw error;
  }
}

async function getPredictions(stationId, date = new Date()) {
  try {
    const params = {
      station: stationId,
      product: "predictions",
      datum: "MLLW",
      time_zone: "gmt",
      units: "english",
      format: "json",
      date: "today",
    };

    const response = await axios.get(PREDICTIONS_API_URL, {
      params,
      timeout: REQUEST_TIMEOUT,
    });

    if (!response.data?.predictions) {
      throw new AppError(404, "No predictions available for this station");
    }

    return response.data.predictions;
  } catch (error) {
    logger.error("Error fetching predictions:", {
      stationId,
      error: error.message,
    });
    throw error;
  }
}

module.exports = {
  getStations,
  getPredictions,
};
