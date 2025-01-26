import xarray as xr
import os
import glob
from pathlib import Path
import numpy as np
from typing import Dict, List, Set, Tuple
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_grib_file(file_path: str) -> xr.Dataset:
    """Load a GRIB2 file and return the dataset."""
    try:
        return xr.open_dataset(file_path, engine='cfgrib')
    except Exception as e:
        logger.error(f"Error loading {file_path}: {str(e)}")
        return None

def get_structure_info(ds: xr.Dataset) -> Dict:
    """Extract structural information from dataset."""
    if ds is None:
        return None
        
    return {
        'dimensions': dict(ds.sizes),
        'coordinates': list(ds.coords),
        'data_vars': list(ds.data_vars),
        'attrs': dict(ds.attrs)
    }

def compare_datasets(files: List[str]) -> Tuple[Dict, Dict]:
    """Compare multiple GRIB2 files and return differences."""
    
    # Store structure and data comparisons
    structures = {}
    differences = {
        'dimensions': set(),
        'coordinates': set(),
        'data_vars': set(),
        'attrs': set(),
        'data_values': []
    }
    
    # Reference dataset (first file)
    ref_ds = None
    ref_structure = None
    
    for file_path in sorted(files):
        filename = os.path.basename(file_path)
        ds = load_grib_file(file_path)
        
        if ds is None:
            continue
            
        structure = get_structure_info(ds)
        structures[filename] = structure
        
        # Set first file as reference
        if ref_ds is None:
            ref_ds = ds
            ref_structure = structure
            continue
        
        # Compare structure
        if structure['dimensions'] != ref_structure['dimensions']:
            differences['dimensions'].add(filename)
            
        if set(structure['coordinates']) != set(ref_structure['coordinates']):
            differences['coordinates'].add(filename)
            
        if set(structure['data_vars']) != set(ref_structure['data_vars']):
            differences['data_vars'].add(filename)
            
        if structure['attrs'] != ref_structure['attrs']:
            differences['attrs'].add(filename)
        
        # Compare data values (excluding time-related fields)
        for var in structure['data_vars']:
            if var in ['time', 'step', 'valid_time']:
                continue
                
            try:
                if not np.array_equal(ds[var].values, ref_ds[var].values):
                    differences['data_values'].append({
                        'file': filename,
                        'variable': var
                    })
            except Exception as e:
                logger.error(f"Error comparing variable {var} in {filename}: {str(e)}")
        
        ds.close()
    
    if ref_ds is not None:
        ref_ds.close()
        
    return structures, differences

def main():
    # Get data directory from environment or use default
    data_dir = os.getenv('WAVE_DATA_DIR', 'data/')
    
    # Find all GRIB2 files
    grib_files = glob.glob(os.path.join(data_dir, '*.grib2'))
    
    if not grib_files:
        logger.error(f"No GRIB2 files found in {data_dir}")
        return
        
    logger.info(f"Found {len(grib_files)} GRIB2 files")
    
    # Compare files
    structures, differences = compare_datasets(grib_files)
    
    # Output results
    print("\n=== GRIB2 Files Comparison Results ===\n")
    
    if not any(differences.values()):
        print("✅ All files have identical structure and data (excluding time fields)")
    else:
        print("❌ Found differences:\n")
        
        if differences['dimensions']:
            print("Dimension differences in files:", differences['dimensions'])
            
        if differences['coordinates']:
            print("Coordinate differences in files:", differences['coordinates'])
            
        if differences['data_vars']:
            print("Variable differences in files:", differences['data_vars'])
            
        if differences['attrs']:
            print("Attribute differences in files:", differences['attrs'])
            
        if differences['data_values']:
            print("\nData value differences:")
            for diff in differences['data_values']:
                print(f"- File: {diff['file']}, Variable: {diff['variable']}")
    
    # Output reference structure
    ref_structure = next(iter(structures.values()))
    print("\nReference Structure:")
    print(f"Dimensions: {ref_structure['dimensions']}")
    print(f"Coordinates: {ref_structure['coordinates']}")
    print(f"Variables: {ref_structure['data_vars']}")

if __name__ == "__main__":
    main() 