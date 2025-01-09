const fs = require('fs').promises;
const path = require('path');
const axios = require('axios');
const { logger } = require('../utils/logger');
const { getOrSet, DEFAULT_TTL } = require('../utils/cache');

const NDBC_BASE_URL = 'https://www.ndbc.noaa.gov/data/realtime2';
const CACHE_TTL = 30 * 60; // 30 minutes
const REQUEST_TIMEOUT = 10000; // 10 seconds
const TREND_HOURS = 4; // Hours to analyze for trends

// Conversion helpers
const metersToFeet = meters => meters * 3.28084;
const knotsToMph = knots => knots * 1.15078;
const celsiusToFahrenheit = celsius => (celsius * 9/5) + 32;

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
            case 'WVHT': return parseFloat((metersToFeet(num)).toFixed(1));
            case 'WSPD':
            case 'GST': return parseFloat((knotsToMph(num)).toFixed(1));
            case 'DPD':
            case 'APD':
            case 'MWD':
            case 'WDIR': return Math.round(num);
            case 'WTMP':
            case 'ATMP':
            case 'DEWP': return parseFloat(celsiusToFahrenheit(num).toFixed(1));
            case 'PRES': return parseFloat(num.toFixed(1));
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
            time: new Date(Date.UTC(
                parseInt(values[COLUMNS.YEAR]),
                parseInt(values[COLUMNS.MONTH]) - 1,
                parseInt(values[COLUMNS.DAY]),
                parseInt(values[COLUMNS.HOUR]),
                parseInt(values[COLUMNS.MINUTE])
            )).toISOString(),
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

    async fetchBuoyData(buoyId) {
        try {
            const cacheKey = `buoy_data_${buoyId}`;
            
            const { data: buoyData, fromCache } = await getOrSet(
                cacheKey,
                async () => {
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

                    // Parse recent observations for trend analysis
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

                    const trends = this.analyzeTrends(recentObservations);
                    const currentData = recentObservations[0];

                    return {
                        ...currentData,
                        trends,
                        stationId: buoyId,
                        fetchTime: new Date().toISOString()
                    };
                },
                DEFAULT_TTL
            );

            if (!buoyData) {
                logger.error(`Failed to fetch or process data for buoy ${buoyId}`);
                return null;
            }

            if (!fromCache) {
                logger.info(`Fresh buoy data fetched for ${buoyId}`);
            }

            return buoyData;
        } catch (error) {
            logger.error(`Error fetching buoy data for ${buoyId}:`, error);
            throw error;
        }
    }
}

module.exports = new NDBCService(); 