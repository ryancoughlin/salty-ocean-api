const axios = require('axios');
const { logger } = require('../utils/logger');
const { getOrSet } = require('../utils/cache');
const CONFIG = require('../config/waveModelConfig');
const https = require('https');

// Create reusable HTTPS agent
const agent = new https.Agent({
    keepAlive: true,
    keepAliveMsecs: 1000,
    timeout: 60000,
    maxSockets: 10
});

// Model selection
const findModelForLocation = (lat, lon) => {
    const model = Object.entries(CONFIG.models)
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
    // Normalize longitude to 0-360 range
    const normalizedLon = lon < 0 ? lon + 360 : lon;
    
    // Calculate indices
    const latIdx = Math.round((lat - model.grid.lat.start) / model.grid.lat.resolution);
    const lonIdx = Math.round((normalizedLon - model.grid.lon.start) / model.grid.lon.resolution);
    
    // Validate indices
    if (latIdx < 0 || latIdx >= model.grid.lat.size) {
        throw new Error(`Invalid latitude grid index: ${latIdx} (max ${model.grid.lat.size - 1})`);
    }
    if (lonIdx < 0 || lonIdx >= model.grid.lon.size) {
        throw new Error(`Invalid longitude grid index: ${lonIdx} (max ${model.grid.lon.size - 1})`);
    }
    
    return { latIdx, lonIdx };
};

// Get available model run
const getAvailableModelRun = (now = new Date()) => {
    const hour = now.getUTCHours();
    
    // Find most recent available run
    const availableRun = CONFIG.modelRuns.hours
        .map(runHour => ({
            hour: runHour,
            availableAt: parseInt(runHour) + CONFIG.modelRuns.availableAfter[runHour]
        }))
        .reverse()
        .find(run => hour >= run.availableAt);
    
    if (!availableRun) {
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

// Fetch model data
const fetchModelData = async (url, attempt = 1) => {
    try {
        const response = await axios({
            method: 'get',
            url,
            httpAgent: agent,
            httpsAgent: agent,
            headers: { 'Accept': 'text/plain' },
            responseType: 'text',
            validateStatus: status => status === 200
        });
        
        if (!response.data || response.data.includes('Error') || response.data.includes('</html>')) {
            throw new Error('Invalid response from GDS server');
        }
        
        return response.data;
    } catch (error) {
        if (attempt >= CONFIG.request.maxRetries) {
            logger.error('Max retries exceeded for GDS request', { url, error: error.message });
            throw error;
        }
        
        const delay = Math.min(1000 * Math.pow(2, attempt - 1), 8000);
        await new Promise(resolve => setTimeout(resolve, delay));
        return fetchModelData(url, attempt + 1);
    }
};

// Process raw data into forecast periods
const processModelData = (modelRun, lines) => {
    const [year, month, day] = modelRun.date.match(/(\d{4})(\d{2})(\d{2})/).slice(1).map(Number);
    const baseTime = Date.UTC(year, month - 1, day, parseInt(modelRun.hour));
    
    // Initialize data points
    const data = {};
    let currentVar = null;
    let currentTimeIndex = 0;
    
    // Process each line
    lines.forEach(line => {
        const varMatch = Object.entries(CONFIG.variables)
            .find(([_, v]) => line.includes(`${v.key},`));
        
        if (varMatch) {
            currentVar = varMatch[1];
            currentTimeIndex = 0;
            return;
        }
        
        if (!currentVar) return;
        
        const match = line.match(/\[\d+\]\[\d+\],\s*([-\d.]+)/);
        if (!match) return;
        
        const value = parseFloat(match[1]);
        if (isNaN(value) || value >= 9.9e19) return;
        
        const time = new Date(baseTime + currentTimeIndex * CONFIG.forecast.periodHours * 60 * 60 * 1000)
            .toISOString()
            .split('T')[0];
            
        data[time] = data[time] || { date: time, periods: [] };
        data[time].periods[currentTimeIndex] = data[time].periods[currentTimeIndex] || {
            time: new Date(baseTime + currentTimeIndex * CONFIG.forecast.periodHours * 60 * 60 * 1000).toISOString(),
            waves: {},
            wind: {},
            components: { swells: [] }
        };
        
        const varName = Object.entries(CONFIG.variables)
            .find(([_, v]) => v === currentVar)[0];
        
        if (varName.startsWith('swell')) {
            const [_, num] = varName.match(/swell(\d)(\w+)/);
            const type = varName.endsWith('Height') ? 'height' :
                        varName.endsWith('Period') ? 'period' : 'direction';
                        
            data[time].periods[currentTimeIndex].components.swells[num - 1] = 
                data[time].periods[currentTimeIndex].components.swells[num - 1] || {};
            data[time].periods[currentTimeIndex].components.swells[num - 1][type] = 
                currentVar.convert(value);
        } else if (varName.startsWith('windWave')) {
            const type = varName.endsWith('Height') ? 'height' :
                        varName.endsWith('Period') ? 'period' : 'direction';
            data[time].periods[currentTimeIndex].components.windWave = 
                data[time].periods[currentTimeIndex].components.windWave || {};
            data[time].periods[currentTimeIndex].components.windWave[type] = 
                currentVar.convert(value);
        } else if (varName.startsWith('wave')) {
            const type = varName.endsWith('Height') ? 'height' :
                        varName.endsWith('Period') ? 'period' : 'direction';
            data[time].periods[currentTimeIndex].waves[type] = currentVar.convert(value);
        } else if (varName.startsWith('wind')) {
            const type = varName.endsWith('Speed') ? 'speed' : 'direction';
            data[time].periods[currentTimeIndex].wind[type] = currentVar.convert(value);
        }
        
        currentTimeIndex++;
    });

    return Object.values(data)
        .map(day => ({
            ...day,
            periods: day.periods.filter(p => p?.waves?.height && p?.waves?.period)
        }))
        .filter(day => day.periods.length > 0)
        .sort((a, b) => a.date.localeCompare(b.date));
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
                // Find appropriate model and grid location
                const model = findModelForLocation(lat, lon);
                const { latIdx, lonIdx } = getGridLocation(lat, lon, model);
                const modelRun = getAvailableModelRun();

                // Build URL for data request
                const url = `${CONFIG.baseUrl}/${modelRun.date}/gfswave.${model.name}_${modelRun.hour}z.ascii?` +
                    Object.values(CONFIG.variables)
                        .map(v => `${v.key}[0:${CONFIG.forecast.days * CONFIG.forecast.periodsPerDay - 1}][${latIdx}][${lonIdx}]`)
                        .join(',');

                // Fetch and process data
                const data = await fetchModelData(url);
                const forecastData = processModelData(modelRun, data.trim().split('\n'));

                return {
                    metadata: {
                        modelRun: `${modelRun.date}${modelRun.hour}z`,
                        model: model.id,
                        generated: new Date().toISOString(),
                        location: { latitude: lat, longitude: lon }
                    },
                    days: forecastData
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
    CONFIG
}; 