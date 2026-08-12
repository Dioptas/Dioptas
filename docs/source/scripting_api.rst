.. sectnum::
   :start: 7

Scripting API
=============

Dioptas provides a Python scripting API through the :class:`Pipeline` class, allowing you to use
Dioptas processing capabilities from scripts and Jupyter notebooks without the GUI.

This is useful for:

- **Beamline automation**: Integrate images from data acquisition scripts
- **Batch processing**: Process large datasets programmatically
- **Jupyter notebooks**: Interactive analysis with inline plotting
- **Reproducibility**: Version-controlled processing scripts


Quick Start
-----------

The simplest way to use the scripting API is to set up your experiment in the Dioptas GUI
(calibration, mask, corrections, etc.), save a project file (``.dio``), and then use that
project file in your scripts:

.. code-block:: python

    from dioptas.pipeline import Pipeline

    # Load the full setup from a project file
    p = Pipeline.from_project("experiment.dio")

    # Integrate an image
    pattern = p.integrate("sample_001.tiff")

    # Save the result
    pattern.save("sample_001.xy")

You can also set up a pipeline manually:

.. code-block:: python

    from dioptas.pipeline import Pipeline

    p = Pipeline()
    p.load_calibration("LaB6.poni")
    p.load_mask("beamstop.mask")

    pattern = p.integrate("sample_001.tiff")


Creating a Pipeline
-------------------

From a Project File
^^^^^^^^^^^^^^^^^^^

The recommended workflow is to configure your setup interactively in the Dioptas GUI, save
a ``.dio`` project file, and load it in your script. This restores the complete state:
calibration, mask, corrections, image orientation, and integration parameters.

.. code-block:: python

    p = Pipeline.from_project("experiment.dio")

Any individual setting can then be overridden. For example, if the mask changes between runs:

.. code-block:: python

    p = Pipeline.from_project("experiment.dio")
    p.load_mask("new_beamstop.mask")


From Scratch
^^^^^^^^^^^^

.. code-block:: python

    p = Pipeline()
    p.load_calibration("calibration.poni")
    p.load_mask("mask.tif")
    p.integration_unit = "q_A^-1"
    p.integration_num_points = 2000


Calibration
-----------

Load a pyFAI ``.poni`` calibration file:

.. code-block:: python

    p.load_calibration("calibration.poni")

Check if calibration is loaded:

.. code-block:: python

    if p.is_calibrated:
        pattern = p.integrate(image)


Masking
-------

Masks define regions to exclude from integration (e.g. beam stop, dead pixels).

Loading a mask automatically enables masking:

.. code-block:: python

    # From a file (.mask, .tif, .edf, .npy)
    p.load_mask("beamstop.mask")

    # From a numpy array
    import numpy as np
    mask = np.zeros((2048, 2048), dtype=bool)
    mask[900:1100, 900:1100] = True  # mask center region
    p.set_mask(mask)

Toggle masking on/off without removing the mask data:

.. code-block:: python

    p.use_mask = False  # temporarily disable
    p.use_mask = True   # re-enable


Background Subtraction
----------------------

Image Background
^^^^^^^^^^^^^^^^

Subtract a background image (e.g. dark frame) from all images before integration:

.. code-block:: python

    p.load_image_background("dark_frame.tiff")

    # Adjust scaling and offset
    p.image_background_scaling = 0.95
    p.image_background_offset = 10

    # Remove background subtraction
    p.reset_image_background()

Pattern Background
^^^^^^^^^^^^^^^^^^

Apply automatic background subtraction on the integrated 1D pattern using the robust
smoothing procedure of Brückner (2000, *J. Appl. Cryst.* **33**, 977–979) combined with
a Chebyshev polynomial fit — see :doc:`integration` for a description of the algorithm:

.. code-block:: python

    # Enable with default parameters
    p.set_pattern_background_subtraction()

    # Customize parameters
    p.set_pattern_background_subtraction(
        smoothing=150,     # smoothing window width
        iterations=50,     # number of iterations
        poly_order=50,     # Chebyshev polynomial order
        roi=(5, 30),       # x-range for background fitting
    )

    # Disable
    p.unset_pattern_background_subtraction()


Corrections
-----------

CbN Correction
^^^^^^^^^^^^^^

Diamond anvil cell (DAC) absorption correction for cubic boron nitride seats:

.. code-block:: python

    p.add_cbn_correction(
        diamond_thickness=2.0,
        seat_thickness=5.0,
        small_cbn_seat_radius=0.5,
        large_cbn_seat_radius=2.0,
        tilt=0,
        tilt_rotation=0,
    )

Oblique Angle Detector Absorption Correction
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Correction for detector absorption at oblique incidence angles:

.. code-block:: python

    p.add_oiadac_correction(
        detector_thickness=0.032,
        absorption_length=0.0076,
    )

Slab Sample Absorption Correction
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Absorption correction for a flat slab sample in transmission geometry, using the
depth-integrated formula of Busing & Levy (1957, *Acta Cryst.* **10**, 180–182).
The absorption coefficient is calculated automatically from the chemical formula and
the calibration wavelength:

.. code-block:: python

    # Correct for a 0.1 mm CeO2 pellet
    p.add_slab_absorption_correction(
        formula="CeO2",
        density=7.22,       # g/cm³ (optional for known materials)
        thickness=0.1,      # mm
    )

    # Tilted slab
    p.add_slab_absorption_correction(
        formula="Fe2O3",
        density=5.24,
        thickness=0.2,
        slab_tilt=10,       # degrees from beam normal
        slab_rotation=45,   # degrees
    )

Cylinder Sample Absorption Correction
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Absorption correction for a cylindrical sample (e.g., a capillary), using numerical
integration over the beam footprint (Paalman & Pings, 1962, *J. Appl. Phys.* **33**,
2635–2639). The ``beam_width`` parameter controls the illuminated area:

.. code-block:: python

    # Pencil beam (default) — synchrotron
    p.add_cylinder_absorption_correction(
        formula="SiO2",
        density=2.65,
        radius=0.15,        # mm
    )

    # Finite beam — 50 μm beam on 200 μm capillary
    p.add_cylinder_absorption_correction(
        formula="SiO2",
        density=2.65,
        radius=0.1,
        beam_width=0.05,    # mm
    )

    # With glass capillary container
    p.add_cylinder_absorption_correction(
        formula="LaB6",
        density=4.72,
        radius=0.1,
        container_formula="SiO2",   # borosilicate glass
        container_density=2.23,
        wall_thickness=0.01,        # mm
    )

Sphere Sample Absorption Correction
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Absorption correction for a spherical sample. Due to spherical symmetry,
only depends on 2θ (no orientation parameters needed). The ``beam_width``
parameter controls the illuminated area:

.. code-block:: python

    # Pencil beam (default) — synchrotron
    p.add_sphere_absorption_correction(
        formula="Fe2O3",
        density=5.24,
        radius=0.5,         # mm
    )

    # Finite beam — 50 μm beam on 1 mm sphere
    p.add_sphere_absorption_correction(
        formula="Fe2O3",
        density=5.24,
        radius=0.5,
        beam_width=0.05,    # mm
    )

Plate Sample Absorption Correction
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Absorption correction for a flat plate sample (e.g., a thin film or pellet)
in the Debye–Scherrer geometry. The correction uses an analytical formula
derived from the transmission through a flat slab at varying diffraction
angles:

.. code-block:: python

    p.add_plate_absorption_correction(
        formula="CeO2",
        density=7.22,       # g/cm³ (optional for known materials)
        thickness=0.1,      # mm
    )

Remove all corrections:

.. code-block:: python

    p.clear_corrections()


Integration Parameters
----------------------

.. code-block:: python

    # Integration unit: "2th_deg", "q_A^-1", or "d_A"
    p.integration_unit = "q_A^-1"

    # Number of radial points (None for automatic)
    p.integration_num_points = 2000

    # Azimuthal range in degrees (None for full range)
    p.azimuth_range = (-10, 10)

    # Solid angle correction
    p.correct_solid_angle = True


Integrating Images
------------------

Single Image
^^^^^^^^^^^^

Integrate from a file path or numpy array:

.. code-block:: python

    # From file
    pattern = p.integrate("sample_001.tiff")

    # From numpy array
    import fabio
    img_data = fabio.open("sample_001.tiff").data
    pattern = p.integrate(img_data)

The returned ``Pattern`` object (from the ``xypattern`` library) provides:

.. code-block:: python

    pattern.x        # numpy array of x values (2theta, q, or d)
    pattern.y        # numpy array of intensities
    pattern.name     # filename-based name

    # Save to file (.xy, .chi, .dat, .fxye)
    pattern.save("output.xy")

    # Plot with matplotlib
    import matplotlib.pyplot as plt
    plt.plot(pattern.x, pattern.y)
    plt.xlabel("2θ (°)")
    plt.ylabel("Intensity")
    plt.show()


Batch Integration
^^^^^^^^^^^^^^^^^

Integrate multiple images at once:

.. code-block:: python

    # From a list of files
    patterns = p.integrate_batch(["sample_001.tif", "sample_002.tif"])

    # From a glob pattern
    patterns = p.integrate_batch("data/sample_*.tif")

    # From a single file path
    patterns = p.integrate_batch("data/sample_001.tif")

    # Disable progress bar
    patterns = p.integrate_batch("data/*.tif", progress=False)

If ``tqdm`` is installed, a progress bar is shown by default.

Save all results:

.. code-block:: python

    for pattern in patterns:
        pattern.save(f"output/{pattern.name}.xy")


Advanced: Direct Model Access
-----------------------------

For advanced use cases, you can access the underlying Dioptas model objects directly:

.. code-block:: python

    p.calibration_model   # CalibrationModel - pyFAI geometry, detector
    p.mask_model          # MaskModel - mask data and operations
    p.img_model           # ImgModel - image data and transformations
    p.configuration       # Configuration - the full bundled configuration

This gives you access to all the functionality of the Dioptas model layer. See the
:doc:`API reference <api_reference>` or the source code for details.


Complete Example
----------------

.. code-block:: python

    from dioptas.pipeline import Pipeline
    import matplotlib.pyplot as plt

    # Load experiment setup
    p = Pipeline.from_project("experiment.dio")

    # Override mask for this run
    p.load_mask("run42_beamstop.mask")

    # Set integration parameters
    p.integration_unit = "q_A^-1"
    p.integration_num_points = 2000

    # Correct for sample absorption (0.2 mm Fe2O3 pellet)
    p.add_slab_absorption_correction(formula="Fe2O3", density=5.24, thickness=0.2)

    # Enable pattern background subtraction
    p.set_pattern_background_subtraction(smoothing=100, iterations=50)

    # Batch integrate
    patterns = p.integrate_batch("run42/scan_*.tif")

    # Plot all patterns
    fig, ax = plt.subplots()
    for pattern in patterns:
        ax.plot(pattern.x, pattern.y, label=pattern.name)
        pattern.save(f"output/{pattern.name}.xy")
    ax.set_xlabel("Q (Å⁻¹)")
    ax.set_ylabel("Intensity")
    ax.legend()
    plt.show()
