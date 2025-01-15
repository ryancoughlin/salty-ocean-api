# 🌊 Salty API

Marine conditions and forecasts from NDBC buoys and NOAA wave models.

## 🚀 Deploy

```bash
docker-compose up -d --build
```

## 📡 API

### Get Buoy Data

```http
GET /api/buoys/{buoyId}
```

Returns current conditions and 7-day forecast for a buoy.

**Response**

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

## 🔧 Environment Variables

```env
NODE_ENV=production   # Environment (development/production)
PORT=5010            # Server port (default: 5010)
LOG_LEVEL=info       # Logging level
```

## 📝 Data Sources

- NDBC (National Data Buoy Center): Current conditions
- NOAA NOMADS: Wave model forecasts
