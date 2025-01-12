const axios = require('axios');
const { logger } = require('../utils/logger');
const { getOrSet } = require('../utils/cache');
const CONFIG = require('../config/waveModelConfig');
const https = require('https');

// Create a reusable HTTPS agent with keep-alive
const agent = new https.Agent({
    keepAlive: true,
    keepAliveMsecs: 1000,
    timeout: 60000,
    maxSockets: 10
});

// Model selection
const findModelForLocation = (lat, lon, models) => {
    const model = Object.entries(models)
        .find(([_, m]) => {
            const inLatRange = lat >= m.grid.lat.start && lat <= m.grid.lat.end;
            const inLonRange = lon >= m.bounds.min && lon <= m.bounds.max;
            return inLatRange && inLonRange;
        });
    
    if (!model) {
        throw new Error('Location is outside all regional model bounds');
    }
    
    return { id: model[0], ...model[1] };
};

// Grid calculations
const getGridLocation = (lat, lon, model) => {
    logger.debug(`Calculating grid indices for lat=${lat}, lon=${lon} in ${model.id} model`);
    
    // Normalize longitude to 0-360 range
    const normalizedLon = lon < 0 ? lon + 360 : lon;
    
    // Calculate and validate indices
    const latIdx = Math.round((lat - model.grid.lat.start) / model.grid.lat.resolution);
    const lonIdx = Math.round((normalizedLon - model.grid.lon.start) / model.grid.lon.resolution);
    
    if (latIdx < 0 || latIdx >= model.grid.lat.size) {
        throw new Error(`Invalid latitude grid index: ${latIdx} (max ${model.grid.lat.size - 1})`);
    }
    if (lonIdx < 0 || lonIdx >= model.grid.lon.size) {
        throw new Error(`Invalid longitude grid index: ${lonIdx} (max ${model.grid.lon.size - 1})`);
    }
    
    logger.info(`Valid grid indices calculated: latIdx=${latIdx}, lonIdx=${lonIdx}`);
    return { latIdx, lonIdx };
};

// Model run selection
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
            date: yesterday.toISOString().split('T')[0].replace(/-/g, ''),
            hour: CONFIG.modelRuns.hours[CONFIG.modelRuns.hours.length - 1]
        };
    }
    
    return {
        date: now.toISOString().split('T')[0].replace(/-/g, ''),
        hour: availableRun.hour
    };
};

// Data processing
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
        time: new Date(baseTime + i * CONFIG.forecast.periodHours * 60 * 60 * 1000).toISOString()
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
        
        const match = line.match(/\[\d+\]\[\d+\],\s*([-\d.]+)/);
        if (!match) return;
        
        const value = parseFloat(match[1]);
        if (isNaN(value) || value >= 9.9e19) return;
        
        const varName = Object.entries(CONFIG.variables)
            .find(([_, v]) => v === currentVar)[0];
        
        data[currentTimeIndex][varName] = currentVar.convert(value);
        currentTimeIndex++;
    });

    // Process and group data by day
    const groupedByDay = data.reduce((acc, point) => {
        if (!point.waveHeight || !point.wavePeriod) return acc;

        const date = point.time.split('T')[0];
        if (!acc[date]) {
            acc[date] = {
                date,
                periods: []
            };
        }

        acc[date].periods.push({
            time: point.time,
            waves: {
                height: point.waveHeight,
                period: point.wavePeriod,
                direction: point.waveDirection
            },
            wind: {
                speed: point.windSpeed,
                direction: point.windDirection
            },
            components: {
                windWave: point.windWaveHeight ? {
                    height: point.windWaveHeight,
                    period: point.windWavePeriod,
                    direction: point.windWaveDirection
                } : null,
                swells: [
                    point.swell1Height ? {
                        height: point.swell1Height,
                        period: point.swell1Period,
                        direction: point.swell1Direction
                    } : null,
                    point.swell2Height ? {
                        height: point.swell2Height,
                        period: point.swell2Period,
                        direction: point.swell2Direction
                    } : null,
                    point.swell3Height ? {
                        height: point.swell3Height,
                        period: point.swell3Period,
                        direction: point.swell3Direction
                    } : null
                ].filter(Boolean)
            }
        });

        return acc;
    }, {});

    // Convert to array and sort by date
    return Object.values(groupedByDay)
        .sort((a, b) => a.date.localeCompare(b.date));
};

// API request handling
const checkModelAvailability = async (modelRun) => {
    try {
        const response = await axios.get(`${CONFIG.baseUrl}/${modelRun.date}`, {
            timeout: CONFIG.request.timeout,
            headers: { 'Accept-Encoding': 'gzip, deflate' }
        });
        
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
    logger.info(`GDS Request (${attempt}/${CONFIG.request.maxRetries}): ${url}`);
    
    try {
        const response = await axios({
            method: 'get',
            url,
            httpAgent: agent,
            httpsAgent: agent,
            headers: {
                'Accept': 'text/plain',
                'Accept-Encoding': 'identity'
            },
            responseType: 'text',
            maxRedirects: 2,
            timeout: 30000,
            validateStatus: status => status === 200
        });
        
        if (response.data.includes('Error') || response.data.includes('error')) {
            throw new Error(`GDS returned error in response: ${response.data.split('\n')[0]}`);
        }
        
        return response;
    } catch (error) {
        const isConnectionError = error.code === 'ECONNRESET' || 
                                error.code === 'ECONNABORTED' ||
                                error.message.includes('socket hang up');

        logger.error(`GDS request failed`, {
            url,
            attempt,
            error: error.message,
            code: error.code,
            isConnectionError
        });

        if (attempt >= CONFIG.request.maxRetries) throw error;
        
        // Shorter delay for connection errors
        const delay = isConnectionError ? 500 : Math.min(1000 * Math.pow(2, attempt - 1), 8000);
        logger.info(`Retrying in ${delay}ms`);
        await new Promise(resolve => setTimeout(resolve, delay));
        return retryRequest(url, attempt + 1);
    }
};

async function getPointForecast(lat, lon) {
    if (!lat || !lon || isNaN(lat) || isNaN(lon)) {
        throw new Error('Invalid latitude or longitude');
    }

    const cacheKey = `ww3_forecast_${lat}_${lon}`;
    
    try {
        const { data: forecast } = await getOrSet(
            cacheKey,
            async () => {
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
                        throw new Error('No recent model runs available');
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
                    throw new Error(`Model data not available for ${modelRun.date}_${modelRun.hour}z`);
                }

                const forecastData = processModelData(modelRun, response.data.trim().split('\n'));
                if (!forecastData?.length) {
                    throw new Error('No valid forecast data found');
                }

                return {
                    location: { latitude: lat, longitude: lon },
                    generated: new Date().toISOString(),
                    modelRun: `${modelRun.date}${modelRun.hour}z`,
                    model: model.id,
                    periods: forecastData
                };
            },
            CONFIG.cache.hours * 60 * 60
        );

        logger.debug(`Retrieved forecast from cache:`, {
            hasForecast: !!forecast,
            modelRun: forecast?.modelRun,
            daysCount: forecast?.days?.length
        });

        return forecast;
    } catch (error) {
        logger.error(`Forecast error for ${lat}N ${lon}W: ${error.message}`);
        return null;
    }
}

module.exports = {
    getPointForecast,
    CONFIG
}; 