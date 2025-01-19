const { logger } = require("../utils/logger");
const waveModelService = require("./waveModelService");
const Handlebars = require("handlebars");

// Constants for condition classifications
const CONDITIONS = {
  WAVE_HEIGHT: {
    FLAT: { max: 1.0, description: "flat" },
    SMALL: { max: 2.0, description: "small" },
    MILD: { max: 3.0, description: "mild" },
    MODERATE: { max: 4.0, description: "moderate" },
    CONSIDERABLE: { max: 6.0, description: "considerable" },
    LARGE: { max: 8.0, description: "large" },
    HUGE: { max: Infinity, description: "huge" },
  },
  WIND: {
    LIGHT: { max: 5, description: "light" },
    GENTLE: { max: 10, description: "gentle" },
    MODERATE: { max: 15, description: "moderate" },
    FRESH: { max: 20, description: "fresh" },
    STRONG: { max: 25, description: "strong" },
    VERY_STRONG: { max: Infinity, description: "very strong" },
  },
  COAST: {
    EAST: {
      favorable: ["W", "NW", "SW"],
      unfavorable: ["E", "NE", "SE"],
      neutral: ["N", "S"],
    },
    WEST: {
      favorable: ["E", "SE", "NE"],
      unfavorable: ["W", "SW", "NW"],
      neutral: ["N", "S"],
    },
  },
};

// Register Handlebars helpers
Handlebars.registerHelper("round", function (value) {
  return Math.round(value);
});

Handlebars.registerHelper("degreesToDirection", function (degrees) {
  return getWindDirectionText(degrees);
});

// Templates for various conditions
const templates = {
  waves: {
    flat: [
      "{{round height}}ft ripples",
      "minimal {{round height}}ft waves",
      "flat {{round height}}ft conditions",
    ],
    small: [
      "small {{round height}}ft waves",
      "minor {{round height}}ft swell",
      "gentle {{round height}}ft surf",
    ],
    normal: [
      "{{round height}}ft waves",
      "{{round height}}ft swell",
      "surf running {{round height}}ft",
    ],
  },
  period: {
    short: "at {{period}}s intervals",
    medium: "{{period}}s apart",
    long: "with clean {{period}}s spacing",
  },
  trend: {
    steady: ["holding steady", "maintaining size", "staying consistent"],
    building: ["slowly building", "gradually increasing", "trending up"],
    dropping: ["gradually dropping", "slowly decreasing", "easing down"],
  },
  wind: {
    base: "{{description}} {{round speed}}mph {{degreesToDirection direction}}",
    withGust:
      "{{description}} {{round speed}}mph {{degreesToDirection direction}} gusting {{round gust}}mph",
  },
};

// Compile templates
const compiledTemplates = {
  waves: {
    flat: templates.waves.flat.map((t) => Handlebars.compile(t)),
    small: templates.waves.small.map((t) => Handlebars.compile(t)),
    normal: templates.waves.normal.map((t) => Handlebars.compile(t)),
  },
  period: {
    short: Handlebars.compile(templates.period.short),
    medium: Handlebars.compile(templates.period.medium),
    long: Handlebars.compile(templates.period.long),
  },
  trend: {
    steady: templates.trend.steady.map((t) => Handlebars.compile(t)),
    building: templates.trend.building.map((t) => Handlebars.compile(t)),
    dropping: templates.trend.dropping.map((t) => Handlebars.compile(t)),
  },
  wind: {
    base: Handlebars.compile(templates.wind.base),
    withGust: Handlebars.compile(templates.wind.withGust),
  },
};

/**
 * Get random template from array
 */
const getRandomTemplate = (templates) => {
  return templates[Math.floor(Math.random() * templates.length)];
};

/**
 * Format wave description using templates
 */
const formatWaveDescription = (height, period = null, trend = "steady") => {
  // Select appropriate wave template set
  let waveTemplates = compiledTemplates.waves.normal;
  if (height <= 1) waveTemplates = compiledTemplates.waves.flat;
  else if (height <= 2) waveTemplates = compiledTemplates.waves.small;

  // Generate wave description
  let description = getRandomTemplate(waveTemplates)({ height });

  // Add period if available
  if (period) {
    let periodTemplate = compiledTemplates.period.medium;
    if (period <= 6) periodTemplate = compiledTemplates.period.short;
    else if (period >= 12) periodTemplate = compiledTemplates.period.long;

    description += " " + periodTemplate({ period });
  }

  // Add trend
  const trendTemplates =
    trend === "steady"
      ? compiledTemplates.trend.steady
      : trend === "increasing"
      ? compiledTemplates.trend.building
      : compiledTemplates.trend.dropping;

  description += ", " + getRandomTemplate(trendTemplates)();

  return description;
};

/**
 * Format wind description using templates
 */
const formatWindDescription = (speed, direction, gust = null) => {
  const context = {
    description: getWindDescription(speed),
    speed,
    direction,
  };

  if (gust && gust > speed) {
    context.gust = gust;
    return compiledTemplates.wind.withGust(context);
  }

  return compiledTemplates.wind.base(context);
};

/**
 * Get wave height description based on height in feet
 */
const getWaveDescription = (heightInFeet) => {
  const category = Object.values(CONDITIONS.WAVE_HEIGHT).find(
    (cat) => heightInFeet <= cat.max
  );
  return category.description;
};

/**
 * Get wind description based on speed in mph
 */
const getWindDescription = (speed) => {
  const category = Object.values(CONDITIONS.WIND).find(
    (cat) => speed <= cat.max
  );
  return category.description;
};

/**
 * Convert degrees to cardinal direction
 */
const getWindDirectionText = (degrees) => {
  const directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const index = Math.round(((degrees + 22.5) % 360) / 45);
  return directions[index % 8];
};

/**
 * Calculate wave steepness and quality
 */
const analyzeWaveQuality = (height, period) => {
  if (!height || !period) return null;

  const steepness = height / (period * period);
  let quality;

  if (steepness < 0.004) quality = "clean";
  else if (steepness < 0.007) quality = "fair";
  else if (steepness < 0.01) quality = "choppy";
  else quality = "rough";

  return { steepness, quality };
};

/**
 * Analyze wind impact based on direction and coast
 */
const getWindImpact = (windDirection, windSpeed, location) => {
  const windDir = getWindDirectionText(windDirection);
  const config =
    location.longitude < -100 ? CONDITIONS.COAST.WEST : CONDITIONS.COAST.EAST;

  if (config.unfavorable.includes(windDir)) {
    if (windSpeed > 15) return "poor-choppy";
    if (windSpeed > 10) return "poor";
    return "fair";
  }

  if (config.favorable.includes(windDir)) {
    if (windSpeed > 25) return "fair-strong";
    if (windSpeed > 15) return "good-breezy";
    return "excellent";
  }

  if (windSpeed > 20) return "poor-choppy";
  if (windSpeed > 15) return "fair";
  return "good";
};

/**
 * Generate human-readable summaries for conditions
 */
const generateSummaries = (modelData, location) => {
  if (!modelData?.days?.[0]?.periods?.length) {
    throw new Error("Invalid model data structure");
  }

  try {
    const current = modelData.days[0].periods[0];
    const next12Hours = modelData.days[0].periods.slice(0, 4);

    // Build summary parts based on available data
    const summaryParts = [];

    // Wave summary if available
    if (current.waveHeight) {
      const maxWaveHeight = Math.max(...next12Hours.map((p) => p.waveHeight));
      const waveChange = maxWaveHeight - current.waveHeight;
      const trend =
        Math.abs(waveChange) >= 0.5
          ? waveChange > 0
            ? "increasing"
            : "decreasing"
          : "steady";

      summaryParts.push(
        formatWaveDescription(current.waveHeight, current.wavePeriod, trend)
      );
    }

    // Wind summary if available
    if (current.windSpeed) {
      summaryParts.push(
        formatWindDescription(
          current.windSpeed,
          current.windDirection,
          current.windGust
        )
      );
    }

    const currentSummary = summaryParts.join(", with ");

    // Week summary based on available data
    const peakDay = modelData.days.reduce((peak, day) => {
      if (!day.summary.waveHeight?.max) return peak;
      return !peak || day.summary.waveHeight.max > peak.waveHeight
        ? {
            date: day.date,
            waveHeight: day.summary.waveHeight.max,
            windSpeed: day.summary.windSpeed?.avg,
            windDirection: day.summary.windDirection?.avg,
          }
        : peak;
    }, null);

    let weekSummary = "";
    if (peakDay) {
      const peakDate = new Date(peakDay.date);
      weekSummary =
        `Peaks ${peakDate.toLocaleDateString("en-US", {
          weekday: "long",
        })} at ${peakDay.waveHeight}ft` +
        (peakDay.windSpeed && peakDay.windDirection
          ? ` with ${formatWindDescription(
              peakDay.windSpeed,
              peakDay.windDirection
            )}`
          : "");
    }

    // Analyze current conditions
    let conditions = "unknown";
    if (current.waveHeight && current.wavePeriod) {
      const waveQuality = analyzeWaveQuality(
        current.waveHeight,
        current.wavePeriod
      );
      const windImpact =
        current.windSpeed && current.windDirection
          ? getWindImpact(current.windDirection, current.windSpeed, location)
          : "unknown";

      // Combine wave quality and wind impact
      if (waveQuality && windImpact !== "unknown") {
        if (windImpact.includes("poor")) {
          conditions = windImpact; // Wind is the limiting factor
        } else if (windImpact === "excellent") {
          conditions =
            waveQuality.quality === "clean" ? "excellent" : waveQuality.quality;
        } else if (windImpact === "good" || windImpact === "good-breezy") {
          conditions =
            waveQuality.quality === "rough" ? "fair" : waveQuality.quality;
        } else {
          conditions = waveQuality.quality === "clean" ? "fair" : "poor";
        }
      } else {
        conditions = waveQuality?.quality || "unknown";
      }
    }

    return {
      current: currentSummary || "No current observations available",
      week: weekSummary || "No forecast available",
      conditions,
      windImpact:
        current.windSpeed && current.windDirection
          ? getWindImpact(current.windDirection, current.windSpeed, location)
          : "unknown",
    };
  } catch (error) {
    logger.error("Error generating summaries:", error);
    return {
      current: "Forecast unavailable",
      week: "Forecast unavailable",
      conditions: "unknown",
      windImpact: "unknown",
    };
  }
};

module.exports = {
  generateSummaries,
  getWindImpact,
  getWaveDescription,
  getWindDescription,
  getWindDirectionText,
  formatWindDescription,
  analyzeWaveQuality,
  CONDITIONS,
};
