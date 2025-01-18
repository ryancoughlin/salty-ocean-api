const { AppError } = require("../../middlewares/errorHandler");
const { logger } = require("../../utils/logger");
const { getStations, getPredictions } = require("../services/tideService");

/**
 * Get all tide stations
 */
const getAllStations = async (req, res, next) => {
  try {
    const stations = await getStations();
    res.status(200).json(stations);
  } catch (error) {
    next(error);
  }
};

/**
 * Get stations in GeoJSON format for Mapbox
 */
const getStationsGeoJSON = async (req, res, next) => {
  try {
    const stations = await getStations();

    const geojson = {
      type: "FeatureCollection",
      features: stations.map((station) => ({
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [station.lng, station.lat],
        },
        properties: {
          id: station.id,
          name: station.name,
        },
      })),
    };
    res.status(200).json(geojson);
  } catch (error) {
    next(error);
  }
};

/**
 * Get predictions for a station
 */
const getStationPredictions = async (req, res, next) => {
  const { stationId } = req.params;
  const date = req.query.date ? new Date(req.query.date) : new Date();

  try {
    const stations = await getStations();
    const station = stations.find((s) => s.id === stationId);

    if (!station) {
      throw new AppError(404, "Station not found");
    }

    const predictions = await getPredictions(stationId, date);

    res.status(200).json({
      id: stationId,
      name: station.name,
      predictions: predictions.map((p) => ({
        time: p.t,
        height: parseFloat(p.v),
      })),
    });
  } catch (error) {
    next(error);
  }
};

module.exports = {
  getAllStations,
  getStationsGeoJSON,
  getStationPredictions,
};
