const axios = require("axios");
const { logger } = require("../utils/logger");
const { getOrSet } = require("../utils/cache");
const CONFIG = require("../config/waveModelConfig");
const https = require("https");

// Create reusable HTTPS agent
const agent = new https.Agent({
  keepAlive: true,
  keepAliveMsecs: 1000,
  timeout: 60000,
  maxSockets: 10,
});

// Model selection
const findModelForLocation = (lat, lon) => {
  // Normalize longitude to 0-360 range for comparison with model grids
  const normalizedLon = lon < 0 ? lon + 360 : lon;

  const model = Object.entries(CONFIG.models).find(([_, m]) => {
    const inLatRange = lat >= m.grid.lat.start && lat <= m.grid.lat.end;
    const inLonRange =
      normalizedLon >= m.grid.lon.start && normalizedLon <= m.grid.lon.end;
    return inLatRange && inLonRange;
  });

  if (!model) {
    const availableRegions = Object.entries(CONFIG.models)
      .map(
        ([id, m]) =>
          `${id} (${m.description}): lat(${m.grid.lat.start}° to ${m.grid.lat.end}°), lon(${m.grid.lon.start}°E to ${m.grid.lon.end}°E)`
      )
      .join("\n");

    logger.error(
      `Location ${lat}°N ${lon}°W (${normalizedLon}°E) is outside all model bounds. Available regions:\n${availableRegions}`
    );
    throw new Error(`Location ${lat}°N ${lon}°W is outside all model bounds`);
  }

  return { id: model[0], ...model[1] };
};

// Grid calculations
const getGridLocation = (lat, lon, model) => {
  // Normalize longitude to 0-360 range
  const normalizedLon = lon < 0 ? lon + 360 : lon;

  // Calculate indices based on grid resolution
  const latIdx = Math.round(
    (lat - model.grid.lat.start) / model.grid.lat.resolution
  );
  const lonIdx = Math.round(
    (normalizedLon - model.grid.lon.start) / model.grid.lon.resolution
  );

  // Validate indices against grid size
  if (latIdx < 0 || latIdx >= model.grid.lat.size) {
    throw new Error(
      `Invalid latitude grid index: ${latIdx} (valid range: 0 to ${
        model.grid.lat.size - 1
      })`
    );
  }
  if (lonIdx < 0 || lonIdx >= model.grid.lon.size) {
    throw new Error(
      `Invalid longitude grid index: ${lonIdx} (valid range: 0 to ${
        model.grid.lon.size - 1
      })`
    );
  }

  return { latIdx, lonIdx };
};

// Get available model run
const getAvailableModelRun = (now = new Date()) => {
  const currentHour = now.getUTCHours();

  // Find most recent available run
  const availableRun = CONFIG.modelRuns.hours
    .map((runHour) => ({
      hour: runHour,
      availableAt: parseInt(runHour) + CONFIG.modelRuns.availableAfter[runHour],
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
};

// Fetch model data
const fetchModelData = async (url, attempt = 1) => {
  try {
    const response = await axios({
      method: "get",
      url,
      httpAgent: agent,
      httpsAgent: agent,
      headers: { Accept: "text/plain" },
      responseType: "text",
      validateStatus: (status) => status === 200,
    });

    if (
      !response.data ||
      response.data.includes("Error") ||
      response.data.includes("</html>")
    ) {
      throw new Error("Invalid response from GDS server");
    }

    return response.data;
  } catch (error) {
    if (attempt >= CONFIG.request.maxRetries) {
      logger.error("Max retries exceeded for GDS request", {
        url,
        error: error.message,
      });
      throw error;
    }

    const delay = Math.min(1000 * Math.pow(2, attempt - 1), 8000);
    await new Promise((resolve) => setTimeout(resolve, delay));
    return fetchModelData(url, attempt + 1);
  }
};

// Validate NOMADS response format
const validateModelData = (data) => {
  if (!data || typeof data !== "string") {
    logger.error("Invalid model data format: empty response");
    return false;
  }

  const lines = data.trim().split("\n");

  // Look for at least one valid data line
  let foundValidData = false;
  for (const line of lines) {
    const trimmedLine = line.trim();
    if (!trimmedLine) continue;

    // Check for valid data line with numeric value
    const match = trimmedLine.match(/\[\d+\]\[\d+\],\s*([-\d.]+)/);
    if (match && !isNaN(parseFloat(match[1]))) {
      foundValidData = true;
      break;
    }
  }

  if (!foundValidData) {
    logger.error("No valid data points found in response");
    return false;
  }

  return true;
};

// Process raw data into forecast periods
const processModelData = (modelRun, lines) => {
  const dateMatch = modelRun.date.match(/(\d{4})(\d{2})(\d{2})/);
  if (!dateMatch) {
    throw new Error("Invalid model run date format");
  }

  const [_, modelYear, modelMonth, modelDay] = dateMatch;
  const baseTime = Date.UTC(
    parseInt(modelYear),
    parseInt(modelMonth) - 1,
    parseInt(modelDay),
    parseInt(modelRun.hour)
  );

  // Initialize data points
  const data = {};
  let currentVar = null;

  // Process each line
  lines.forEach((line) => {
    const trimmedLine = line.trim();
    if (!trimmedLine) return;

    // Check for variable header
    if (trimmedLine.includes(",") && trimmedLine.includes("[")) {
      const varName = trimmedLine.split(",")[0].trim();
      currentVar = Object.entries(CONFIG.variables).find(
        ([_, v]) => v.key === varName
      )?.[1];
      return;
    }

    if (!currentVar) return;

    // Parse data line
    const match = trimmedLine.match(/\[(\d+)\]\[\d+\],\s*([-\d.]+)/);
    if (!match) return;

    const [_, timeIndex, rawValue] = match;
    const value = parseFloat(rawValue);
    if (isNaN(value)) return;

    const time = new Date(
      baseTime +
        parseInt(timeIndex) * CONFIG.forecast.periodHours * 60 * 60 * 1000
    )
      .toISOString()
      .split("T")[0];

    // Initialize period data structure if needed
    data[time] = data[time] || {
      date: time,
      periods: [],
    };

    data[time].periods[timeIndex] = data[time].periods[timeIndex] || {
      time: new Date(
        baseTime +
          parseInt(timeIndex) * CONFIG.forecast.periodHours * 60 * 60 * 1000
      ).toISOString(),
      waves: {},
      wind: {},
      components: { swells: [] },
    };

    // Update the appropriate data field
    if (varName.startsWith("swell")) {
      const [_, num] = varName.match(/swell(\d)(\w+)/);
      const type = varName.endsWith("Height")
        ? "height"
        : varName.endsWith("Period")
        ? "period"
        : "direction";

      data[time].periods[timeIndex].components.swells[num - 1] =
        data[time].periods[timeIndex].components.swells[num - 1] || {};
      data[time].periods[timeIndex].components.swells[num - 1][type] =
        currentVar.convert(value);
    } else if (varName.startsWith("windWave")) {
      const type = varName.endsWith("Height")
        ? "height"
        : varName.endsWith("Period")
        ? "period"
        : "direction";
      data[time].periods[timeIndex].components.windWave =
        data[time].periods[timeIndex].components.windWave || {};
      data[time].periods[timeIndex].components.windWave[type] =
        currentVar.convert(value);
    } else if (varName.startsWith("wave")) {
      const type = varName.endsWith("Height")
        ? "height"
        : varName.endsWith("Period")
        ? "period"
        : "direction";
      data[time].periods[timeIndex].waves[type] = currentVar.convert(value);
    } else if (varName.startsWith("wind")) {
      const type = varName.endsWith("Speed") ? "speed" : "direction";
      data[time].periods[timeIndex].wind[type] = currentVar.convert(value);
    }
  });

  // Filter and sort the processed data
  return Object.values(data)
    .map((day) => ({
      ...day,
      periods: day.periods.filter((p) => p?.waves?.height && p?.waves?.period),
    }))
    .filter((day) => day.periods.length > 0)
    .sort((a, b) => a.date.localeCompare(b.date));
};

async function getPointForecast(lat, lon) {
  if (!lat || !lon || isNaN(lat) || isNaN(lon)) {
    throw new Error("Invalid latitude or longitude");
  }

  const forecastCacheKey = `ww3_forecast_${lat}_${lon}`;

  try {
    const { data: forecast } = await getOrSet(
      forecastCacheKey,
      async () => {
        const model = findModelForLocation(lat, lon);
        const { latIdx, lonIdx } = getGridLocation(lat, lon, model);
        const modelRun = getAvailableModelRun();

        const url =
          `${CONFIG.baseUrl}/${modelRun.date}/gfswave.${model.name}_${modelRun.hour}z.ascii?` +
          Object.values(CONFIG.variables)
            .map(
              (v) =>
                `${v.key}[0:${
                  CONFIG.forecast.days * CONFIG.forecast.periodsPerDay - 1
                }][${latIdx}][${lonIdx}]`
            )
            .join(",");

        const data = await fetchModelData(url);
        if (!validateModelData(data)) {
          throw new Error("Invalid model data format");
        }

        const forecastData = processModelData(
          modelRun,
          data.trim().split("\n")
        );

        return {
          metadata: {
            model: model.id,
            generated: new Date().toISOString(),
            location: { latitude: lat, longitude: lon },
          },
          days: forecastData,
        };
      },
      CONFIG.cache.hours * 60 * 60
    );

    return forecast;
  } catch (error) {
    logger.error(`Forecast error for ${lat}N ${lon}W: ${error.message}`);
    return null;
  }
}

module.exports = {
  getPointForecast,
  CONFIG,
};
