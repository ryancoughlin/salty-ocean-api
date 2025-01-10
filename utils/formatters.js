/**
 * Standardized formatting utilities
 */

// Wave heights should be numbers with 1 decimal place
const formatWaveHeight = (meters) => {
    if (!meters || isNaN(meters)) return null;
    return Number((meters * 3.28084).toFixed(1));
};

// Wind speeds should be whole numbers in mph
const formatWindSpeed = (knots) => {
    if (!knots || isNaN(knots)) return null;
    return Math.round(knots * 1.15078);
};

// Temperatures in Fahrenheit with 1 decimal place
const formatTemperature = (celsius) => {
    if (!celsius || isNaN(celsius)) return null;
    return Number(((celsius * 9/5) + 32).toFixed(1));
};

// Pressure in mb/hPa with 1 decimal place
const formatPressure = (pressure) => {
    if (!pressure || isNaN(pressure)) return null;
    return Number(pressure.toFixed(1));
};

// Wave/wind directions should be whole numbers 0-359
const formatDirection = (degrees) => {
    if (!degrees || isNaN(degrees)) return null;
    return Math.round(degrees) % 360;
};

// Wave periods should be whole numbers
const formatPeriod = (seconds) => {
    if (!seconds || isNaN(seconds)) return null;
    return Math.round(seconds);
};

// All timestamps should be UTC ISO8601
const formatTimestamp = (date) => {
    if (!date) return null;
    return new Date(date).toISOString();
};

module.exports = {
    formatWaveHeight,
    formatWindSpeed,
    formatTemperature,
    formatPressure,
    formatDirection,
    formatPeriod,
    formatTimestamp
}; 