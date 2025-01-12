const { 
    formatWaveHeight,
    formatWindSpeed,
    formatDirection,
    formatPeriod
} = require('../utils/formatters');

/**
 * Wave Model Configuration
 * Contains all configuration for NOAA wave models including grid specifications,
 * variable definitions, and operational parameters.
 */

const CONFIG = {
    baseUrl: 'https://nomads.ncep.noaa.gov/dods/wave/gfswave',
    models: {
        pacific: {
            name: 'wcoast.0p16',
            grid: {
                lat: { 
                    size: 151,
                    start: 25.00000000000,
                    end: 50.00005000000,
                    resolution: 0.166667
                },
                lon: { 
                    size: 241,
                    start: 210.00000000000,
                    end: 250.00008000000,
                    resolution: 0.166667
                }
            },
            bounds: { min: -150, max: -110 }  // West Coast (converted from 210-250°E)
        },
        atlantic: {
            name: 'atlocn.0p16',
            grid: {
                lat: { 
                    size: 331,
                    start: 0.00000000000,
                    end: 55.00011000000,
                    resolution: 0.166667
                },
                lon: { 
                    size: 301,
                    start: 260.00000000000,
                    end: 310.00010000000,
                    resolution: 0.166667
                }
            },
            bounds: { min: -100, max: -50 }  // Atlantic Ocean
        },
        gulf: {
            name: 'gulfmex.0p16',
            grid: {
                lat: { 
                    size: 151,
                    start: 15.00000000000,
                    end: 40.00011000000,
                    resolution: 0.166667
                },
                lon: { 
                    size: 181,
                    start: 260.00000000000,
                    end: 290.00010000000,
                    resolution: 0.166667
                }
            },
            bounds: { min: -100, max: -70 }  // Gulf of Mexico
        }
    },
    variables: {
        // Combined waves
        waveHeight: { 
            key: 'htsgwsfc', 
            unit: 'ft', 
            convert: formatWaveHeight,
            description: 'surface significant height of combined wind waves and swell'
        },
        wavePeriod: { 
            key: 'perpwsfc', 
            unit: 'seconds', 
            convert: formatPeriod,
            description: 'surface primary wave mean period'
        },
        waveDirection: { 
            key: 'dirpwsfc', 
            unit: 'degrees', 
            convert: formatDirection,
            description: 'surface primary wave direction'
        },
        // Wind waves
        windWaveHeight: {
            key: 'wvhgtsfc',
            unit: 'ft',
            convert: formatWaveHeight,
            description: 'surface significant height of wind waves'
        },
        windWavePeriod: {
            key: 'wvpersfc',
            unit: 'seconds',
            convert: formatPeriod,
            description: 'surface mean period of wind waves'
        },
        windWaveDirection: {
            key: 'wvdirsfc',
            unit: 'degrees',
            convert: formatDirection,
            description: 'surface direction of wind waves'
        },
        // Swell components
        swell1Height: {
            key: 'swell_1',
            unit: 'ft',
            convert: formatWaveHeight,
            description: '1st swell wave height'
        },
        swell1Period: {
            key: 'swper_1',
            unit: 'seconds',
            convert: formatPeriod,
            description: '1st swell wave period'
        },
        swell1Direction: {
            key: 'swdir_1',
            unit: 'degrees',
            convert: formatDirection,
            description: '1st swell wave direction'
        },
        swell2Height: {
            key: 'swell_2',
            unit: 'ft',
            convert: formatWaveHeight,
            description: '2nd swell wave height'
        },
        swell2Period: {
            key: 'swper_2',
            unit: 'seconds',
            convert: formatPeriod,
            description: '2nd swell wave period'
        },
        swell2Direction: {
            key: 'swdir_2',
            unit: 'degrees',
            convert: formatDirection,
            description: '2nd swell wave direction'
        },
        swell3Height: {
            key: 'swell_3',
            unit: 'ft',
            convert: formatWaveHeight,
            description: '3rd swell wave height'
        },
        swell3Period: {
            key: 'swper_3',
            unit: 'seconds',
            convert: formatPeriod,
            description: '3rd swell wave period'
        },
        swell3Direction: {
            key: 'swdir_3',
            unit: 'degrees',
            convert: formatDirection,
            description: '3rd swell wave direction'
        },
        // Wind components
        windSpeed: { 
            key: 'windsfc', 
            unit: 'mph', 
            convert: formatWindSpeed,
            description: 'surface wind speed'
        },
        windDirection: { 
            key: 'wdirsfc', 
            unit: 'degrees', 
            convert: formatDirection,
            description: 'surface wind direction'
        },
        windU: {
            key: 'ugrdsfc',
            unit: 'mph',
            convert: formatWindSpeed,
            description: 'surface u-component of wind'
        },
        windV: {
            key: 'vgrdsfc',
            unit: 'mph',
            convert: formatWindSpeed,
            description: 'surface v-component of wind'
        }
    },
    modelRuns: {
        hours: ['00', '06', '12', '18'],
        availableAfter: {
            '00': 5,  // Available ~05:12 UTC
            '06': 5,  // Available ~11:09 UTC
            '12': 5,  // Available ~17:00 UTC
            '18': 5   // Available ~23:00 UTC
        }
    },
    forecast: {
        days: 7,
        periodsPerDay: 8,
        periodHours: 3
    },
    cache: {
        hours: 6  // Maximum cache duration
    },
    request: {
        timeout: 60000,
        maxRetries: 3,
        retryDelay: 2000
    }
};

module.exports = CONFIG; 