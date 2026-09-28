# Dioptas

A GUI program for fast analysis of powder X-ray diffraction images. It provides the capability of calibrating,
creating masks, having pattern overlays and showing phase lines.

## Documentation

The full user manual is hosted on Read the Docs:

https://dioptas.readthedocs.io/

## Maintainer

Clemens Prescher (clemens.prescher@gmail.com)

## Requirements

- Python 3.11, 3.12, or 3.13

Dioptas runs on 64-bit Windows, macOS, and Linux. Python packages support
Python 3.11–3.13. The standalone macOS application targets Apple silicon;
Intel Mac users can install the Python package.

The offline material library and EoS calculations are supplied by Peritheos
(0.11.0 or newer), with diffraction reflections calculated by PhaseSmith 0.7.
Both dependencies are installed automatically with the Python package and
included in standalone applications.

## Installation

### Executables

Executable versions for Windows, macOS, and Linux can be downloaded from:

https://github.com/Dioptas/Dioptas/releases

The executable versions are self-contained and do not need a Python installation.
Under Windows and Linux the program can be started by running the executable (e.g. Dioptas.exe or Dioptas).
On macOS, open the `.dmg` and drag Dioptas to Applications. A `.tar.gz` archive of the application is also available.

If macOS shows a warning that the app "cannot be verified", you need to remove the quarantine attribute by running the following command in the Terminal:

```bash
xattr -dr com.apple.quarantine /Applications/Dioptas_*.app
```

### Python Package

Use a Python 3.11–3.13 environment and install the Dioptas package with pip.

```bash
python -m pip install dioptas
```

and then run Dioptas by typing:

```bash
dioptas
```

on the command line.

Dioptas is also available from conda-forge. Its available version can lag behind
GitHub and PyPI; check the resolved version before relying on new features:

```bash
conda config --add channels conda-forge
conda install dioptas
```

## Running the Program from source

In order to run the program from source, the easiest way is to use the uv package manager.
Clone the repository from github and navigate to the repository:

```bash
git clone https://github.com/Dioptas/Dioptas.git
cd Dioptas
```

Note: This will clone the `develop` branch by default, which contains the latest development version.
If you want to use the latest stable release instead, switch to the `main` branch after cloning:

```bash
git checkout main
```

Install uv and the dependencies by running:

```bash
python -m pip install uv
uv sync
```

This will create a new environment with all the required python packages in `.venv`.

Afterward the program can be started by running:

```bash
uv run dioptas
```

In order to run the program without uv, you need to install the required packages yourself.
The packages are listed in the file `pyproject.toml`. The program can then be started by running:

```bash
python run.py
```

## Scripting API

Dioptas can also be used as a Python library for headless integration from scripts and Jupyter notebooks.
Set up your experiment in the GUI, save a `.dio` project file, then use it in code:

```python
from dioptas.pipeline import Pipeline

# Load full setup (calibration, mask, corrections, etc.) from a project file
p = Pipeline.from_project("experiment.dio")

# Override the mask if needed
p.load_mask("new_beamstop.mask")

# Integrate a single image
pattern = p.integrate("sample_001.tiff")
pattern.save("sample_001.xy")

# Batch integrate with a glob pattern
patterns = p.integrate_batch("data/sample_*.tif")
```

See the [scripting API documentation](docs/source/scripting_api.rst) for the full reference.
