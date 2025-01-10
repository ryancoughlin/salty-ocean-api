const { AppError } = require('../middlewares/errorHandler');
const { logger } = require('../utils/logger');
const ndbcService = require('../services/ndbcService');
const waveModelService = require('../services/waveModelService');
const waveConditionsService = require('../services/waveConditionsService');
const { getModelRunCacheDuration } = require('../utils/cacheManager');

/**
 * Get buoy data by ID
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Express next middleware function
 * @throws {AppError} 400 - Invalid buoy ID format
 * @throws {AppError} 404 - Buoy data not found
 * @throws {AppError} 500 - Internal server error
 */
const getBuoyData = async (req, res, next) => {
    const startTime = Date.now();
    const { buoyId } = req.params;

    try {
        // Validate buoy ID format
        if (!buoyId?.match(/^\d+$/)) {
            throw new AppError(400, 'Invalid buoy ID format');
        }

        // Get cache duration from cache manager
        const cacheDuration = getModelRunCacheDuration();
        res.set('Cache-Control', `public, max-age=${cacheDuration}`);
        res.set('Vary', 'Accept-Encoding');

        // Start parallel requests with timeout
        const [buoyData, stationInfo] = await Promise.all([
            Promise.race([
                ndbcService.fetchBuoyData(buoyId),
                new Promise((_, reject) => 
                    setTimeout(() => reject(new AppError(504, 'Buoy data fetch timeout')), 5000)
                )
            ]),
            ndbcService.getStationById(buoyId)
        ]);

        if (!buoyData) {
            throw new AppError(404, 'Buoy data not found');
        }

        if (!stationInfo) {
            logger.warn(`Station info not found for buoy ${buoyId}`);
        }

        // Structure station info
        const buoyInfo = {
            id: buoyId,
            name: stationInfo?.name,
            location: stationInfo?.location
        };

        // Fetch forecast if we have location
        let forecast = null;
        
        if (stationInfo?.location?.coordinates) {
            try {
                const [lon, lat] = stationInfo.location.coordinates;
                logger.debug(`Fetching forecast for buoy ${buoyId} at lat=${lat}, lon=${lon}`);
                
                forecast = await Promise.race([
                    waveModelService.getPointForecast(lat, lon),
                    new Promise((_, reject) => 
                        setTimeout(() => reject(new AppError(504, 'Forecast fetch timeout')), 10000)
                    )
                ]);
                
                if (forecast) {
                    forecast.summaries = waveConditionsService.generateSummaries(forecast, {
                        latitude: lat,
                        longitude: lon
                    });
                    logger.debug(`Generated forecast summaries for buoy ${buoyId}`);
                }
            } catch (forecastError) {
                logger.warn(`Failed to fetch forecast for buoy ${buoyId}:`, {
                    error: forecastError.message,
                    coordinates: stationInfo.location.coordinates
                });
            }
        }

        // Build response
        const response = {
            id: buoyInfo.id,
            name: buoyInfo.name,
            location: buoyInfo.location,
            observations: {
                time: buoyData.time,
                wind: buoyData.wind.speed ? {
                    direction: buoyData.wind.direction,
                    speed: buoyData.wind.speed,
                    gust: buoyData.wind.gust,
                    trend: buoyData.trends?.wind || null
                } : null,
                waves: buoyData.waves?.height && {
                    height: buoyData.waves.height,
                    dominantPeriod: buoyData.waves.dominantPeriod,
                    averagePeriod: buoyData.waves.averagePeriod,
                    direction: buoyData.waves.direction,
                    trend: buoyData.trends?.waveHeight || null,
                    spectral: buoyData.waves.spectral && {
                        steepness: buoyData.waves.spectral.steepness,
                        swell: buoyData.waves.spectral.swell,
                        windWave: buoyData.waves.spectral.windWave
                    }
                },
                weather: {
                    pressure: buoyData.conditions.pressure,
                    airTemp: buoyData.conditions.airTemp,
                    waterTemp: buoyData.conditions.waterTemp,
                    dewPoint: buoyData.conditions.dewPoint
                }
            },
            summary: buoyData.trends?.summary || null
        };

        // Add forecast if available
        if (forecast) {
            response.modelRun = forecast.modelRun;
            response.forecast = forecast.days.map(day => ({
                date: day.date,
                waves: day.summary.waveHeight ? {
                    min: day.summary.waveHeight.min,
                    max: day.summary.waveHeight.max,
                    avg: day.summary.waveHeight.avg
                } : null,
                wind: day.summary.windSpeed ? {
                    min: day.summary.windSpeed.min,
                    max: day.summary.windSpeed.max,
                    avg: day.summary.windSpeed.avg
                } : null,
                periods: day.periods.map(period => ({
                    time: period.time,
                    waves: period.waveHeight ? {
                        height: period.waveHeight,
                        period: period.wavePeriod,
                        direction: period.waveDirection
                    } : null,
                    wind: period.windSpeed ? {
                        speed: period.windSpeed,
                        direction: period.windDirection
                    } : null
                }))
            }));
            response.summary = forecast.summaries;
            response.units = {
                waveHeight: 'ft',
                wavePeriod: 'seconds',
                waveDirection: 'degrees',
                windSpeed: 'mph',
                windDirection: 'degrees'
            };
        }

        // Remove null values and send response
        const cleanResponse = JSON.parse(JSON.stringify(response));
        
        // Log performance metrics
        const duration = Date.now() - startTime;
        logger.info(`Buoy data request completed`, {
            buoyId,
            duration,
            hasForecast: !!forecast,
            cacheDuration,
            statusCode: 200
        });

        res.status(200).json(cleanResponse);
    } catch (error) {
        logger.error(`Error processing buoy data request`, {
            buoyId,
            error: error.message,
            stack: error.stack,
            statusCode: error.statusCode || 500,
            duration: Date.now() - startTime
        });
        next(error);
    }
};

module.exports = {
    getBuoyData
}; 