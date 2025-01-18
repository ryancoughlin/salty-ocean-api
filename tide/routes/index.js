const express = require("express");
const { query } = require("express-validator");
const tideStationController = require("../controllers/tideStationController");

const router = express.Router();

// NOAA Co-Ops Tide Stations
router.get("/", tideStationController.getAllStations);
router.get("/geojson", tideStationController.getStationsGeoJSON);
router.get(
  "/nearest",
  [
    query("lat").isFloat().withMessage("Latitude must be a valid number"),
    query("lon").isFloat().withMessage("Longitude must be a valid number"),
  ],
  tideStationController.getClosestStation
);
router.get(
  "/:stationId",
  [
    query("startDate")
      .optional()
      .isISO8601()
      .withMessage("Start date must be a valid ISO date"),
    query("endDate")
      .optional()
      .isISO8601()
      .withMessage("End date must be a valid ISO date"),
  ],
  tideStationController.getStationPredictions
);

module.exports = router;
