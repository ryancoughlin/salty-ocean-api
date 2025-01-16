# 🌊 Salty API

Marine conditions and forecasts from NDBC buoys and NOAA wave models.

## 🚀 Deploy

```bash
docker-compose up -d --build
```

## 📡 API

### Offshore Stations (NDBC)

```http
GET /offshore-stations
```

Returns list of all offshore stations

```http
GET /offshore-stations/nearest?lat={latitude}&lon={longitude}
```

Returns closest offshore station to coordinates

```http
GET /offshore-stations/{stationId}
```

Returns current conditions and forecast for an offshore station

### Tide Stations (NOAA Co-Ops)

```http
GET /tide-stations
```

Returns list of all tide stations

```http
GET /tide-stations/nearest?lat={latitude}&lon={longitude}
```

Returns closest tide station to coordinates

```http
GET /tide-stations/{stationId}?startDate={date}&endDate={date}
```

Returns tide predictions for a station. Dates should be in ISO 8601 format.

**Example Response (Offshore Station)**

```json
{
  "id": "46407",
  "name": "SE PAPA",
  "location": {
    "type": "Point",
    "coordinates": [-145.2, 50.5]
  },
  "observations": {
    "time": "2024-01-09T14:50:00.000Z",
    "wind": {
      "direction": 270,
      "speed": 15,
      "gust": 19
    },
    "waves": {
      "height": 8.2,
      "dominantPeriod": 12,
      "direction": 280
    },
    "weather": {
      "pressure": 1014.2,
      "airTemp": 48.2,
      "waterTemp": 50.1
    }
  },
  "forecast": {
    "days": [
      {
        "date": "2024-01-09",
        "periods": [
          {
            "time": "2024-01-09T12:00:00.000Z",
            "wind": {
              "speed": 18,
              "direction": 270
            },
            "waves": {
              "height": 9.2,
              "period": 11,
              "direction": 285
            }
          }
        ]
      }
    ]
  },
  "units": {
    "waveHeight": "ft",
    "wavePeriod": "seconds",
    "waveDirection": "degrees",
    "windSpeed": "mph",
    "windDirection": "degrees"
  }
}
```

**Example Response (Tide Station)**

```json
{
  "id": "9447130",
  "predictions": [
    {
      "time": "2024-01-09T00:00:00.000Z",
      "height": 8.2
    }
  ],
  "metadata": {
    "station": "Seattle",
    "state": "WA"
  },
  "units": {
    "height": "ft",
    "time": "UTC"
  }
}
```

## 🔧 Environment Variables

```env
NODE_ENV=production   # Environment (development/production)
PORT=5010            # Server port (default: 5010)
LOG_LEVEL=info       # Logging level
```

## 📝 Data Sources

- NDBC (National Data Buoy Center): Offshore station conditions
- NOAA Co-Ops: Tide predictions
