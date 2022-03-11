# dftbplus_restarter
Python scripts to instantly prepare input files to restart DFTB+ MD simulations

# Requirements
- [hsd-python](https://github.com/dftbplus/hsd-python)

# Installation
1. Download `restart_filemaker.py` and `restart_collector.py`
2. Place them in dftbplus project directory

# Usage
## restart_filemaker.py
`python restart_filemaker.py` creates a new `dftb_in.hsd` reflecting the latest coordinates and velocities of the current MD in a newly added restart directory.
To see available options:
```
python restart_filmaker.py --help
```

## restart_collector.py
`python restart_collector.py` recursively combines all MD runs `geo_end.xyz` into one file.
To see available options:
```
python restart_collector.py --help
```
