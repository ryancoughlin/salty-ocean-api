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

## Development

### Prerequisites

- Python 3.12+
- FastAPI
- Redis (for caching)

### Setup

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run development server:

```bash
python main.py
```

## Deployment

```bash
docker-compose up -d
```

API available at `http://localhost:5010`

## Data Sources

- NDBC Buoy Network - Real-time observations
- NOAA GFS - Wave and wind forecasts
- NOAA CO-OPS - Tide predictions

## License

ISC
