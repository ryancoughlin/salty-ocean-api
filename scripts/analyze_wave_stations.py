import json
import requests
from typing import List, Set
from pathlib import Path
import re

def load_ndbc_stations() -> Set[str]:
    """Load NDBC station IDs from JSON file."""
    with open("ndbcStations.json", "r") as f:
        stations = json.load(f)
        return {station["id"] for station in stations}

def get_gfs_bulletin_stations(url: str) -> Set[str]:
    """Extract station IDs from GFS wave bulletin file listing."""
    response = requests.get(url)
    if not response.ok:
        print(f"Failed to fetch bulletin listing: {response.status_code}")
        return set()
    
    # Extract station IDs from filenames using regex
    # Matches patterns like: gfswave.22103.bull, gfswave.WAKE.bull
    pattern = r"gfswave\.([A-Z0-9]+)\.bull"
    matches = re.findall(pattern, response.text, re.IGNORECASE)
    return set(matches)

def main():
    # Load NDBC stations
    ndbc_stations = load_ndbc_stations()
    print(f"Total NDBC stations: {len(ndbc_stations)}")
    
    # Get GFS bulletin stations
    url = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/gfs.20250219/06/wave/station/bulls.t06z/"
    gfs_stations = get_gfs_bulletin_stations(url)
    print(f"Total GFS bulletin stations: {len(gfs_stations)}")
    
    # Find matching stations
    matching_stations = ndbc_stations.intersection(gfs_stations)
    print(f"\nNDBC stations with GFS wave bulletins: {len(matching_stations)}")
    print("\nMatching station IDs:")
    for station in sorted(matching_stations):
        print(station)
    
    # Find NDBC stations without bulletins
    missing_stations = ndbc_stations - gfs_stations
    print(f"\nNDBC stations without GFS wave bulletins: {len(missing_stations)}")

if __name__ == "__main__":
    main() 