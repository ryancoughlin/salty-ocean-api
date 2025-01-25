import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup
import json
from models.tide_station import TideStation

def parse_stations(html_file: str) -> list[TideStation]:
    with open(html_file, 'r') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    stations = []
    for row in soup.find_all('tr'):
        name_cell = row.find('td', class_='stationname')
        if not name_cell:
            continue
            
        station_name = name_cell.find('a').text.strip()
        station_id = row.find('td', class_='stationid').text.strip()
        latitude = float(row.find('td', class_='latitude').text.strip())
        longitude = float(row.find('td', class_='longitude').text.strip())
        pred_type = row.find('td', class_='pred_type').text.strip()
        
        station = TideStation(
            name=station_name,
            station_id=station_id,
            latitude=latitude,
            longitude=longitude,
            prediction_type=pred_type
        )
        stations.append(station)
    
    return stations

def main():
    stations = parse_stations('tide crawl.html')
    
    # Convert to list of dicts for JSON serialization
    station_data = [station.model_dump() for station in stations]
    
    with open('tide_stations.json', 'w') as f:
        json.dump(station_data, f, indent=2)

if __name__ == '__main__':
    main() 