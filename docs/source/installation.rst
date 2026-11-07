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
- **macOS (Apple silicon, macOS 14 or newer):** open the DMG and drag the application to
  Applications, or unpack the application archive. Intel Mac users can use the
  Python package below. Signed and notarized releases use macOS's normal
  first-launch confirmation. Older releases and ordinary branch builds may
  require removing the quarantine attribute in Terminal, adjusting the path
  to the application you installed::

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

Use Python **3.11–3.15** in a virtual environment. For example::

    python3.13 -m venv dioptas-env

Activate it with ``source dioptas-env/bin/activate`` on macOS/Linux, or
``dioptas-env\Scripts\activate`` in Windows Command Prompt. Then install and run::

    python -m pip install dioptas
    dioptas

Several tested dependencies require source builds on Python 3.15, so
installation needs native build tools,
including HDF5 development libraries. Use Python 3.13 for the simplest
installation. Free-threaded Python builds are not covered by this support range.

To upgrade an existing Python installation::

    python -m pip install --upgrade dioptas

Dioptas 0.12 requires Peritheos 0.18.x and PhaseSmith 0.7. Pip installs
these dependencies automatically. Catalog contents follow the installed
Peritheos version; standalone applications contain the version selected when
that application was built. The lock file selects the tested Peritheos 0.18.0
release. Source and standalone startup checks report the installed version
and exercise native EOSMAT conversion, thermal calculations, the core material
library and scientific assessments. Dioptas does not require the optional
``peritheos-datasets`` package or its observation tables.

The BM2Reference equation retains its explicit reference pressure: its V0 and
K0 describe the state at P0, which can be nonzero. Use ``.eosmat`` or a Dioptas
project to preserve that reference state; legacy JCPDS files cannot store it.

On macOS older than 26, xypattern 1.2.4 has no compatible Apple-silicon wheel;
Intel Macs also require its source build. Install Apple's Command Line Tools
with ``xcode-select --install`` before installing the Python package, or use
the standalone Apple-silicon application, which bundles a source-built
xypattern and does not require a compiler on your computer.

Conda-forge packages are maintained separately and may become available later
than GitHub and PyPI. Check the version selected by conda before relying on a
feature from a new release.

Existing projects
-----------------

Keep original project files when upgrading and save your first updated session
under a new name. Dioptas 0.12 reads the project format introduced in 0.9;
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
its tag before running ``uv sync``, for example ``git checkout 0.13.0``. A source checkout builds Dioptas's small native
extension and may require a C compiler; ordinary wheel installations do not.

The optional native backend uses Dioptrin 0.10.0 and dioptrin-io 0.2.0.
Their prebuilt wheels include the fused fixed-mask Eiger bridge. Install them with
``uv sync --extra dioptrin`` and start with ``uv run --extra dioptrin dioptas``.
For a pip installation, use ``pip install 'dioptas[dioptrin]'``.
Dioptrin 0.10.0 is MIT licensed and needs no activation or license key.
pyFAI remains the default backend and works without this extra. See the
`Dioptrin package <https://pypi.org/project/dioptrin/0.10.0/>`_ and
`dioptrin-io package <https://pypi.org/project/dioptrin-io/0.2.0/>`_.

Batch and map integration use Dioptrin's fixed-mask mode when no dynamic mask
plugin is enabled. With masking enabled and an active dynamic plugin, frames
are integrated individually in dynamic mode so that each frame gets a fresh
mask and normalization. Disabling masking or the dynamic plugins restores
the fixed-mask batch path for the next run.

For Batch and Map reading, the Dioptrin extra also installs the pinned MIT-licensed
``bslz4-to-sparse==0.0.22a3`` decoder on platforms with its published wheels
(macOS Apple Silicon, supported Linux architectures, and Windows x86-64).
macOS Intel retains the existing
decoder. The indexed fast path supports native-endian uint16/uint32
bitshuffle/LZ4 datasets with one complete frame per chunk. Other layouts and
an unavailable fast backend retain the existing HDF5/bitshuffle readers.

Batch, map, and live-map append processing keep bounded parallel prefetch when
dynamic masking is enabled. Each mask is still calculated for its own frame;
transformations, background corrections and scaling run through ImgModel.
Prefetched frames own independent arrays, and temporary readers are closed on
completion, cancellation or failure. Dataset aliases are resolved by HDF5
object identity; different image channels retain the established selection.

The fast index treats a source as immutable for one integration run. Changes
to its identity, size or modification time cause an error rather than returning
stale counts; reopen the source before retrying. It is not a live/SWMR reader.
Fast-decoder payload admission is capped at 2 GiB and eight workers; native
integration queues, geometry and masks require additional memory.

With Dioptrin enabled, compatible single-frame Eiger HDF5 integrations with a
fixed mask use the fused bridge included in the dioptrin-io wheel. Parallel
block decoding produces original display counts and the float64 1D pattern in
one pass. Unsupported layouts or processing settings use the established path;
dynamic masks, Batch, Map and cake processing keep their existing routes.
The core Rust I/O library remains independent of integration mathematics.

Fast 1D layout
~~~~~~~~~~~~~~

Dioptrin defaults to CSC for fast 1D integration. Select CSC or CSR in
Integration Options under Sparse layout. Fixed masks cache normalization;
dynamic masks recompute it per frame using the shared geometry weights.
Strict arithmetic, azimuthal spread and 2D retain compatible implementations.
