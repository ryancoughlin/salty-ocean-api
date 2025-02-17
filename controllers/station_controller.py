import logging
from typing import Dict
from fastapi import HTTPException
from datetime import datetime

from models.ndbc_types import StationSummary
from core.cache import cached
from services.station_service import StationService
from services.buoy_service import BuoyService

logger = logging.getLogger(__name__)

class StationController:
    def __init__(
        self,
        station_service: StationService,
        buoy_service: BuoyService
    ):
        self.station_service = station_service
        self.buoy_service = buoy_service

    @cached(namespace="station_summary")
    async def get_station_summary(self, station_id: str) -> StationSummary:
        """Get a general summary for a specific station."""
        try:
            # Get station info
            station = self.station_service.get_station(station_id)
            if not station:
                raise HTTPException(
                    status_code=404,
                    detail=f"Station {station_id} not found"
                )
            
            # Get latest observation for metadata
            observation = await self.buoy_service.get_observation(station_id)
            
            # Create summary with metadata and observation time
            return StationSummary(
                station_id=station_id,
                metadata={
                    "id": station_id,
                    "name": station["name"],
                    "location": station["location"],
                    "type": station.get("type", "buoy")
                },
                summary=f"Station {station['name']} ({station_id})",
                last_updated=observation.time if observation else datetime.now()
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting summary for station {station_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @cached(namespace="stations_geojson")
    async def get_stations_geojson(self) -> Dict:
        """Get all monitoring stations in GeoJSON format."""
        try:
            stations = self.station_service.get_all_stations()
            
            features = []
            for station in stations:
                feature = {
                    "type": "Feature",
                    "geometry": station["location"],
                    "properties": {
                        "id": station["id"],
                        "name": station["name"],
                        "type": station.get("type", "buoy")
                    }
                }
                features.append(feature)
            
            return {
                "type": "FeatureCollection",
                "features": features
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error converting stations to GeoJSON: {str(e)}"
            ) 