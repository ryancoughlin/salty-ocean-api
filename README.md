# Salty Ocean API

FastAPI application for ocean and weather data.

## Features

- Real-time NDBC buoy observations
- GFS wave forecasts
- NOAA tide predictions
- Weather summaries and forecasts
- Station metadata and geolocation

## API Endpoints

### Station Data

```
GET /stations/geojson              - Get all stations in GeoJSON format
GET /stations/{station_id}         - Get station metadata and info
GET /stations/{station_id}/obs     - Get current station conditions

### Wave Data

```

GET /waves/geojson - Get all wave stations in GeoJSON format
GET /waves/{station_id}/forecast - Get GFS wave forecast
GET /waves/{station_id}/summary - Get wave conditions summary

### Tide Data

```
GET /tides/geojson                 - Get tide stations in GeoJSON format
GET /tides/{station_id}/forecast   - Get tide predictions

### Wind Data

```

GET /wind/{station_id}/forecast - Get GFS wind forecast
GET /wind/{station_id}/summary - Get wind conditions summary

### Health Check

```
GET /health                        - API status and scheduler state
```
