const axios = require('axios');
const { logger } = require('../utils/logger');
const { getOrSet } = require('../utils/cache');
const CONFIG = require('../config/waveModelConfig');

// Pure functions for model selection
const isPointInBounds = (lat, lon, model) => {
    const inLatRange = lat >= model.grid.lat.start && lat <= model.grid.lat.end;
    const inLonRange = lon >= model.bounds.min && lon <= model.bounds.max;
    return inLatRange && inLonRange;
};

const findModelForLocation = (lat, lon, models) => {
    const model = Object.entries(models)
        .find(([_, m]) => isPointInBounds(lat, lon, m));
    
    if (!model) {
        throw new Error('Location is outside all regional model bounds');
    }
    
    return { id: model[0], ...model[1] };
};

// Pure functions for grid calculations
const normalizeGridCoordinate = (value, isLongitude) => 
    isLongitude && value < 0 ? value + 360 : value;

const calculateGridIndex = (value, start, resolution) => 
    Math.round((value - start) / resolution);

const validateGridIndex = (index, size, dimension) => {
    if (isNaN(index) || index < 0 || index >= size) {
        throw new Error(`Invalid ${dimension} grid index: ${index} (max ${size - 1})`);
    }
    return index;
};

// Compose grid location functions
const getGridLocation = (lat, lon, model) => {
    logger.debug(`Calculating grid indices for lat=${lat}, lon=${lon} in ${model.id} model`);
    
    // Normalize coordinates
    const normalizedLon = normalizeGridCoordinate(lon, true);
    logger.debug(`Normalized longitude: ${normalizedLon}`);
    
    // Calculate indices
    const latIdx = calculateGridIndex(lat, model.grid.lat.start, model.grid.lat.resolution);
    const lonIdx = calculateGridIndex(normalizedLon, model.grid.lon.start, model.grid.lon.resolution);
    
    // Validate indices
    validateGridIndex(latIdx, model.grid.lat.size, 'latitude');
    validateGridIndex(lonIdx, model.grid.lon.size, 'longitude');
    
    logger.info(`Valid grid indices calculated: latIdx=${latIdx}, lonIdx=${lonIdx}`);
    return { latIdx, lonIdx };
};

// Error handling utility
const logError = (message, error, level = 'error') => {
    logger[level](`${message}: ${error.message}`, { error });
    return null;
};

// Pure functions for model run selection
const getAvailableModelRun = (now = new Date()) => {
    const hour = now.getUTCHours();
    
    // Find the most recent available run
    const availableRun = CONFIG.modelRuns.hours
        .map(runHour => ({
            hour: runHour,
            availableAt: parseInt(runHour) + CONFIG.modelRuns.availableAfter[runHour]
        }))
        .reverse() // Start with most recent
        .find(run => hour >= run.availableAt);
    
    if (!availableRun) {
        // If no runs are available yet today, use yesterday's last run
        const yesterday = new Date(now);
        yesterday.setUTCDate(yesterday.getUTCDate() - 1);
        return {
            date: formatModelDate(yesterday),
            hour: CONFIG.modelRuns.hours[CONFIG.modelRuns.hours.length - 1]
        };
    }
    
    return {
        date: formatModelDate(now),
        hour: availableRun.hour
    };
};

const formatModelDate = date => 
    date.toISOString().split('T')[0].replace(/-/g, '');

// Pure functions for data processing
const createTimePoint = (baseTime, index) => 
    new Date(baseTime + index * CONFIG.forecast.periodHours * 60 * 60 * 1000).toISOString();

const parseModelLine = line => {
    const match = line.match(/\[\d+\]\[\d+\],\s*([-\d.]+)/);
    if (!match) return null;
    
    const value = parseFloat(match[1]);
    return (!isNaN(value) && value < 9.9e19) ? value : null;
};

const processModelData = (modelRun, lines) => {
    // Calculate base time
    const [year, month, day] = [
        modelRun.date.slice(0, 4),
        modelRun.date.slice(4, 6),
        modelRun.date.slice(6, 8)
    ].map(Number);
    const baseTime = Date.UTC(year, month - 1, day, parseInt(modelRun.hour));
    
    // Initialize data structure
    const timePoints = CONFIG.forecast.days * CONFIG.forecast.periodsPerDay;
    const data = new Array(timePoints).fill().map((_, i) => ({
        time: createTimePoint(baseTime, i)
    }));
    
    // Process each variable
    let currentVar = null;
    let currentTimeIndex = 0;
    
    lines.forEach(line => {
        // Check if line defines a new variable
        const varMatch = Object.entries(CONFIG.variables)
            .find(([_, v]) => line.includes(`${v.key},`));
        
        if (varMatch) {
            currentVar = varMatch[1];
            currentTimeIndex = 0;
            return;
        }
        
        if (!currentVar || currentTimeIndex >= timePoints) return;
        
        const value = parseModelLine(line);
        if (value === null) return;
        
        const varName = Object.entries(CONFIG.variables)
            .find(([_, v]) => v === currentVar)[0];
        
        data[currentTimeIndex][varName] = currentVar.convert(value);
        currentTimeIndex++;
    });
    
    // Filter for complete records
    return data.filter(point => 
        Object.keys(CONFIG.variables)
            .every(key => point[key] && !isNaN(parseFloat(point[key])))
    );
};

const groupForecastByDay = forecast => {
    const grouped = forecast.reduce((acc, period) => {
        const date = period.time.split('T')[0];
        if (!acc[date]) {
            acc[date] = { date, periods: [] };
        }
        acc[date].periods.push(period);
        return acc;
    }, {});
    
    return Object.values(grouped);
};

// API request handling
const checkModelAvailability = async (modelRun) => {
    try {
        // Check the directory listing first
        const response = await axios.get(`${CONFIG.baseUrl}/${modelRun.date}`, {
            timeout: CONFIG.request.timeout,
            headers: { 'Accept-Encoding': 'gzip, deflate' }
        });
        
        // Look for model run in directory listing
        const modelRunExists = response.data.includes(`_${modelRun.hour}z`);
        if (!modelRunExists) {
            logger.warn(`Model run ${modelRun.date}_${modelRun.hour}z not found in directory listing`);
            return false;
        }
        
        return true;
    } catch (error) {
        logger.warn(`Failed to check model availability: ${error.message}`);
        return false;
    }
};

const retryRequest = async (url, attempt = 1) => {
    try {
        return await axios.get(url, { 
            timeout: CONFIG.request.timeout,
            headers: { 'Accept-Encoding': 'gzip, deflate' }
        });
    } catch (error) {
        if (attempt >= CONFIG.request.maxRetries) throw error;
        
        logger.warn(`Attempt ${attempt} failed, retrying in ${CONFIG.request.retryDelay}ms...`);
        await new Promise(resolve => setTimeout(resolve, CONFIG.request.retryDelay));
        return retryRequest(url, attempt + 1);
    }
};

// Main forecast function
async function getPointForecast(lat, lon) {
    if (!lat || !lon || isNaN(lat) || isNaN(lon)) {
        throw new Error('Invalid latitude or longitude');
    }

    const cacheKey = `ww3_forecast_${lat}_${lon}`;
    
    try {
        const { data: forecast } = await getOrSet(
            cacheKey,
            async () => {
                try {
                    const model = findModelForLocation(lat, lon, CONFIG.models);
                    const { latIdx, lonIdx } = getGridLocation(lat, lon, model);
                    const modelRun = getAvailableModelRun();
                    
                    // Check if model run is available
                    const isAvailable = await checkModelAvailability(modelRun);
                    if (!isAvailable) {
                        // Try previous run
                        const prevDate = new Date();
                        prevDate.setUTCHours(prevDate.getUTCHours() - 6);
                        const prevRun = getAvailableModelRun(prevDate);
                        
                        const prevAvailable = await checkModelAvailability(prevRun);
                        if (!prevAvailable) {
                            return logError('No recent model runs available', new Error('Data unavailable'));
                        }
                        
                        logger.info(`Using previous model run ${prevRun.date}_${prevRun.hour}z`);
                        Object.assign(modelRun, prevRun);
                    }

                    const url = `${CONFIG.baseUrl}/${modelRun.date}/gfswave.${model.name}_${modelRun.hour}z.ascii?` +
                        Object.values(CONFIG.variables)
                            .map(v => `${v.key}[0:${CONFIG.forecast.days * CONFIG.forecast.periodsPerDay - 1}][${latIdx}][${lonIdx}]`)
                            .join(',');

                    const response = await retryRequest(url);
                    if (!response.data || response.data.includes('</html>')) {
                        return logError('Model data not available', new Error(`${modelRun.date}_${modelRun.hour}z`));
                    }

                    const validForecast = processModelData(modelRun, response.data.trim().split('\n'));
                    if (!validForecast.length) {
                        return logError('No valid forecast data found', new Error('Empty forecast'));
                    }

                    const groupedForecast = validForecast.reduce((acc, period) => {
                        const date = period.time.split('T')[0];
                        if (!acc[date]) {
                            logger.debug(`Creating new group for date ${date}`);
                            acc[date] = { date, periods: [] };
                        }
                        acc[date].periods.push(period);
                        return acc;
                    }, {});

                    return {
                        location: { latitude: lat, longitude: lon },
                        generated: new Date().toISOString(),
                        modelRun: `${modelRun.date}${modelRun.hour}z`,
                        model: model.id,
                        days: Object.values(groupedForecast).map(day => ({
                            date: day.date,
                            summary: calculateDailySummary(day.periods),
                            periods: day.periods
                        }))
                    };
                } catch (error) {
                    return logError('Error fetching model data', error);
                }
            },
            CONFIG.cache.hours * 60 * 60
        );

        return forecast;
    } catch (error) {
        return logError(`Forecast error for ${lat}N ${lon}W`, error);
    }
}

// Helper function to calculate daily summary
function calculateDailySummary(periods) {
    if (!periods?.length) return null;
    
    try {
        const calcStats = values => ({
            min: Math.min(...values),
            max: Math.max(...values),
            avg: parseFloat((values.reduce((a, b) => a + b, 0) / values.length).toFixed(1))
        });

        return {
            waveHeight: calcStats(periods.map(p => parseFloat(p.waveHeight))),
            wavePeriod: calcStats(periods.map(p => parseFloat(p.wavePeriod))),
            windSpeed: calcStats(periods.map(p => parseFloat(p.windSpeed)))
        };
    } catch (error) {
        return logError('Error calculating daily summary', error);
    }
}

module.exports = {
    getPointForecast,
    CONFIG
}; 