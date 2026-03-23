.. sectnum::
   :start: 8

API Reference
=============

This section documents the public Python API for scripting and programmatic use
of Dioptas. For most use cases, the :class:`~dioptas.pipeline.Pipeline` class
is the recommended entry point.


Pipeline
--------

.. automodule:: dioptas.pipeline
   :members:
   :undoc-members:
   :show-inheritance:


Model Layer
-----------

The model layer contains the core data and business logic of Dioptas.
Controllers and the Pipeline class delegate all operations to these models.

DioptasModel
^^^^^^^^^^^^

.. autoclass:: dioptas.model.DioptasModel.DioptasModel
   :members:
   :show-inheritance:

Configuration
^^^^^^^^^^^^^

.. autoclass:: dioptas.model.Configuration.Configuration
   :members:
   :show-inheritance:

ImgModel
^^^^^^^^

.. autoclass:: dioptas.model.ImgModel.ImgModel
   :members:
   :show-inheritance:

CalibrationModel
^^^^^^^^^^^^^^^^

.. autoclass:: dioptas.model.CalibrationModel.CalibrationModel
   :members:
   :show-inheritance:

MaskModel
^^^^^^^^^

.. autoclass:: dioptas.model.MaskModel.MaskModel
   :members:
   :show-inheritance:

PatternModel
^^^^^^^^^^^^

.. autoclass:: dioptas.model.PatternModel.PatternModel
   :members:
   :show-inheritance:

PhaseModel
^^^^^^^^^^

.. autoclass:: dioptas.model.PhaseModel.PhaseModel
   :members:
   :show-inheritance:

OverlayModel
^^^^^^^^^^^^^

.. autoclass:: dioptas.model.OverlayModel.OverlayModel
   :members:
   :show-inheritance:


Corrections
-----------

.. autoclass:: dioptas.model.util.ImgCorrection.ImgCorrectionInterface
   :members:
   :show-inheritance:

.. autoclass:: dioptas.model.util.ImgCorrection.CbnCorrection
   :members:
   :show-inheritance:

.. autoclass:: dioptas.model.util.ImgCorrection.ObliqueAngleDetectorAbsorptionCorrection
   :members:
   :show-inheritance:

.. autoclass:: dioptas.model.util.ImgCorrection.SlabAbsorptionCorrection
   :members:
   :show-inheritance:

.. autoclass:: dioptas.model.util.ImgCorrection.CylinderAbsorptionCorrection
   :members:
   :show-inheritance:

.. autoclass:: dioptas.model.util.ImgCorrection.SphereAbsorptionCorrection
   :members:
   :show-inheritance:

.. autoclass:: dioptas.model.util.ImgCorrection.PlateAbsorptionCorrection
   :members:
   :show-inheritance:


Utilities
---------

Signal
^^^^^^

.. autoclass:: dioptas.model.util.signal.Signal
   :members:
   :show-inheritance:

JCPDS
^^^^^

.. autoclass:: dioptas.model.util.jcpds.jcpds
   :members:
   :show-inheritance:

.. autoclass:: dioptas.model.util.jcpds.jcpds_reflection
   :members:
   :show-inheritance:

CIF Converter
^^^^^^^^^^^^^

.. autoclass:: dioptas.model.util.cif.CifConverter
   :members:
   :show-inheritance:
