// routes/index.js
const express = require("express");
const { query } = require("express-validator");
const rateLimit = require("express-rate-limit");
const offshoreStationController = require("../controllers/offshoreStationController");
const tideStationController = require("../controllers/tideStationController");

const router = express.Router();

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
});

// NDBC Offshore Stations
router.get("/offshore-stations", offshoreStationController.getAllStations);
router.get(
  "/offshore-stations/nearest",
  [
    query("lat").isFloat().withMessage("Latitude must be a valid number"),
    query("lon").isFloat().withMessage("Longitude must be a valid number"),
  ],
  offshoreStationController.getClosestStation
);
router.get(
  "/offshore-stations/:stationId",
  limiter,
  offshoreStationController.getStationData
);

// NOAA Co-Ops Tide Stations
router.get("/tide-stations", tideStationController.getAllStations);
router.get(
  "/tide-stations/nearest",
  [
    query("lat").isFloat().withMessage("Latitude must be a valid number"),
    query("lon").isFloat().withMessage("Longitude must be a valid number"),
  ],
  tideStationController.getClosestStation
);
router.get(
  "/tide-stations/:stationId",
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
  tideStationController.getStationData
);

// Catch all 404 errors
router.use("*", (req, res) => {
  res.status(404).json({
    status: "fail",
    message: `Can't find ${req.originalUrl} on this server`,
  });
});

module.exports = router;
