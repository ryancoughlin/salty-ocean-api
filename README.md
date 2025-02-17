# Salty Ocean API

FastAPI application for tide predictions and wave data.

## Tide Station Endpoints

### Get All Stations

```
GET /tide-stations
```

Returns a list of all tide stations.

### Get Stations GeoJSON

```
GET /tide-stations/geojson
```

Returns tide stations in GeoJSON format for mapping applications.

### Get Station Predictions

```
GET /tide-stations/{station_id}/predictions
```

Returns high and low tide predictions for a station for the next 7 days.

Optional query parameter:

- `date`: Start date for predictions (defaults to today)

Example:

```
GET /tide-stations/8419807/predictions
```

## Station Endpoints

### Get All Stations GeoJSON

```
GET /stations/geojson
```

Returns all monitoring stations in GeoJSON format for mapping applications.

### Get Station Observations

```
GET /stations/{station_id}/observations
```

Returns the latest observations from NDBC for the specified station including waves, wind, and meteorological data.

### Get Wave Forecast

```
GET /stations/{station_id}/waves/forecast
```

Returns the latest wave model forecast from NOAA for the specified station.

### Get Wave Summary

```
GET /stations/{station_id}/waves/summary
```

Returns a summary of wave conditions and forecast for the specified station.

### Get Station Summary

```
GET /stations/{station_id}/summary
```

Returns general station information and metadata.

## Deployment

1. Build and start with Docker:

```bash
docker-compose up -d
```

The API will be available at `http://localhost:5010`

## API Endpoints

### GET /health

Health check endpoint returns status of the API.

## License

ISC
