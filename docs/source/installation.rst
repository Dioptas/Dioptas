Installation and Upgrading
==========================

Native Rust desktop (recommended)
---------------------------------

Use the native installer for your operating system. The Rust desktop includes
its Rust/Dioptrin processing engine, examples, offline guide and scientific
resources. No separate Python installation is needed. The bundled Peritheos
catalog contains EOS definitions and provenance, without experimental datafiles
or embedded observation/audit tables.

.. note::

   `Dioptas 0.14.0-rc.1 <https://github.com/Dioptas/Dioptas/releases/tag/0.14.0-rc.1>`_
   is the first Rust desktop prerelease, with macOS, Windows and Linux installers
   for testing. The latest stable 0.13.x downloads remain the legacy Qt edition.
   See the
   `candidate release notes <https://github.com/Dioptas/Dioptas/blob/0.14.0-rc.1/desktop/RELEASE_0.14.0-rc.1.md>`_
   and
   `native installer guide <https://github.com/Dioptas/Dioptas/blob/develop/desktop/NATIVE_RELEASE.md>`_
   for verification and known limits. The rc.2 installer used in automated
   upgrade tests is a disposable fixture and is not distributed.

macOS
~~~~~

Choose the DMG matching your Mac: **Apple Silicon (arm64)** or **Intel (x86_64)**.
Both require macOS **14 or newer**. Open the DMG, drag **Dioptas Desktop** to
**Applications**, then open the installed application. Eject the disk image
after copying.

Both architecture candidates are Developer ID signed and notarized. Use
macOS's normal first-launch confirmation. The declared minimum is macOS 14;
the native installation checks ran on macOS 15.

Windows
~~~~~~~

On **64-bit x86 Windows**, run the ``*-setup.exe`` installer and follow the
installation prompts. Launch **Dioptas Desktop** from the Start menu.
The installer includes the offline Microsoft WebView2 runtime installer and
the application's Visual C++ runtime libraries.

The current test candidate is **unsigned**. Installation, upgrade and uninstall
checks passed on Windows Server 2022 x64; Windows 10/11 and ARM64 have not been
separately qualified. See the
`Windows installer guide <https://github.com/Dioptas/Dioptas/blob/develop/desktop/NATIVE_WINDOWS_RELEASE.md>`_
for the tested scope and signing status.

Linux
~~~~~

Both formats target **64-bit x86 Linux**. Use the actual downloaded filename in
place of ``VERSION`` in the examples below.

**Debian package:** on Ubuntu 22.04 or 24.04, install the local ``.deb`` through
APT so its GTK/WebKitGTK dependencies are resolved::

    sudo apt install './Dioptas Desktop_VERSION_amd64.deb'

Launch **Dioptas Desktop** from the applications menu or run
``dioptas-desktop`` in a terminal. Remove it with
``sudo apt remove dioptas-desktop``. The package requires glibc **2.35 or newer**;
other Debian-based distributions have not been separately qualified.

**AppImage:** use Ubuntu 24.04 or a compatible system with glibc **2.39 or newer**.
Make the downloaded file executable and launch it::

    chmod +x './Dioptas Desktop_VERSION_amd64.AppImage'
    './Dioptas Desktop_VERSION_amd64.AppImage'

The AppImage requires FUSE 2 (``libfuse2t64`` on Ubuntu 24.04). If FUSE is
unavailable, use the tested extraction mode::

    './Dioptas Desktop_VERSION_amd64.AppImage' --appimage-extract-and-run

Linux candidates are unsigned. Installation checks use Ubuntu runners with a
virtual X11 display and software rendering; other distributions, Wayland and
physical GPU configurations have not been qualified. See the
`Linux installer guide <https://github.com/Dioptas/Dioptas/blob/develop/desktop/NATIVE_LINUX_RELEASE.md>`_
for prerequisites and verification details.

Upgrading and existing projects
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install the newer native package for the same platform and architecture. On
macOS, replace the application in Applications; on Windows, run the newer setup
executable; on Linux, install the newer ``.deb`` or replace the AppImage.

Keep original project files and save your first session in a new edition under
a new name. The Rust desktop reads current format-2 ``.dio`` projects. Older
formats require their compatible legacy application and explicit data export.
Saving a native project through an older Qt writer can discard native-specific
metadata. See the
`native project compatibility guide <https://github.com/Dioptas/Dioptas/blob/develop/desktop/NATIVE_PROJECT_PARITY.md>`_
before moving projects between editions. The editions use separate application
identities; do not assume preferences are migrated automatically.

Python package (legacy Qt edition)
----------------------------------

``pip install dioptas`` installs the **legacy Qt/Python application**, not the
Rust desktop. Existing PyPI versions remain available for legacy workflows,
Python scripting and reproducibility. A pip package for the Rust desktop is
deferred. The legacy Qt manual is maintained on the ``legacy/qt`` branch.

Use a separate virtual environment for the legacy edition. Python **3.13** is
the recommended starting point; check the selected release's requirements
before choosing another Python version::

    python3.13 -m venv dioptas-qt-env

Activate it with ``source dioptas-qt-env/bin/activate`` on macOS/Linux, or
``dioptas-qt-env\Scripts\activate`` in Windows Command Prompt. Then install and
run the legacy application::

    python -m pip install dioptas
    dioptas

To upgrade within the legacy Qt edition::

    python -m pip install --upgrade dioptas

For a reproducible legacy environment, select an exact published package version
and retain its dependency versions. Updating the Python package does not upgrade
an installed Rust desktop application.

Pip installs the legacy edition's Python dependencies, including its Peritheos
and PhaseSmith versions. Its catalog follows the installed Peritheos package;
the Rust desktop ships its separately verified EOS-only catalog. Legacy package
installation can require native build tools where dependency wheels are
unavailable. Consult the
`legacy Qt guide <https://github.com/Dioptas/Dioptas/blob/legacy/qt/README.md>`_
for that edition's requirements. Conda-forge packages are maintained separately;
check their selected version and edition before installing.

The BM2Reference equation retains its explicit reference pressure: its V0 and
K0 describe the state at P0, which can be nonzero. Use ``.eosmat`` or a compatible
Dioptas project to preserve that reference state; legacy JCPDS files cannot
store it.

Running from source
-------------------

Native Rust desktop
~~~~~~~~~~~~~~~~~~~

Development of the Rust desktop takes place on ``develop``. Install Node/npm,
Rust, a C/C++ compiler, CMake, Git and the platform prerequisites for Tauri, then
run::

    git clone --branch develop https://github.com/Dioptas/Dioptas.git
    cd Dioptas/desktop
    npm ci
    npm run tauri:dev

See the
`desktop development guide <https://github.com/Dioptas/Dioptas/blob/develop/desktop/README.md>`_
for platform setup and checks. Python is not required to run the Rust desktop.

Legacy Qt edition
~~~~~~~~~~~~~~~~~

Use the separate ``legacy/qt`` branch for Qt maintenance, or check out the tag
matching a published legacy release before installing its dependencies::

    git clone --branch legacy/qt https://github.com/Dioptas/Dioptas.git Dioptas-qt
    cd Dioptas-qt
    python -m pip install uv
    uv sync --python 3.13
    uv run dioptas

A legacy source checkout builds a small native extension and may require a C
compiler. These Python commands run the legacy edition, not the Rust desktop.
