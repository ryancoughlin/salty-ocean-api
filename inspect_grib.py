import xarray as xr
import pygrib
import logging
from pathlib import Path
import numpy as np
import pandas as pd
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GribInspector:
    def __init__(self, file_path):
        self.file_path = Path(file_path)
        self.grbs = None
        self.ds = None
        
    def inspect_with_pygrib(self):
        """Detailed inspection using pygrib"""
        logger.info(f"\nInspecting with pygrib: {self.file_path}")
        try:
            self.grbs = pygrib.open(str(self.file_path))
            
            # Get basic file information
            logger.info("\n=== GRIB File Overview ===")
            msg_count = len(self.grbs)
            logger.info(f"Total messages: {msg_count}")
            
            # Analyze each message
            for i, msg in enumerate(self.grbs, 1):
                logger.info(f"\n--- Message {i}/{msg_count} ---")
                logger.info(f"Variable: {msg.name}")
                logger.info(f"Level: {msg.level} {msg.typeOfLevel}")
                logger.info(f"Valid Date: {msg.validDate}")
                logger.info(f"Grid Shape: {msg.values.shape}")
                
                # Get geographical bounds
                logger.info("Geographical Bounds:")
                logger.info(f"Lats: {msg.latitudeOfFirstGridPointInDegrees:.2f} to "
                          f"{msg.latitudeOfLastGridPointInDegrees:.2f}")
                logger.info(f"Lons: {msg.longitudeOfFirstGridPointInDegrees:.2f} to "
                          f"{msg.longitudeOfLastGridPointInDegrees:.2f}")
                
                # Print first few data points
                data_sample = msg.values.flatten()[:5]
                logger.info(f"Data sample: {data_sample}")
                
                # Get key metadata
                logger.info("\nKey Metadata:")
                for key in ['parameterName', 'parameterUnits', 'dataDate', 
                          'forecastTime', 'gridType']:
                    try:
                        value = msg.get(key)
                        logger.info(f"{key}: {value}")
                    except:
                        pass
                
        except Exception as e:
            logger.error(f"Error in pygrib inspection: {str(e)}")
        finally:
            if self.grbs:
                self.grbs.close()

    def inspect_with_xarray(self):
        """Detailed inspection using xarray"""
        logger.info(f"\nInspecting with xarray: {self.file_path}")
        try:
            self.ds = xr.open_dataset(
                self.file_path, 
                engine='cfgrib',
                backend_kwargs={'indexpath': ''}
            )
            
            logger.info("\n=== Dataset Overview ===")
            logger.info(f"Dimensions: {dict(self.ds.dims)}")
            
            logger.info("\n=== Variables ===")
            for var in self.ds.data_vars:
                logger.info(f"\nVariable: {var}")
                logger.info(f"Dimensions: {self.ds[var].dims}")
                logger.info(f"Shape: {self.ds[var].shape}")
                logger.info(f"Attributes: {self.ds[var].attrs}")
                
                # Show data sample
                data = self.ds[var].values
                if not np.isscalar(data):
                    sample = data.flatten()[:5]
                    logger.info(f"Data sample: {sample}")
                
            logger.info("\n=== Coordinates ===")
            for coord in self.ds.coords:
                logger.info(f"\nCoordinate: {coord}")
                logger.info(f"Values: {self.ds[coord].values}")
                
            logger.info("\n=== Global Attributes ===")
            for attr, value in self.ds.attrs.items():
                logger.info(f"{attr}: {value}")
                
        except Exception as e:
            logger.error(f"Error in xarray inspection: {str(e)}")
        finally:
            if self.ds is not None:
                self.ds.close()

def main():
    # Find GRIB2 files
    data_dir = Path("data")
    grib_files = list(data_dir.glob("*atlocn*.grib2"))
    
    if not grib_files:
        logger.error("No Atlantic GRIB2 files found in data directory")
        return
    
    # Inspect first file found
    file_path = grib_files[0]
    inspector = GribInspector(file_path)
    
    # Run both inspection methods
    inspector.inspect_with_pygrib()
    inspector.inspect_with_xarray()

if __name__ == "__main__":
    main() 