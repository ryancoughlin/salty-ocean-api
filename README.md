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

## Deployment

1. Build and start with Docker:

```bash
docker-compose up -d
```

The API will be available at `http://localhost:5010`

## API Endpoints

### GET /health

Health check endpoint returns status of the API.

### Offshore Stations

- GET /offshore-stations/{station_id}/observations - Get real-time observations for a station
- GET /offshore-stations/{station_id}/forecast - Get wave forecast for a station

## License

ISC
