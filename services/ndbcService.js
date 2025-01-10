const fs = require('fs').promises;
const path = require('path');
const axios = require('axios');
const { logger } = require('../utils/logger');
const { getOrSet } = require('../utils/cache');
const { 
    formatWaveHeight,
    formatWindSpeed,
    formatTemperature,
    formatPressure,
    formatDirection,
    formatPeriod,
    formatTimestamp
} = require('../utils/formatters');

const NDBC_BASE_URL = 'https://www.ndbc.noaa.gov/data/realtime2';
const SPECTRAL_URL = 'https://www.ndbc.noaa.gov/data/realtime2';

// NDBC updates every 30 minutes at :26 and :56 past the hour
const NDBC_UPDATE_MINUTES = [26, 56];
const REQUEST_TIMEOUT = 10000; // 10 seconds
const TREND_HOURS = 4; // Hours to analyze for trends

// Calculate TTL to next NDBC update
const getTimeToNextUpdate = () => {
    const now = new Date();
    const currentMinute = now.getMinutes();
    const currentSecond = now.getSeconds();
    
    // Find next update minute
    const nextUpdateMinute = NDBC_UPDATE_MINUTES.find(min => min > currentMinute) || NDBC_UPDATE_MINUTES[0];
    
    // Calculate seconds until next update
    let secondsToNextUpdate;
    if (nextUpdateMinute > currentMinute) {
        secondsToNextUpdate = ((nextUpdateMinute - currentMinute) * 60) - currentSecond;
    } else {
        // Next update is in the next hour
        secondsToNextUpdate = ((60 - currentMinute + nextUpdateMinute) * 60) - currentSecond;
    }
    
    // Add 60 seconds buffer to ensure data is available
    return secondsToNextUpdate + 60;
};

// Beaufort Scale Wind Categories
const BEAUFORT_SCALE = [
    { speed: 1, description: 'Calm', seaCondition: 'Sea like a mirror' },
    { speed: 3, description: 'Light Air', seaCondition: 'Ripples without crests' },
    { speed: 7, description: 'Light Breeze', seaCondition: 'Small wavelets' },
    { speed: 12, description: 'Gentle Breeze', seaCondition: 'Large wavelets' },
    { speed: 18, description: 'Moderate Breeze', seaCondition: 'Small waves' },
    { speed: 24, description: 'Fresh Breeze', seaCondition: 'Moderate waves' },
    { speed: 31, description: 'Strong Breeze', seaCondition: 'Large waves' },
    { speed: 38, description: 'Near Gale', seaCondition: 'Sea heaps up' },
    { speed: 46, description: 'Gale', seaCondition: 'Moderately high waves' },
    { speed: 54, description: 'Strong Gale', seaCondition: 'High waves' },
    { speed: 63, description: 'Storm', seaCondition: 'Very high waves' },
    { speed: 72, description: 'Violent Storm', seaCondition: 'Exceptionally high waves' },
    { speed: 83, description: 'Hurricane', seaCondition: 'Air filled with foam and spray' }
];

// Get Beaufort scale description
const getBeaufortDescription = (windSpeed) => {
    const category = BEAUFORT_SCALE.find((cat, index, arr) => 
        windSpeed <= cat.speed || index === arr.length - 1
    );
    return category;
};

// Column indices for NDBC data
const COLUMNS = {
    YEAR: 0,
    MONTH: 1,
    DAY: 2,
    HOUR: 3,
    MINUTE: 4,
    WIND_DIR: 5,    // WDIR: Wind direction (degrees clockwise from true N)
    WIND_SPEED: 6,  // WSPD: Wind speed (m/s)
    WIND_GUST: 7,   // GST: Wind gust speed (m/s)
    WAVE_HEIGHT: 8, // WVHT: Significant wave height (meters)
    DOM_PERIOD: 9,  // DPD: Dominant wave period (seconds)
    AVG_PERIOD: 10, // APD: Average wave period (seconds)
    WAVE_DIR: 11,   // MWD: Wave direction (degrees clockwise from true N)
    PRESSURE: 12,   // PRES: Sea level pressure (hPa)
    AIR_TEMP: 13,   // ATMP: Air temperature (°C)
    WATER_TEMP: 14, // WTMP: Sea surface temperature (°C)
    DEW_POINT: 15   // DEWP: Dewpoint temperature (°C)
};

// Add spectral data columns
const SPECTRAL_COLUMNS = {
    YEAR: 0,
    MONTH: 1,
    DAY: 2,
    HOUR: 3,
    MINUTE: 4,
    WVHT: 5,    // Total wave height
    SwH: 6,     // Swell height
    SwP: 7,     // Swell period
    WWH: 8,     // Wind wave height
    WWP: 9,     // Wind wave period
    SwD: 10,    // Swell direction
    WWD: 11,    // Wind wave direction
    STEEPNESS: 12,
    APD: 13,    // Average wave period
    MWD: 14     // Mean wave direction
};

class NDBCService {
    constructor() {
        this.stations = [];
        this.loadStations().catch(err => {
            logger.error('Failed to load stations:', err);
            process.exit(1);
        });
    }

    async loadStations() {
        try {
            const stationsPath = path.join(__dirname, '../data/ndbc-stations.geojson');
            const data = await fs.readFile(stationsPath, 'utf8');
            const geojson = JSON.parse(data);
            this.stations = geojson.features.map(feature => ({
                id: feature.properties.id,
                name: feature.properties.name,
                location: {
                    type: feature.geometry.type,
                    coordinates: feature.geometry.coordinates
                },
                type: feature.properties.type,
                hasRealTimeData: feature.properties.hasRealTimeData
            }));
            logger.info(`Loaded ${this.stations.length} NDBC stations`);
        } catch (error) {
            logger.error('Error loading stations:', error.message);
            throw error;
        }
    }

    async getStationById(stationId) {
        if (!this.stations.length) {
            await this.loadStations();
        }
        return this.stations.find(s => s.id === stationId);
    }

    parseValue(value, type) {
        if (!value || value === 'MM') return null;
        const num = parseFloat(value);
        if (isNaN(num)) return null;
        
        switch(type) {
            case 'WVHT': return formatWaveHeight(num);
            case 'WSPD':
            case 'GST': return formatWindSpeed(num);
            case 'DPD':
            case 'APD': return formatPeriod(num);
            case 'MWD':
            case 'WDIR': return formatDirection(num);
            case 'WTMP':
            case 'ATMP':
            case 'DEWP': return formatTemperature(num);
            case 'PRES': return formatPressure(num);
            default: return num;
        }
    }

    analyzeTrends(observations) {
        const periods = observations.slice(0, 8); // Last 4 hours (30-min intervals)
        if (periods.length < 2) return null;

        const first = periods[periods.length - 1];
        const last = periods[0];
        
        // Find most recent valid wave data
        const lastValidWaveData = periods.find(p => p.waves.height !== null);
        const firstValidWaveData = [...periods].reverse().find(p => p.waves.height !== null);

        // Calculate changes only if we have valid data points
        const waveHeightChange = lastValidWaveData && firstValidWaveData ? 
            lastValidWaveData.waves.height - firstValidWaveData.waves.height : null;
        const periodChange = lastValidWaveData && firstValidWaveData ? 
            lastValidWaveData.waves.dominantPeriod - firstValidWaveData.waves.dominantPeriod : null;
        
        const windSpeedChange = last.wind.speed - first.wind.speed;
        const windDirChange = ((last.wind.direction - first.wind.direction + 540) % 360) - 180;

        // Get current Beaufort conditions
        const beaufort = getBeaufortDescription(last.wind.speed);

        // Build wave trend description
        let waveTrendDesc = '';
        if (lastValidWaveData) {
            const waveTrend = !waveHeightChange ? 'steady' :
                Math.abs(waveHeightChange) < 0.5 ? 'steady' :
                waveHeightChange > 0 ? 'building' : 'dropping';

            const periodTrend = !periodChange ? 'steady' :
                Math.abs(periodChange) < 1 ? 'steady' :
                periodChange > 0 ? 'lengthening' : 'shortening';

            waveTrendDesc = `Waves ${waveTrend} at ${lastValidWaveData.waves.height}ft` +
                (waveHeightChange ? ` (${waveHeightChange > 0 ? '+' : ''}${waveHeightChange.toFixed(1)}ft)` : '') +
                (lastValidWaveData.waves.dominantPeriod ? 
                    ` with ${periodTrend} ${lastValidWaveData.waves.dominantPeriod}s period` : '');
        } else {
            waveTrendDesc = 'Wave data temporarily unavailable';
        }

        // Determine wind trend
        const windTrend = Math.abs(windSpeedChange) < 2 ? 'steady' :
            windSpeedChange > 0 ? 'increasing' : 'decreasing';

        // Build complete summary
        const summary = `${waveTrendDesc}. ${beaufort.description} winds ${windTrend} at ${last.wind.speed}mph` +
            (beaufort.seaCondition ? ` (${beaufort.seaCondition})` : '');

        return {
            summary,
            waveHeight: lastValidWaveData ? {
                trend: !waveHeightChange ? 'steady' :
                    Math.abs(waveHeightChange) < 0.5 ? 'steady' :
                    waveHeightChange > 0 ? 'building' : 'dropping',
                change: waveHeightChange,
                current: lastValidWaveData.waves.height,
                lastValidReading: lastValidWaveData.time
            } : null,
            wavePeriod: lastValidWaveData?.waves.dominantPeriod ? {
                trend: !periodChange ? 'steady' :
                    Math.abs(periodChange) < 1 ? 'steady' :
                    periodChange > 0 ? 'lengthening' : 'shortening',
                change: periodChange,
                current: lastValidWaveData.waves.dominantPeriod,
                lastValidReading: lastValidWaveData.time
            } : null,
            wind: {
                trend: windTrend,
                change: windSpeedChange,
                current: last.wind.speed,
                beaufort: beaufort,
                gustFactor: last.wind.gust ? (last.wind.gust - last.wind.speed).toFixed(1) : null
            },
            timeSpan: {
                start: first.time,
                end: last.time,
                lastValidWaveReading: lastValidWaveData?.time || null
            }
        };
    }

    parseDataLine(values) {
        return {
            time: formatTimestamp(new Date(Date.UTC(
                parseInt(values[COLUMNS.YEAR]),
                parseInt(values[COLUMNS.MONTH]) - 1,
                parseInt(values[COLUMNS.DAY]),
                parseInt(values[COLUMNS.HOUR]),
                parseInt(values[COLUMNS.MINUTE])
            ))),
            wind: {
                direction: this.parseValue(values[COLUMNS.WIND_DIR], 'WDIR'),
                speed: this.parseValue(values[COLUMNS.WIND_SPEED], 'WSPD'),
                gust: this.parseValue(values[COLUMNS.WIND_GUST], 'GST')
            },
            waves: {
                height: this.parseValue(values[COLUMNS.WAVE_HEIGHT], 'WVHT'),
                dominantPeriod: this.parseValue(values[COLUMNS.DOM_PERIOD], 'DPD'),
                averagePeriod: this.parseValue(values[COLUMNS.AVG_PERIOD], 'APD'),
                direction: this.parseValue(values[COLUMNS.WAVE_DIR], 'MWD')
            },
            conditions: {
                pressure: this.parseValue(values[COLUMNS.PRESSURE], 'PRES'),
                airTemp: this.parseValue(values[COLUMNS.AIR_TEMP], 'ATMP'),
                waterTemp: this.parseValue(values[COLUMNS.WATER_TEMP], 'WTMP'),
                dewPoint: this.parseValue(values[COLUMNS.DEW_POINT], 'DEWP')
            }
        };
    }

    async fetchSpectralData(buoyId) {
        try {
            const url = `${SPECTRAL_URL}/${buoyId}.spec`;
            logger.info(`Fetching spectral data from: ${url}`);
            
            const response = await axios.get(url, { timeout: REQUEST_TIMEOUT });
            const lines = response.data.trim().split('\n');
            logger.debug(`Received ${lines.length} lines of spectral data`);
            
            // Get first data line (most recent)
            const dataLines = lines.filter(line => !line.startsWith('#'));
            if (dataLines.length === 0) {
                logger.warn(`No spectral data lines found for buoy ${buoyId}`);
                return null;
            }

            const values = dataLines[0].trim().split(/\s+/);
            if (values.length < 15) {
                logger.warn(`Invalid spectral data format for buoy ${buoyId}, got ${values.length} columns, expected 15`);
                return null;
            }

            const spectralData = {
                time: new Date(Date.UTC(
                    parseInt(values[SPECTRAL_COLUMNS.YEAR]),
                    parseInt(values[SPECTRAL_COLUMNS.MONTH]) - 1,
                    parseInt(values[SPECTRAL_COLUMNS.DAY]),
                    parseInt(values[SPECTRAL_COLUMNS.HOUR]),
                    parseInt(values[SPECTRAL_COLUMNS.MINUTE])
                )).toISOString(),
                waves: {
                    height: this.parseValue(values[SPECTRAL_COLUMNS.WVHT], 'WVHT'),
                    swell: {
                        height: this.parseValue(values[SPECTRAL_COLUMNS.SwH], 'WVHT'),
                        period: this.parseValue(values[SPECTRAL_COLUMNS.SwP], 'SwP'),
                        direction: values[SPECTRAL_COLUMNS.SwD] === 'MM' ? null : values[SPECTRAL_COLUMNS.SwD]
                    },
                    windWave: {
                        height: this.parseValue(values[SPECTRAL_COLUMNS.WWH], 'WVHT'),
                        period: this.parseValue(values[SPECTRAL_COLUMNS.WWP], 'WWP'),
                        direction: values[SPECTRAL_COLUMNS.WWD] === 'MM' ? null : values[SPECTRAL_COLUMNS.WWD]
                    },
                    steepness: values[SPECTRAL_COLUMNS.STEEPNESS] === 'MM' ? null : values[SPECTRAL_COLUMNS.STEEPNESS]
                }
            };
            
            logger.debug('Parsed spectral data:', spectralData);
            return spectralData;
        } catch (error) {
            if (error.response?.status === 404) {
                logger.info(`No spectral data available for buoy ${buoyId}`);
            } else {
                logger.warn(`Error fetching spectral data for buoy ${buoyId}:`, error.message);
            }
            return null;
        }
    }

    createMarinerSummary(metData, spectralData) {
        if (!metData) return 'No current conditions available';

        let summary = [];

        // Add wave information if available
        if (spectralData?.waves) {
            const { waves } = spectralData;
            const hasSwell = waves.swell.height > 0.5; // More than 0.5m swell
            const hasWindWaves = waves.windWave.height > 0.5;

            if (hasSwell && hasWindWaves) {
                summary.push(
                    `Mixed conditions with ${waves.windWave.height.toFixed(1)}ft wind waves ` +
                    `(${waves.windWave.period}s) from the ${waves.windWave.direction} and ` +
                    `${waves.swell.height.toFixed(1)}ft swell (${waves.swell.period}s) from the ${waves.swell.direction}`
                );
            } else if (hasSwell) {
                summary.push(
                    `Clean ${waves.swell.height.toFixed(1)}ft swell from the ${waves.swell.direction} ` +
                    `at ${waves.swell.period}s`
                );
            } else if (hasWindWaves) {
                summary.push(
                    `${waves.steepness.toLowerCase()} ${waves.windWave.height.toFixed(1)}ft ` +
                    `wind waves from the ${waves.windWave.direction}`
                );
            }
        } else if (metData.waves.height) {
            summary.push(`${metData.waves.height.toFixed(1)}ft waves at ${metData.waves.dominantPeriod}s`);
        }

        // Add wind information
        if (metData.wind.speed) {
            const beaufort = getBeaufortDescription(metData.wind.speed);
            summary.push(
                `${beaufort.description} winds at ${metData.wind.speed}mph from the ${metData.wind.direction}` +
                (metData.wind.gust ? ` gusting to ${metData.wind.gust}mph` : '')
            );
        }

        return summary.join('. ');
    }

    async fetchBuoyData(buoyId) {
        try {
            const cacheKey = `ndbc_buoy_${buoyId}`;
            logger.info(`Fetching buoy data for ${buoyId}`);
            
            const { data: buoyData, fromCache } = await getOrSet(
                cacheKey,
                async () => {
                    // Fetch both meteorological and spectral data
                    logger.info(`Fetching fresh data for buoy ${buoyId}`);
                    const [metData, spectralData] = await Promise.all([
                        this.fetchMetData(buoyId),
                        this.fetchSpectralData(buoyId)
                    ]);

                    if (!metData) {
                        logger.warn(`No meteorological data available for buoy ${buoyId}`);
                        return null;
                    }

                    // Use spectral wave height when available, fallback to met data
                    const waveHeight = spectralData?.waves?.height || metData.waves.height;

                    // Combine the data
                    const combinedData = {
                        time: metData.time,
                        wind: metData.wind,
                        waves: {
                            height: waveHeight,
                            dominantPeriod: metData.waves.dominantPeriod,
                            averagePeriod: metData.waves.averagePeriod,
                            direction: metData.waves.direction,
                            spectral: spectralData?.waves ? {
                                steepness: spectralData.waves.steepness,
                                swell: spectralData.waves.swell,
                                windWave: spectralData.waves.windWave
                            } : null
                        },
                        conditions: metData.conditions,
                        trends: metData.trends,
                        marinerSummary: this.createMarinerSummary(metData, spectralData)
                    };

                    logger.debug('Combined buoy data:', {
                        time: combinedData.time,
                        hasSpectral: !!spectralData?.waves,
                        waveHeight,
                        spectralComponents: spectralData?.waves ? {
                            swell: spectralData.waves.swell.height,
                            windWave: spectralData.waves.windWave.height
                        } : null
                    });

                    return combinedData;
                },
                getTimeToNextUpdate() // Dynamic TTL based on NDBC update schedule
            );

            if (!buoyData) {
                logger.warn(`No data available for buoy ${buoyId}`);
                return null;
            }

            logger.info(`Returning ${fromCache ? 'cached' : 'fresh'} data for buoy ${buoyId}`);
            return buoyData;
        } catch (error) {
            logger.error(`Error fetching buoy data for ${buoyId}:`, error);
            throw error;
        }
    }

    // Rename existing data fetch to be more specific
    async fetchMetData(buoyId) {
        try {
            const url = `${NDBC_BASE_URL}/${buoyId}.txt`;
            const response = await axios.get(url, { timeout: REQUEST_TIMEOUT });
            const lines = response.data.trim().split('\n');
            
            if (lines.length < 3) {
                logger.error(`Invalid response for buoy ${buoyId}: insufficient data`);
                return null;
            }

            const dataLines = lines.filter(line => !line.startsWith('#'));
            if (dataLines.length === 0) {
                logger.error(`No data lines found for buoy ${buoyId}`);
                return null;
            }

            // Parse recent observations
            const recentObservations = dataLines
                .slice(0, 8)
                .map(line => {
                    const values = line.trim().split(/\s+/);
                    return this.parseDataLine(values);
                })
                .filter(data => data.waves.height || data.wind.speed);

            if (recentObservations.length === 0) {
                logger.error(`No valid observations found for buoy ${buoyId}`);
                return null;
            }

            const currentData = recentObservations[0];
            const trends = this.analyzeTrends(recentObservations);

            return {
                ...currentData,
                trends
            };
        } catch (error) {
            logger.error(`Error fetching met data for buoy ${buoyId}:`, error);
            return null;
        }
    }
}

module.exports = new NDBCService(); 