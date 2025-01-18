const { AppError } = require("../middlewares/errorHandler");
const { logger } = require("../utils/logger");
const ndbcService = require("./ndbcService");
const waveModelService = require("./waveModelService");

/**
 * Fetch station data with forecast
 */
async function getStationData(stationId) {
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
        `Fetching forecast for station ${stationId} at lat=${lat}, lon=${normalizedLon}`
      );

      const modelData = await Promise.race([
        waveModelService.getPointForecast(lat, normalizedLon),
        new Promise((_, reject) =>
          setTimeout(
            () => reject(new AppError(504, "Forecast fetch timeout")),
            20000
          )
        ),
      ]);

      if (modelData?.forecasts?.length) {
        // Group forecasts by date
        const forecastsByDate = modelData.forecasts.reduce((acc, f) => {
          const date = f.time.split("T")[0];
          if (!acc[date]) {
            acc[date] = [];
          }
          acc[date].push({
            time: f.time,
            wind: f.wind?.speed
              ? {
                  speed: f.wind.speed,
                  direction: f.wind.direction,
                }
              : null,
            waves: f.waves?.height
              ? {
                  height: f.waves.height,
                  period: f.waves.period,
                  direction: f.waves.direction,
                  windWave: f.waves.windWave,
                  swells: f.waves.swells,
                }
              : null,
          });
          return acc;
        }, {});

        forecast = {
          metadata: modelData.metadata,
          days: Object.entries(forecastsByDate).map(([date, periods]) => ({
            date,
            periods,
          })),
        };
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
      waves: stationData.waves?.height
        ? {
            height: stationData.waves.height,
            dominantPeriod: stationData.waves.dominantPeriod,
            averagePeriod: stationData.waves.averagePeriod,
            direction: stationData.waves.direction,
            trend: stationData.trends?.waveHeight || null,
            steepness: stationData.waves.spectral?.steepness || null,
            swell: stationData.waves.spectral?.swell || null,
            windWave: stationData.waves.spectral?.windWave || null,
          }
        : null,
      weather: {
        pressure: stationData.conditions.pressure,
        airTemp: stationData.conditions.airTemp,
        waterTemp: stationData.conditions.waterTemp,
        dewPoint: stationData.conditions.dewPoint,
      },
    },
    summary: stationData.marinerSummary || null,
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
    response.forecast = forecast;
  } else if (forecastError) {
    response.forecast = { error: forecastError };
  }

  return response;
}

module.exports = {
  getStationData,
};
