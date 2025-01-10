const axios = require('axios');
const { logger } = require('../utils/logger');
const { formatTimestamp } = require('../utils/formatters');

const NOAA_COOPS_API = 'https://api.tidesandcurrents.noaa.gov/api/prod/datagetter';

/**
 * Get tide predictions for a station
 */
async function getTidePredictions(stationId, startDate, endDate) {
    try {
        const params = {
            station: stationId,
            begin_date: formatDate(startDate),
            end_date: formatDate(endDate),
            product: 'predictions',
            datum: 'MLLW',
            units: 'english',
            time_zone: 'gmt',
            format: 'json',
            interval: 'hilo'
        };

        const response = await axios.get(NOAA_COOPS_API, { params });
        
        if (!response.data?.predictions) {
            logger.warn(`No tide predictions available for station ${stationId}`);
            return [];
        }

        return response.data.predictions.map(prediction => ({
            time: formatTimestamp(prediction.t),
            height: Number(prediction.v),
            type: prediction.type
        }));
    } catch (error) {
        logger.error(`Error fetching tide predictions for station ${stationId}:`, error);
        throw error;
    }
}

/**
 * Format date for NOAA API (YYYYMMDD)
 */
function formatDate(date) {
    return date.toISOString().split('T')[0].replace(/-/g, '');
}

module.exports = {
    getTidePredictions
}; 