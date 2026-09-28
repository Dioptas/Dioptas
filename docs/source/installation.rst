Installation and Upgrading
==========================

Standalone applications
-----------------------

Download the application for your platform from the
`GitHub releases <https://github.com/Dioptas/Dioptas/releases>`_. These packages
include Python, the integration libraries, and the offline Peritheos material
catalog; no separate Python installation is needed.

- **Windows (64-bit x86):** use the installer, or unpack the ZIP and run
  ``Dioptas.exe``. Keep the executable with its accompanying folders.
- **macOS (Apple silicon):** open the DMG and drag the application to
  Applications, or unpack the application archive. Intel Mac users can use the
  Python package below. If macOS blocks an application you downloaded from the
  official release, remove its quarantine attribute in Terminal, adjusting the
  path to the application you installed::

      xattr -dr com.apple.quarantine /Applications/Dioptas_*.app

- **Linux (64-bit x86):** make the AppImage executable and open it::

      chmod +x Dioptas_Linux.AppImage
      ./Dioptas_Linux.AppImage

  Alternatively, unpack the Linux archive and run ``Dioptas`` inside its folder.
  Keep all files in the archive together. If FUSE is unavailable, the AppImage
  can extract itself temporarily and run with::

      APPIMAGE_EXTRACT_AND_RUN=1 ./Dioptas_Linux.AppImage

Python package
--------------

Use Python **3.11, 3.12 or 3.13** in a virtual environment. For example::

    python3.13 -m venv dioptas-env

Activate it with ``source dioptas-env/bin/activate`` on macOS/Linux, or
``dioptas-env\Scripts\activate`` in Windows Command Prompt. Then install and run::

    python -m pip install dioptas
    dioptas

To upgrade an existing Python installation::

    python -m pip install --upgrade dioptas

Dioptas 0.11 requires Peritheos 0.11 or newer and PhaseSmith 0.7. Pip installs
these dependencies automatically. Catalog contents follow the installed
Peritheos version; standalone applications contain the version selected when
that application was built.

Conda-forge packages are maintained separately and may become available later
than GitHub and PyPI. Check the version selected by conda before relying on a
feature from a new release.

Existing projects
-----------------

Keep original project files when upgrading and save your first updated session
under a new name. Dioptas 0.11 reads the project format introduced in 0.9;
0.8.7 and earlier projects require their matching older application.
See :doc:`configurations_and_projects` for persistence and recovery details.

Running from source
-------------------

Clone the repository and install the dependencies using uv::

    git clone https://github.com/Dioptas/Dioptas.git
    cd Dioptas
    python -m pip install uv
    uv sync
    uv run dioptas

The default branch is ``develop``. For a specific published release, check out
its tag before running ``uv sync``, for example ``git checkout 0.11.0`` once that
release is published. A source checkout builds Dioptas's small native extension
and may require a C compiler; ordinary wheel installations do not.
