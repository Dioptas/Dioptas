Understanding integration and uncertainties
===========================================

Integration turns a two-dimensional detector image into a one-dimensional
diffraction pattern. This guide explains the main choices and the meaning of the
result. For the controls themselves, see :doc:`integration` under **X → 1D
Integration**.


From an image to a pattern
--------------------------

The calibration assigns a scattering angle or momentum transfer to each pixel.
Integration combines pixels in the same radial interval, called a **bin**, into
one intensity point. The mask excludes unwanted pixels, and the selected azimuth
range determines which part of each ring contributes.

Solid-angle and polarization corrections account for how the measurement
geometry affects the recorded intensity. Use the same geometry, mask, radial
range and corrections when comparing two integrations.


Binning, pixel splitting and supersampling
------------------------------------------

**Binning** sets the number of output points. More bins give a finer sampling of
the pattern, but do not by themselves improve the detector's physical resolution.
Very fine bins can contain few contributing pixels and show more noise.

A detector pixel covers a finite area and can overlap more than one radial bin.
**Pixel splitting** distributes its contribution between those bins. Different
methods approximate the overlap differently. A bounding-box approximation uses
a simpler footprint than geometric splitting, so the methods need not produce
identical patterns.

**Supersampling** estimates the overlap by sampling smaller regions inside each
pixel. A sampling value of ``n`` per dimension uses ``n × n`` subpixels. Increasing
``n`` requires more work when building integration tables and can increase their
memory use; it does not create additional measured information. Geometric pixel
splitting does not use this sampling count.

Compare peak position, shape and integrated intensity when choosing settings.
Speed alone is not an accuracy test, and equal bin or sampling counts do not
guarantee equal algorithms.


.. _dioptrin-sampling-modes:

Selecting the Dioptrin integration method
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With **Use Dioptrin** enabled and Dioptrin handling the integration, the
**Supersampling** control under **X → 1D Integration** selects the method:

.. list-table:: Dioptrin sampling modes
   :header-rows: 1
   :widths: 20 80

   * - Control value
     - Method used by Dioptrin
   * - ``1``
     - **Geometric pixel splitting**
   * - ``n > 1``
     - **Dioptrin supersampling**

At ``1``, pixel/bin overlap is calculated geometrically, without a subpixel
sampling grid. At ``n > 1``, Dioptrin uses its native supersampling with ``n × n``
subpixels per detector pixel: ``5`` means ``5 × 5 = 25`` subpixels, and ``15`` means
``15 × 15 = 225``.

**Setting 1 does not disable pixel splitting.** Increasing the value switches
from geometric pixel splitting to the subpixel-sampling method; it does not tune
the precision of geometric pixel splitting. Selecting a higher value by itself
does not switch the backend to pyFAI.

Implementation and normalization conventions can differ between integration
libraries, so the same sampling value does not guarantee identical patterns.
These control-value rules describe the Dioptrin backend.


.. _poisson-counting-errors:

Poisson counting errors
-----------------------

Even a stable experiment records slightly different photon counts on repeated
exposures. For independent raw photon counts, the Poisson estimate of the
standard deviation is approximately the square root of the count:

* 100 counts gives an estimated standard deviation of about 10, or 10%.
* 10,000 counts gives about 100, or 1%.

Integration propagates pixel variances through the overlap weights and
normalization to estimate the **counting uncertainty of each integrated intensity
point**. It is not generally the square root of the final, corrected intensity.
The output uncertainty is also distinct from the spread of pixel intensities
around the ring.

Enable **Calculate Poisson Errors** in the **X → 1D Integration** controls to
retain these uncertainties with the pattern. The option is off by default and
uses the active integration backend. It adds an uncertainty calculation; it does
not smooth the pattern or improve the measured counts.

Use it when exporting uncertainty-bearing data or preparing weighted fits.
For routine browsing, comparing peak positions or identifying phases, an
intensity-only pattern is often sufficient. The ``.xye`` and ``.fxye`` formats
need the uncertainty values. Selecting these auto-save formats offers to enable
error calculation and reintegrate if necessary; once calculated, saving the
pattern reuses its stored uncertainties.

Dioptas estimates Poisson errors from the processed image passed to the active
backend. Scaled or background-subtracted values are no longer raw photon counts;
these estimates do not fully propagate the original counting variances and the
uncertainty in image corrections or subtracted data. Calibration, detector gain,
background modeling and other systematic effects require their own treatment.
A single error column also does not describe correlations between neighboring
bins introduced by pixel splitting.

For the numerical conventions used by pyFAI, see its
`weighted-average and uncertainty-propagation reference
<https://pyfai.readthedocs.io/en/latest/statistics.html>`_. Different backends can
use different overlap and normalization conventions, so their uncertainty arrays
need not agree exactly.


Spottiness is a different measurement
-------------------------------------

**Show Spottiness** measures how much the corrected pixel intensities vary around
each ring. Large spread can reveal spots or texture, and also includes counting
noise. It does not directly give the counting uncertainty of the integrated mean.

Choose Poisson errors for an uncertainty estimate on the pattern, and spottiness
to inspect azimuthal variation. Either, both or neither can be enabled. Spottiness
is exported separately and does not replace the Poisson error column. See
:ref:`integration-spottiness` for the display, weighting and export details.


Understanding processing speed and memory
-----------------------------------------

**Frames per second (fps)** measures how many complete detector images a pipeline
processes each second. Check what the timing includes:

* **Integration only:** the images are already in memory.
* **File loading and integration:** opening and decoding each image are included.
* **Complete application:** the readers, processing, output writing and interface
  updates relevant to the chosen workflow are included.

Calibration and integration-table setup can be expensive but are reused while
the geometry and relevant settings remain unchanged. Report setup separately
from repeated, warm integration. A warm file-cache measurement includes decoding
but does not establish performance for a cold disk or network storage.

One frame's processing time and a batch's throughput are different quantities.
Several workers can process different images concurrently, increasing batch fps
without making one image equally faster. A Python worker thread is also distinct
from numerical threads inside an integration library. Record both limits when
comparing configurations.

Dioptas supports several image readers, including multi-frame HDF5 inputs.
File format, compression, storage and the selected frames can change the balance
between loading and integration. Native library file-batch timings are therefore
not automatically the speed of interactive Dioptas browsing.

Dioptrin frame workers share their calibration and integration tables. Total
memory still includes image-reading buffers, temporary arrays, results and
allocator-retained pages; it can grow with the number of active workers. Shared
calibration data do not mean constant total memory use.

For measured examples with the software versions, detector data, worker limits
and timing scope recorded, see the
`Dioptrin, azint and pyFAI benchmark comparison
<https://www.clemensprescher.com/programs/dioptrin/benchmarks/>`_.
