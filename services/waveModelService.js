const axios = require("axios");
const { logger } = require("../utils/logger");
const { getOrSet } = require("../utils/cache");
const CONFIG = require("../config/waveModelConfig");
const https = require("https");

// Create reusable HTTPS agent
const agent = new https.Agent({
  keepAlive: true,
  timeout: 60000,
});

// Find model for location
function findModelForLocation(lat, lon) {
  const normalizedLon = lon < 0 ? lon + 360 : lon;
  const model = Object.entries(CONFIG.models).find(([_, m]) => {
    return (
      lat >= m.grid.lat.start &&
      lat <= m.grid.lat.end &&
      normalizedLon >= m.grid.lon.start &&
      normalizedLon <= m.grid.lon.end
    );
  });

  if (!model) {
    throw new Error(`Location ${lat}°N, ${lon}°W is outside all model bounds`);
  }

  return { id: model[0], ...model[1] };
}

// Get grid indices
function getGridLocation(lat, lon, model) {
  const normalizedLon = lon < 0 ? lon + 360 : lon;
  const latIdx = Math.round(
    (lat - model.grid.lat.start) / model.grid.lat.resolution
  );
  const lonIdx = Math.round(
    (normalizedLon - model.grid.lon.start) / model.grid.lon.resolution
  );
  return { latIdx, lonIdx };
}

// Get latest model run
function getAvailableModelRun() {
  const now = new Date();
  const currentHour = now.getUTCHours();
  const availableRun = CONFIG.modelRuns.hours
    .map((hour) => ({
      hour,
      availableAt: parseInt(hour) + CONFIG.modelRuns.availableAfter[hour],
    }))
    .reverse()
    .find((run) => currentHour >= run.availableAt);

  if (!availableRun) {
    const yesterday = new Date(now);
    yesterday.setUTCDate(yesterday.getUTCDate() - 1);
    return {
      date: yesterday.toISOString().split("T")[0].replace(/-/g, ""),
      hour: CONFIG.modelRuns.hours[CONFIG.modelRuns.hours.length - 1],
    };
  }

  return {
    date: now.toISOString().split("T")[0].replace(/-/g, ""),
    hour: availableRun.hour,
  };
}

// Parse NOMADS ASCII response
function parseModelData(data) {
  const lines = data.trim().split("\n");
  const variables = {};
  let currentVar = null;

  for (const line of lines) {
    const trimmedLine = line.trim();
    if (!trimmedLine) continue;

    // Check for variable header
    if (trimmedLine.includes(",") && !trimmedLine.includes("[0]")) {
      currentVar = trimmedLine.split(",")[0].trim();
      variables[currentVar] = [];
      continue;
    }

    // Parse data line
    const match = trimmedLine.match(/\[(\d+)\]\[0\],\s*([\d.-]+)/);
    if (match && currentVar) {
      const [_, index, value] = match;
      variables[currentVar][parseInt(index)] = parseFloat(value);
    }
  }

  return variables;
}

// Get forecast for point
async function getPointForecast(lat, lon) {
  try {
    // Get model and grid location
    const model = findModelForLocation(lat, lon);
    const { latIdx, lonIdx } = getGridLocation(lat, lon, model);
    const modelRun = getAvailableModelRun();

    // All available variables
    const variables = [
      "htsgwsfc", // Combined wave height
      "perpwsfc", // Primary wave period
      "dirpwsfc", // Primary wave direction
      "swdir_1", // Primary swell direction
      "swdir_2", // Secondary swell direction
      "swdir_3", // Tertiary swell direction
      "swell_1", // Primary swell height
      "swell_2", // Secondary swell height
      "swell_3", // Tertiary swell height
      "swper_1", // Primary swell period
      "swper_2", // Secondary swell period
      "swper_3", // Tertiary swell period
      "wvdirsfc", // Wind wave direction
      "wvhgtsfc", // Wind wave height
      "wvpersfc", // Wind wave period
      "windsfc", // Wind speed
      "wdirsfc", // Wind direction
      "ugrdsfc", // Wind U component
      "vgrdsfc", // Wind V component
    ];

    // Build URL
    const params = variables
      .map(
        (v) =>
          `${v}${encodeURIComponent(
            `[0:${
              CONFIG.forecast.days * CONFIG.forecast.periodsPerDay - 1
            }][${latIdx}][${lonIdx}]`
          )}`
      )
      .join(",");

    const url = `${CONFIG.baseUrl}/${modelRun.date}/gfswave.${model.name}_${modelRun.hour}z.ascii?${params}`;

    // Fetch and parse data
    const response = await axios.get(url, {
      timeout: CONFIG.request.timeout,
      httpsAgent: agent,
    });

    const parsedData = parseModelData(response.data);
    const periods = [];

    // Group data by forecast period
    for (
      let i = 0;
      i < CONFIG.forecast.days * CONFIG.forecast.periodsPerDay;
      i++
    ) {
      if (parsedData.htsgwsfc?.[i] === undefined) continue;

      const periodData = {
        waves: {
          height: parsedData.htsgwsfc[i],
          period: parsedData.perpwsfc[i],
          direction: parsedData.dirpwsfc[i],
          windWave: parsedData.wvhgtsfc[i]
            ? {
                height: parsedData.wvhgtsfc[i],
                period: parsedData.wvpersfc[i],
                direction: parsedData.wvdirsfc[i],
              }
            : null,
          swells:
            parsedData.swell_1[i] ||
            parsedData.swell_2[i] ||
            parsedData.swell_3[i]
              ? [
                  parsedData.swell_1[i]
                    ? {
                        height: parsedData.swell_1[i],
                        period: parsedData.swper_1[i],
                        direction: parsedData.swdir_1[i],
                      }
                    : null,
                  parsedData.swell_2[i]
                    ? {
                        height: parsedData.swell_2[i],
                        period: parsedData.swper_2[i],
                        direction: parsedData.swdir_2[i],
                      }
                    : null,
                  parsedData.swell_3[i]
                    ? {
                        height: parsedData.swell_3[i],
                        period: parsedData.swper_3[i],
                        direction: parsedData.swdir_3[i],
                      }
                    : null,
                ].filter(Boolean)
              : null,
        },
        wind: {
          speed: parsedData.windsfc[i],
          direction: parsedData.wdirsfc[i],
          u: parsedData.ugrdsfc[i],
          v: parsedData.vgrdsfc[i],
        },
      };

      const periodIndex = Math.floor(i / CONFIG.forecast.periodsPerDay);
      if (!periods[periodIndex]) {
        periods[periodIndex] = {
          date: new Date(
            modelRun.date.replace(/(\d{4})(\d{2})(\d{2})/, "$1-$2-$3")
          )
            .toISOString()
            .split("T")[0],
          periods: [],
        };
      }
      periods[periodIndex].periods.push(periodData);
    }

    return {
      days: periods,
      metadata: {
        model: model.id,
        generated: new Date().toISOString(),
        location: { latitude: lat, longitude: lon },
      },
    };
  } catch (error) {
    logger.error(`Forecast error for ${lat}°N ${lon}°W: ${error.message}`);
    throw error;
  }
}

module.exports = {
  getPointForecast,
  CONFIG,
};
