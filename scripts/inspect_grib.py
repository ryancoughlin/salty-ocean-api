import xarray as xr
import pygrib
import logging
from pathlib import Path
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta

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
        
    def inspect_with_xarray(self):
        """Detailed inspection using xarray"""
        logger.info(f"\nInspecting with xarray: {self.file_path}")
        try:
            self.ds = xr.open_dataset(
                self.file_path, 
                engine='cfgrib',
                backend_kwargs={'indexpath': ''}
            )
            
            # Debug information
            logger.info("Dataset variables:")
            for var in self.ds.data_vars:
                logger.info(f"  {var}: {self.ds[var].shape}")
            
            return self.ds
        except Exception as e:
            logger.error(f"Error in xarray inspection: {str(e)}")
            return None
        finally:
            if self.ds is not None:
                self.ds.close()
                
    def inspect_with_pygrib(self):
        """Inspect using pygrib for more detailed information"""
        try:
            grbs = pygrib.open(str(self.file_path))
            
            # Get the first message for metadata
            msg = grbs[1]
            logger.info(f"\nGRIB File Details:")
            logger.info(f"Analysis/Forecast time: {msg.analDate} -> {msg.validDate}")
            logger.info(f"Grid: {msg.Ni}x{msg.Nj} points")
            logger.info(f"Lat/Lon Bounds: {msg.latitudeOfFirstGridPointInDegrees}N to {msg.latitudeOfLastGridPointInDegrees}N, "
                       f"{msg.longitudeOfFirstGridPointInDegrees}E to {msg.longitudeOfLastGridPointInDegrees}E")
            
            # List all parameters
            logger.info("\nParameters in file:")
            for msg in grbs:
                logger.info(f"  {msg.parameterName}: {msg.level} {msg.typeOfLevel}")
                
                # Get some statistics for wave height
                if msg.parameterName == 'Significant height of combined wind waves and swell':
                    data = msg.values
                    logger.info(f"    Min: {np.min(data):.2f} m")
                    logger.info(f"    Max: {np.max(data):.2f} m")
                    logger.info(f"    Mean: {np.mean(data):.2f} m")
            
            grbs.close()
            
        except Exception as e:
            logger.error(f"Error in pygrib inspection: {str(e)}")

def compare_grib_files():
    """Compare the three GRIB2 files from different model runs."""
    test_dir = Path("test")
    grib_files = sorted(list(test_dir.glob("gfswave.t*.atlocn.0p16.f000.grib2")))
    
    if len(grib_files) != 3:
        logger.error(f"Expected 3 GRIB2 files, found {len(grib_files)}")
        return
        
    logger.info("\nComparing GRIB2 files from different model runs:")
    
    # Analyze each file with both methods
    for file in grib_files:
        model_run = file.name.split('.')[1][1:3]  # Extract HH from tHHz
        logger.info(f"\n{'='*50}")
        logger.info(f"Analyzing {model_run}z run file:")
        inspector = GribInspector(file)
        inspector.inspect_with_pygrib()
        inspector.inspect_with_xarray()

if __name__ == "__main__":
    compare_grib_files() 