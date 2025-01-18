const { AppError } = require("../middlewares/errorHandler");
const { logger } = require("../utils/logger");
const ndbcService = require("../services/ndbcService");
const waveModelService = require("../services/waveModelService");
const waveConditionsService = require("../services/waveConditionsService");
const { getModelRunCacheDuration } = require("../utils/cacheManager");

/**
 * Get all offshore stations
 */
const getAllStations = async (req, res, next) => {
  try {
    const stations = await ndbcService.getAllStations();
    res.status(200).json(stations);
  } catch (error) {
    next(error);
  }
};

/**
 * Get closest offshore station to coordinates
 */
const getClosestStation = async (req, res, next) => {
  const { lat, lon } = req.query;
  try {
    const station = await ndbcService.findClosestStation(
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
 * Get station data by ID
 */
const getStationData = async (req, res, next) => {
  const startTime = Date.now();
  const { stationId } = req.params;

  try {
    // Get cache duration from cache manager
    const cacheDuration = getModelRunCacheDuration();
    res.set("Cache-Control", `public, max-age=${cacheDuration}`);
    res.set("Vary", "Accept-Encoding");

    // Start parallel requests with timeout
    const [stationData, stationMetadata] = await Promise.all([
      Promise.race([
        ndbcService.fetchBuoyData(stationId),
        new Promise((_, reject) =>
          setTimeout(
            () => reject(new AppError(504, "Station data fetch timeout")),
            5000
          )
        ),
      ]),
      ndbcService.getStationById(stationId),
    ]);

    if (!stationData) {
      throw new AppError(404, "Station data not found");
    }

    if (!stationMetadata) {
      logger.warn(`Station info not found for station ${stationId}`);
    }

    // Structure station info
    const stationInfo = {
      id: stationId,
      name: stationMetadata?.name,
      location: stationMetadata?.location,
    };

    // Fetch forecast if we have location
    let forecast = null;
    let forecastError = null;

    if (stationInfo?.location?.coordinates) {
      try {
        const [lon, lat] = stationInfo.location.coordinates;
        // Normalize longitude to 0-360 for wave model
        const normalizedLon = lon < 0 ? lon + 360 : lon;

        logger.debug(
          `Station ${stationId} coordinates: [${lon}, ${lat}] (lon, lat)`
        );
        logger.debug(
          `Fetching forecast for station ${stationId} at lat=${lat}, lon=${normalizedLon}`
        );

        forecast = await Promise.race([
          waveModelService.getPointForecast(lat, normalizedLon),
          new Promise((_, reject) =>
            setTimeout(
              () => reject(new AppError(504, "Forecast fetch timeout")),
              20000
            )
          ),
        ]);

        if (forecast?.days?.length) {
          forecast.summaries = waveConditionsService.generateSummaries(
            forecast,
            {
              latitude: lat,
              longitude: lon,
            }
          );
        }
      } catch (error) {
        forecastError = {
          message: error.message,
          type: error.name,
          statusCode: error.statusCode || 500,
        };
        logger.warn(`Failed to fetch forecast for station ${stationId}:`, {
          error: error.message,
          stack: error.stack,
          coordinates: stationInfo.location.coordinates,
        });
      }
    }

    const response = {
      id: stationInfo.id,
      name: stationInfo.name,
      location: stationInfo.location,
      observations: {
        time: stationData.time,
        wind: stationData.wind.speed
          ? {
              direction: stationData.wind.direction,
              speed: stationData.wind.speed,
              gust: stationData.wind.gust,
              trend: stationData.trends?.wind || null,
            }
          : null,
        waves: stationData.waves?.height && {
          height: stationData.waves.height,
          dominantPeriod: stationData.waves.dominantPeriod,
          averagePeriod: stationData.waves.averagePeriod,
          direction: stationData.waves.direction,
          trend: stationData.trends?.waveHeight || null,
          steepness: stationData.waves.spectral?.steepness || null,
          swell: stationData.waves.spectral?.swell || null,
          windWave: stationData.waves.spectral?.windWave || null,
        },
        weather: {
          pressure: stationData.conditions.pressure,
          airTemp: stationData.conditions.airTemp,
          waterTemp: stationData.conditions.waterTemp,
          dewPoint: stationData.conditions.dewPoint,
        },
      },
      summary: stationData.trends?.summary || null,
      units: {
        waveHeight: "ft",
        wavePeriod: "seconds",
        waveDirection: "degrees",
        windSpeed: "mph",
        windDirection: "degrees",
        windComponents: "mph",
      },
    };

    // Add forecast if available
    if (forecast?.days?.length > 0) {
      response.forecast = {
        metadata: forecast.metadata,
        days: forecast.days.map((day) => ({
          date: day.date,
          periods: day.periods.map((period) => ({
            time: period.time,
            wind: period.wind?.speed
              ? {
                  speed: period.wind.speed,
                  direction: period.wind.direction,
                }
              : null,
            waves: period.waves?.height
              ? {
                  height: period.waves.height,
                  period: period.waves.period,
                  direction: period.waves.direction,
                  windWave: period.components?.windWave || null,
                  swells: period.components?.swells || null,
                }
              : null,
          })),
        })),
      };
    } else if (forecastError) {
      response.forecast = {
        error: forecastError,
      };
    }

    // Remove null values and send response
    const cleanResponse = JSON.parse(JSON.stringify(response));
    res.status(200).json(cleanResponse);
  } catch (error) {
    logger.error(`Error processing station data request`, {
      stationId,
      error: error.message,
      stack: error.stack,
      statusCode: error.statusCode || 500,
      duration: Date.now() - startTime,
    });
    next(error);
  }
};

module.exports = {
  getAllStations,
  getClosestStation,
  getStationData,
};
