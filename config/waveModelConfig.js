const {
  formatWaveHeight,
  formatWindSpeed,
  formatDirection,
  formatPeriod,
} = require("../utils/formatters");

/**
 * Wave Model Configuration
 * Contains all configuration for NOAA wave models including grid specifications,
 * variable definitions, and operational parameters.
 */

const CONFIG = {
  baseUrl: "https://nomads.ncep.noaa.gov/dods/wave/gfswave",
  models: {
    pacific: {
      name: "wcoast.0p16",
      description: "GFSwave model: US West Coast: 0p16 grid",
      grid: {
        lat: {
          size: 151,
          start: 25.0,
          end: 50.00005,
          resolution: 0.166667,
        },
        lon: {
          size: 241,
          start: 210.0,
          end: 250.00008,
          resolution: 0.166667,
        },
      },
    },
    atlantic: {
      name: "atlocn.0p16",
      description: "GFSwave model: Atlantic Ocean 0p16 grid",
      grid: {
        lat: {
          size: 331,
          start: 0.0,
          end: 55.00011,
          resolution: 0.166667,
        },
        lon: {
          size: 301,
          start: 260.0,
          end: 310.0001,
          resolution: 0.166667,
        },
      },
    },
    gulf: {
      name: "gulfmex.0p16",
      description: "GFSwave model: Gulf of Mexico 0p16 grid",
      grid: {
        lat: {
          size: 151,
          start: 15.0,
          end: 40.00011,
          resolution: 0.166667,
        },
        lon: {
          size: 181,
          start: 260.0,
          end: 290.0001,
          resolution: 0.166667,
        },
      },
    },
  },
  variables: {
    // Combined waves
    waveHeight: {
      key: "htsgwsfc",
      unit: "m",
      convert: formatWaveHeight,
      description:
        "surface significant height of combined wind waves and swell",
    },
    wavePeriod: {
      key: "perpwsfc",
      unit: "s",
      convert: formatPeriod,
      description: "surface primary wave mean period",
    },
    waveDirection: {
      key: "dirpwsfc",
      unit: "deg",
      convert: formatDirection,
      description: "surface primary wave direction",
    },
    // Wind waves
    windWaveHeight: {
      key: "wvhgtsfc",
      unit: "m",
      convert: formatWaveHeight,
      description: "surface significant height of wind waves",
    },
    windWavePeriod: {
      key: "wvpersfc",
      unit: "s",
      convert: formatPeriod,
      description: "surface mean period of wind waves",
    },
    windWaveDirection: {
      key: "wvdirsfc",
      unit: "deg",
      convert: formatDirection,
      description: "surface direction of wind waves",
    },
    // Swell components
    swell1Height: {
      key: "swell_1",
      unit: "m",
      convert: formatWaveHeight,
      description: "1st swell wave height",
    },
    swell1Period: {
      key: "swper_1",
      unit: "s",
      convert: formatPeriod,
      description: "1st swell wave period",
    },
    swell1Direction: {
      key: "swdir_1",
      unit: "deg",
      convert: formatDirection,
      description: "1st swell wave direction",
    },
    swell2Height: {
      key: "swell_2",
      unit: "m",
      convert: formatWaveHeight,
      description: "2nd swell wave height",
    },
    swell2Period: {
      key: "swper_2",
      unit: "s",
      convert: formatPeriod,
      description: "2nd swell wave period",
    },
    swell2Direction: {
      key: "swdir_2",
      unit: "deg",
      convert: formatDirection,
      description: "2nd swell wave direction",
    },
    swell3Height: {
      key: "swell_3",
      unit: "m",
      convert: formatWaveHeight,
      description: "3rd swell wave height",
    },
    swell3Period: {
      key: "swper_3",
      unit: "s",
      convert: formatPeriod,
      description: "3rd swell wave period",
    },
    swell3Direction: {
      key: "swdir_3",
      unit: "deg",
      convert: formatDirection,
      description: "3rd swell wave direction",
    },
    // Wind components
    windSpeed: {
      key: "windsfc",
      unit: "m/s",
      convert: formatWindSpeed,
      description: "surface wind speed",
    },
    windDirection: {
      key: "wdirsfc",
      unit: "deg",
      convert: formatDirection,
      description: "surface wind direction (from which blowing)",
    },
    windU: {
      key: "ugrdsfc",
      unit: "m/s",
      convert: formatWindSpeed,
      description: "surface u-component of wind",
    },
    windV: {
      key: "vgrdsfc",
      unit: "m/s",
      convert: formatWindSpeed,
      description: "surface v-component of wind",
    },
  },
  modelRuns: {
    hours: ["00", "06", "12", "18"],
    availableAfter: {
      "00": 5,
      "06": 5,
      12: 5,
      18: 5,
    },
  },
  forecast: {
    days: 7,
    periodsPerDay: 8,
    periodHours: 3,
  },
  cache: {
    hours: 6,
  },
  request: {
    timeout: 60000,
    maxRetries: 3,
    retryDelay: 2000,
  },
};

module.exports = CONFIG;
