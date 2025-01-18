const fs = require("fs").promises;
const path = require("path");
const axios = require("axios");
const { logger } = require("../../utils/logger");
const { getOrSet } = require("../../utils/cache");
const { AppError } = require("../../middlewares/errorHandler");
const { formatDate } = require("../../utils/formatters");

// Constants
const CACHE_TTL = 60 * 60; // 1 hour
const REQUEST_TIMEOUT = 10000; // 10 seconds

class TideService {
  constructor() {
    this.stations = [];
    this.loadStations().catch((err) => {
      logger.error("Failed to load tide stations:", err);
      process.exit(1);
    });
  }

  async loadStations() {
    try {
      const stationsPath = path.join(__dirname, "../data/tide-stations.json");
      const data = await fs.readFile(stationsPath, "utf8");
      this.stations = JSON.parse(data);
      logger.info(`Loaded ${this.stations.length} tide stations`);
    } catch (error) {
      logger.error("Error loading tide stations:", error.message);
      throw error;
    }
  }

  async getAllStations() {
    if (!this.stations.length) {
      await this.loadStations();
    }
    return this.stations;
  }

  async getStationById(stationId) {
    if (!this.stations.length) {
      await this.loadStations();
    }
    return this.stations.find((s) => s.id === stationId);
  }

  async findClosestStation(lat, lon) {
    if (!this.stations.length) {
      await this.loadStations();
    }

    let closestStation = null;
    let minDistance = Infinity;

    for (const station of this.stations) {
      const [stationLon, stationLat] = station.location.coordinates;
      const distance = this.calculateDistance(lat, lon, stationLat, stationLon);

      if (distance < minDistance) {
        minDistance = distance;
        closestStation = station;
      }
    }

    return closestStation;
  }

  calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Earth's radius in km
    const dLat = this.toRad(lat2 - lat1);
    const dLon = this.toRad(lon2 - lon1);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(this.toRad(lat1)) *
        Math.cos(this.toRad(lat2)) *
        Math.sin(dLon / 2) *
        Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  toRad(value) {
    return (value * Math.PI) / 180;
  }

  async getTidePredictions(stationId, startDate, endDate) {
    const station = await this.getStationById(stationId);
    if (!station) {
      throw new AppError(404, "Station not found");
    }

    const cacheKey = `tide:${stationId}:${startDate || "now"}:${
      endDate || "week"
    }`;

    try {
      return await getOrSet(
        cacheKey,
        async () => {
          const url = this.constructApiUrl(station, startDate, endDate);
          logger.debug(`Fetching tide predictions from: ${url}`);

          const response = await axios.get(url, { timeout: REQUEST_TIMEOUT });
          const data = response.data;

          if (!data.predictions) {
            throw new AppError(
              404,
              "No predictions available for this station"
            );
          }

          return {
            id: station.id,
            predictions: data.predictions.map((p) => ({
              time: p.t,
              height: parseFloat(p.v),
            })),
            metadata: {
              station: station.name,
              state: station.state,
            },
            units: {
              height: "ft",
              time: "UTC",
            },
          };
        },
        CACHE_TTL
      );
    } catch (error) {
      logger.error("Error fetching tide predictions:", {
        stationId,
        error: error.message,
      });
      throw new AppError(
        error.response?.status || 500,
        "Failed to fetch tide predictions"
      );
    }
  }

  constructApiUrl(station, startDate, endDate) {
    const today = startDate ? new Date(startDate) : new Date();
    const weekAway = endDate ? new Date(endDate) : new Date(today);
    weekAway.setDate(today.getDate() + 6);

    return `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?station=${
      station.id
    }&begin_date=${formatDate(today)}&end_date=${formatDate(
      weekAway
    )}&product=predictions&datum=mllw&interval=hilo&units=english&time_zone=gmt&application=web_services&format=json`;
  }
}

module.exports = new TideService();
