# Salty Ocean API

FastAPI application for ocean and weather data.

## API Endpoints

### Station Data

```
GET /stations/geojson                    - Get all stations in GeoJSON format
GET /stations/{station_id}/observations  - Get current station conditions (waves, wind, met)
GET /stations/{station_id}/summary       - Get station metadata and info

# Wave Data
GET /stations/{station_id}/waves/forecast - Get wave model forecast
GET /stations/{station_id}/waves/summary  - Get wave conditions summary

# Tide Data
GET /tide-stations/geojson               - Get tide stations in GeoJSON format
GET /tide-stations/{station_id}/predictions - Get tide predictions
```

### Health Check

```
GET /health - API status and scheduler state
```

## Deployment

```bash
docker-compose up -d
```

API available at `http://localhost:5010`

## License

ISC
