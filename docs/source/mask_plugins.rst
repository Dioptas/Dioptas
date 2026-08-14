.. sectnum::
   :start: 8

Mask Plugins
============

Dioptas supports mask plugins — custom Python modules that automatically compute masks based on
image data. Plugins can be **static** (computed once per image shape) or **dynamic** (recomputed
for every new image).

Mask plugins are discovered automatically at startup and appear in the Mask module control panel,
where each plugin has a checkbox to enable/disable it, an optional settings button, and an
**Imprint** button.

Inside a plugin's settings dialog, **Restore Defaults** resets every field to the defaults declared
by that plugin. The live preview is recomputed from those defaults before the dialog is closed.

The Imprint button bakes the plugin's current output into the user-drawn mask and disables the
plugin in one step. This is useful for freezing a dynamic plugin's result so subsequent
analyses don't depend on the plugin's parameters or runtime — and so the next plugin run isn't
biased by the previously imprinted pixels (since plugins receive the user-drawn mask via
``existing_mask`` and use it to exclude pre-masked pixels from their statistics). Imprinting
is fully undoable: pressing undo restores the previous user mask **and** re-enables the
plugin.


Writing a Mask Plugin
---------------------

A mask plugin is a Python class that inherits from
:class:`~dioptas.model.util.MaskPlugin.MaskPluginBase`.

Minimal example
~~~~~~~~~~~~~~~

.. code-block:: python

    import numpy as np
    from dioptas.model.util.MaskPlugin import MaskPluginBase

    class DeadPixelMask(MaskPluginBase):
        name = "Dead Pixel Mask"
        is_dynamic = False  # only recompute when image shape changes

        def compute_mask(self, img_data):
            # Mask pixels that are exactly zero
            return img_data == 0

The only required method is ``compute_mask(img_data)``, which receives the current image as a
NumPy array and must return a boolean array of the same shape (``True`` = masked pixel).


Static vs Dynamic Plugins
~~~~~~~~~~~~~~~~~~~~~~~~~~

- **Static** (``is_dynamic = False``): The mask is computed once and cached. It is only
  recomputed when the image shape changes. Use this for masks that depend on detector geometry
  rather than image content (e.g., detector gaps, known bad pixels).

- **Dynamic** (``is_dynamic = True``): The mask is recomputed every time a new image is loaded.
  Use this for content-dependent masks (e.g., hot pixel detection, threshold filtering).


Geometry-Aware Plugins
~~~~~~~~~~~~~~~~~~~~~~

Plugins that need calibration geometry (e.g., 2-theta maps, beam center, wavelength) should set
``needs_geometry = True``. Their ``compute_mask`` receives a second argument — a
:class:`~dioptas.model.util.MaskPlugin.GeometryContext` object, or ``None`` if no calibration
is available.

.. code-block:: python

    from dioptas.model.util.MaskPlugin import MaskPluginBase, GeometryContext

    class PowderRingOutlierMask(MaskPluginBase):
        name = "Powder Ring Outlier Mask"
        needs_geometry = True
        is_dynamic = True

        def compute_mask(self, img_data, geometry=None):
            if geometry is None:
                # No calibration available — cannot compute
                return np.zeros(img_data.shape, dtype=bool)

            # geometry.tth_array: 2-theta per pixel (radians)
            # geometry.azi_array: azimuthal angle per pixel (radians)
            # geometry.dist, geometry.wavelength, etc.
            ...

The ``GeometryContext`` dataclass provides:

.. list-table::
   :header-rows: 1

   * - Attribute
     - Description
   * - ``tth_array``
     - Two-theta per pixel (radians), same shape as image
   * - ``azi_array``
     - Azimuthal (chi) angle per pixel (radians), same shape as image
   * - ``dist``
     - Sample-to-detector distance (meters)
   * - ``wavelength``
     - X-ray wavelength (meters)
   * - ``poni1``, ``poni2``
     - Point of normal incidence / beam center (meters)
   * - ``rot1``, ``rot2``, ``rot3``
     - Detector rotations (radians)
   * - ``pixel1``, ``pixel2``
     - Pixel sizes (meters)

Geometry is automatically updated when calibration changes. If the detector is not calibrated,
``geometry`` will be ``None`` — plugins must handle this gracefully (e.g., return an empty mask).


Adding Settings
~~~~~~~~~~~~~~~

Plugins can expose configurable parameters. Dioptas automatically builds a settings dialog
from the schema you provide.

.. code-block:: python

    class HotPixelPlugin(MaskPluginBase):
        name = "Hot Pixel Removal"
        is_dynamic = True

        def __init__(self):
            self.threshold = 1e6

        def compute_mask(self, img_data):
            return img_data > self.threshold

        def get_settings_schema(self):
            return {
                "threshold": {
                    "type": "float",
                    "default": 1e6,
                    "label": "Threshold",
                    "min": 0,
                    "max": 1e12,
                },
            }

        def update_settings(self, settings):
            self.threshold = settings.get("threshold", self.threshold)

        def get_settings(self):
            return {"threshold": self.threshold}

Supported setting types:

.. list-table::
   :header-rows: 1

   * - ``type``
     - Widget
     - Extra keys
   * - ``"float"``
     - QDoubleSpinBox
     - ``min``, ``max``, ``decimals``, ``step``
   * - ``"int"``
     - QSpinBox
     - ``min``, ``max``, ``step``
   * - ``"bool"``
     - QCheckBox
     -
   * - ``"choice"``
     - QComboBox
     - ``choices`` (list of strings, **required**)
   * - ``"str"``
     - QLineEdit
     -

Each setting dict must include ``type``, ``default``, and ``label``. Optional keys:

- ``description``: shown in a popup next to the parameter (hover over the (i) icon)
- ``min`` / ``max``: bounds for numeric types
- ``decimals``: decimal places for float spinboxes
- ``step``: increment used by the spinbox arrows / scroll wheel


Installing Plugins
------------------

There are two ways to make plugins available to Dioptas.


Method 1: User plugin directory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Place ``.py`` files in::

    ~/.dioptas/plugins/masks/

Dioptas scans this directory at startup. Any class that inherits from ``MaskPluginBase`` and is
defined in a file in this directory is automatically discovered and registered.

This method works with both pip-installed Dioptas and PyInstaller-bundled executables.

.. note::

   Plugins in the user directory can only use libraries that are already available in the
   Python environment. For PyInstaller builds, this means only libraries bundled with Dioptas
   (NumPy, SciPy, pyFAI, fabio, etc.).


Method 2: Python package with entry points
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For distributable plugins, create a standard Python package that declares an entry point in
the ``dioptas.plugins.masks`` group.

``pyproject.toml``:

.. code-block:: toml

    [project]
    name = "dioptas-plugin-hot-pixels"
    version = "0.1.0"
    dependencies = ["dioptas", "numpy"]

    [project.entry-points."dioptas.plugins.masks"]
    hot_pixels = "dioptas_hot_pixels:HotPixelPlugin"

``dioptas_hot_pixels.py``:

.. code-block:: python

    import numpy as np
    from dioptas.model.util.MaskPlugin import MaskPluginBase

    class HotPixelPlugin(MaskPluginBase):
        name = "Hot Pixel Removal"
        is_dynamic = True

        def compute_mask(self, img_data):
            return img_data > 1e6

After ``pip install dioptas-plugin-hot-pixels``, the plugin appears automatically in Dioptas.

This method works for pip/uv-installed Dioptas. For PyInstaller builds, use Method 1 instead.


Plugin API Reference
--------------------

.. class:: MaskPluginBase

   Base class for all mask plugins.

   .. attribute:: name
      :type: str

      Display name shown in the UI. Must be unique across all plugins.

   .. attribute:: is_dynamic
      :type: bool

      If ``False`` (default), the mask is cached and only recomputed when the image shape changes.
      If ``True``, the mask is recomputed on every new image.

   .. attribute:: needs_geometry
      :type: bool

      If ``True``, the plugin's ``compute_mask`` receives a ``GeometryContext`` as the second
      argument. Default is ``False``.

   .. method:: compute_mask(img_data, geometry=None, existing_mask=None, **kwargs) -> numpy.ndarray

      **Required.** Compute and return a boolean mask. ``True`` means the pixel is masked
      (excluded from integration).

      :param img_data: The current image data as a 2D NumPy array.
      :param geometry: Calibration geometry (only passed when ``needs_geometry = True``).
         ``None`` if detector is not calibrated.
      :param existing_mask: User-drawn mask (detector gaps, manual masks). ``True`` means
         the pixel is already masked. Plugins can use this to exclude pre-masked pixels
         from their statistics — useful for ignoring detector gaps when computing
         per-bin medians or local means.
      :returns: Boolean array with the same shape as *img_data*.

      Always accept ``**kwargs`` so future versions can pass additional context without
      breaking existing plugins.

   .. method:: get_settings_schema() -> dict | None

      Return a dict describing user-configurable settings, or ``None`` if the plugin has no
      settings. See `Adding Settings`_ for the schema format.

   .. method:: update_settings(settings: dict) -> None

      Called when the user changes settings via the UI. The *settings* dict contains the
      same keys as the schema.

   .. method:: get_settings() -> dict

      Return the current settings values. Used to populate the settings dialog.

   .. attribute:: has_settings
      :type: bool

      Read-only property. ``True`` if ``get_settings_schema()`` returns a non-None value.


Error Handling
--------------

- If ``compute_mask`` raises an exception, the plugin is automatically disabled and a warning
  is logged. The user can re-enable it via the checkbox.
- If ``compute_mask`` returns an array with the wrong shape, the plugin's mask is ignored and
  a warning is logged.
- If a plugin file in ``~/.dioptas/plugins/masks/`` fails to import, it is skipped and an
  error is logged. Other plugins are not affected.
