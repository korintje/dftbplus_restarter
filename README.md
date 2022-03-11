# dftbplus_restarter
Python scripts to instantly prepare input files to restart DFTB+ MD simulations

# Requirements
- [hsd-python](https://github.com/dftbplus/hsd-python)

# Installation
1. Download `restart_filemaker.py` and `restart_collector.py`
2. Place them in dftbplus project directory

# Usage
## restart_filemaker.py
```
python restart_filemaker.py
```
This script creates a new `dftb_in.hsd` with the latest MD coordinates and velocities.

To see available options: `python restart_filmaker.py --help`

## restart_collector.py
```
python restart_collector.py
``` 
This script recursively combines all resulting `geo_end.xyz` into one file.

To see available options: `python restart_collector.py --help`

# License
These scripts are distributed under [CC0](https://creativecommons.org/share-your-work/public-domain/cc0/) license.
