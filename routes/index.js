// routes/index.js
const express = require('express');
const { query } = require('express-validator');
const rateLimit = require('express-rate-limit');
const stationController = require('../controllers/stationController');
const buoyController = require('../controllers/buoyController');

const router = express.Router();

// Rate limiting
const limiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 100 // limit each IP to 100 requests per windowMs
});

// Station routes
router.get('/stations', stationController.getAllStations);

router.get('/stations/nearest', [
    query('lat').isFloat().withMessage('Latitude must be a valid number'),
    query('lon').isFloat().withMessage('Longitude must be a valid number')
], stationController.getClosestStation);

router.get('/stations/:stationId', [
    query('startDate').optional().isISO8601().withMessage('Start date must be a valid ISO date'),
    query('endDate').optional().isISO8601().withMessage('End date must be a valid ISO date')
], stationController.getStationDetails);

// Buoy routes
router.get('/buoys/:buoyId', limiter, buoyController.getBuoyData);

// Catch all 404 errors
router.use('*', (req, res) => {
    res.status(404).json({
        status: 'fail',
        message: `Can't find ${req.originalUrl} on this server`
    });
});

module.exports = router;
