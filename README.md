# Dioptas

A GUI program for fast analysis of powder X-ray diffraction Images. It provides the capability of calibrating,
creating masks, having pattern overlays and showing phase lines.

## Maintainer

Clemens Prescher (clemens.prescher@gmail.com)

## Requirements

    * python 3.9+

It is known to run on Windows, Mac and Linux. For optimal usage on a Windows machine it should be run with 64 bit
python.

## Installation

### Executables

Executable versions for Windows, Mac OsX and Linux (all 64bit) can be downloaded from:

https://github.com/Dioptas/Dioptas/releases

The executable versions are self-contained folders, which do not need any python installation.
Under Windows and Linux the program can be started by running the executable (e.g. Dioptas.exe or Dioptas).
Under MacOS X the folder will contain an app folder which needs to be right-clicked and selected "Open" to start the program.
Accepting the security prompts is required.

### Python Package

The easiest way to install the dioptas python package is using pip.

```bash
pip install dioptas
```

and then run Dioptas by typing:

```bash
dioptas
```

in the commandline.

We also maintain a conda-forge version of dioptas.
You can add the conda-forge channel to your conda distribution and then install dioptas via conda should be working correctly.

```bash
conda config --add channels conda-forge
conda install dioptas
```

## Running the Program from source

In order to run the program from source, the easiest way is to use the poetry package manager.
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

Install the dependencies by running:

```bash
poetry install
```

This will create a new environment with all the required python packages. The environment can be activated by running:

```bash
poetry shell
```

Afterward the program can be started by running:

```bash
dioptas
```

In order to run the program without activating the poetry shell environment use:

```bash
poetry run dioptas
```

In case you want to run the Dioptas from source without poetry, you need to install the required packages yourself.
The packages are listed in the file `pyproject.toml`. The program can then be started by running:

```bash
python run.py
```
