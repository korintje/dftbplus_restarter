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
This script creates a filesets for a new MD run which will restart from the latest atomic coordinates and velocities.

To see available options: `python restart_filmaker.py --help`

## restart_collector.py
```
python restart_collector.py
``` 
This script recursively combines all MD results into one "geo_end.xyz" file.

To see available options: `python restart_collector.py --help`

# License
These scripts are distributed under [CC0](https://creativecommons.org/share-your-work/public-domain/cc0/) license.
