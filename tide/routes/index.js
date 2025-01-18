const express = require("express");
const tideStationController = require("../controllers/tideStationController");

const router = express.Router();

router.get("/", tideStationController.getAllStations);
router.get("/geojson", tideStationController.getStationsGeoJSON);
router.get(
  "/:stationId/predictions",
  tideStationController.getStationPredictions
);

module.exports = router;
