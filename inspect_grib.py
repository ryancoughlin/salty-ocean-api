import xarray as xr
import logging
from pathlib import Path
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Find first available Atlantic GRIB2 file
data_dir = Path("data")
grib_files = list(data_dir.glob("*atlocn*.grib2"))

if not grib_files:
    logger.error("No Atlantic GRIB2 files found in data directory")
    exit(1)

file_path = grib_files[0]
logger.info(f"\nInspecting Atlantic file: {file_path}")

# Open and inspect dataset
ds = xr.open_dataset(file_path, engine='cfgrib', backend_kwargs={'indexpath': ''})

print("\nDataset structure:")
print(ds)

print("\nDimensions:")
print(ds.dims)

print("\nCoordinates:")
for coord in ds.coords:
    print(f"\n{coord}:")
    print(ds[coord].values)

print("\nCoordinate Ranges:")
print(f"Latitude range:  {float(ds.latitude.min())} to {float(ds.latitude.max())}")
print(f"Longitude range: {float(ds.longitude.min())} to {float(ds.longitude.max())}")

# Try specific coordinate access
lat = 42.8
lon = 289.829

# Find indices
lat_idx = abs(ds.latitude - lat).argmin().item()
lon_idx = abs(ds.longitude - lon).argmin().item()

print(f"\nRequested coordinates: lat={lat}, lon={lon}")
print(f"Nearest grid point:")
print(f"lat={float(ds.latitude[lat_idx])}, lon={float(ds.longitude[lon_idx])}")
print(f"indices: lat_idx={lat_idx}, lon_idx={lon_idx}")

# Try accessing each variable at this point
print("\nValues at nearest point:")
for var in ds.data_vars:
    try:
        if 'orderedSequenceData' in ds[var].dims:
            value = ds[var].isel(
                orderedSequenceData=0,
                latitude=lat_idx,
                longitude=lon_idx
            ).values
        else:
            value = ds[var].isel(
                latitude=lat_idx,
                longitude=lon_idx
            ).values
        print(f"{var}: {value}")
    except Exception as e:
        print(f"{var}: Error - {str(e)}")

ds.close() 