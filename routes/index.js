// routes/index.js
const express = require("express");
const { query } = require("express-validator");
const rateLimit = require("express-rate-limit");
const offshoreStationController = require("../controllers/offshoreStationController");
const tideRoutes = require("../tide/routes");

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

// Mount tide routes
router.use("/tide-stations", tideRoutes);

// Catch all 404 errors
router.use("*", (req, res) => {
  res.status(404).json({
    status: "fail",
    message: `Can't find ${req.originalUrl} on this server`,
  });
});

module.exports = router;
