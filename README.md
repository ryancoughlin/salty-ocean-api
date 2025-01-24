# Salty Ocean API

A FastAPI application that provides wave forecasts for NDBC buoy stations using NOAA NOMADS NCEP wave model data.

## Deployment

1. Build and start with Docker:

```bash
docker-compose up -d
```

The API will be available at `http://localhost:5010`

## API Endpoints

### GET /health

Health check endpoint returns status of the API.

### Tide Stations

- GET /tide-stations - Get all tide stations
- GET /tide-stations/geojson - Get stations in GeoJSON format
- GET /tide-stations/{station_id}/predictions - Get tide predictions for a specific station

### Offshore Stations

- GET /offshore-stations/{station_id}/observations - Get real-time observations for a station
- GET /offshore-stations/{station_id}/forecast - Get wave forecast for a station

## License

ISC
