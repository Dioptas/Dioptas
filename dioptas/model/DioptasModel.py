# SPDX-License-Identifier: MIT

import os
import numpy as np
import h5py

from pyFAI.multi_geometry import MultiGeometry

from xypattern import Pattern

from .util import Signal
from .util import jcpds
from .Configuration import Configuration
from . import (
    ImgModel,
    CalibrationModel,
    MaskModel,
    PhaseModel,
    PatternModel,
    OverlayModel,
    MapModel,
    BatchModel,
)
from .MapModel import MapModel
from .. import __version__


class DioptasModel(object):
    """
    Handles all the data used in Dioptas. Image, Calibration and Mask are handled by so called configurations.
    Patterns and overlays are global and always the same, no matter which configuration is selected.
    """

    def __init__(self):
        super(DioptasModel, self).__init__()
        self.configurations = []
        self.configuration_ind = 0
        self.configurations.append(Configuration())

        self._overlay_model = OverlayModel()
        self._phase_model = PhaseModel()

        self._combine_patterns = False
        self._combine_cakes = False
        self._cake_data = None
        self._cake_tth = None
        self._cake_azi = None

        self._multi_geometry = None
        self._multi_geometry_unit = None

        self.configurations[0].calibration_model.detector_reset.connect(
            self.invalidate_multi_geometry
        )

        self.configuration_added = Signal()
        self.configuration_selected = Signal(int)  # new index
        self.configuration_removed = Signal(int)  # removed index

        self.img_changed = Signal()
        self.pattern_changed = Signal()
        self.cake_changed = Signal()
        self.enabled_phases_in_cake = Signal()

        self.clicked_tth = 0
        self.clicked_azi = 0

        self.clicked_tth_changed = Signal()
        self.clicked_azi_changed = Signal()
        self.clicked_tth_changed.connect(self.update_clicked_tth)
        self.clicked_azi_changed.connect(self.update_clicked_azi)

        self.connect_models()

    def add_configuration(self):
        """
        Adds a new configuration to the list of configurations. The new configuration will have the same working
        directories as the currently selected.
        """
        self.configurations.append(Configuration(self.working_directories))

        if self.current_configuration.calibration_model.is_calibrated:
            dioptas_config_folder = os.path.join(os.path.expanduser("~"), ".Dioptas")
            if not os.path.isdir(dioptas_config_folder):
                os.mkdir(dioptas_config_folder)
            self.current_configuration.calibration_model.save(
                os.path.join(dioptas_config_folder, "transfer.poni")
            )
            self.configurations[-1].calibration_model.load(
                os.path.join(dioptas_config_folder, "transfer.poni")
            )

        self.configurations[-1].img_model._img_data = (
            self.current_configuration.img_model.img_data
        )
        self.configurations[-1].calibration_model.detector_reset.connect(
            self.invalidate_multi_geometry
        )

        self.select_configuration(len(self.configurations) - 1)
        self.invalidate_multi_geometry()
        self.configuration_added.emit()

    def remove_configuration(self):
        """
        Removes the currently selected configuration.
        """
        if len(self.configurations) == 1:
            return
        ind = self.configuration_ind
        self.configurations[ind].calibration_model.detector_reset.disconnect(
            self.invalidate_multi_geometry
        )
        self.disconnect_models()
        del self.configurations[ind]
        if ind == len(self.configurations) or ind == -1:
            self.configuration_ind = len(self.configurations) - 1
        self.connect_models()
        self.invalidate_multi_geometry()
        self.configuration_removed.emit(self.configuration_ind)

    def save(self, filename):
        """
        Saves the current state of the model in a h5py file. file-ending can be chosen as wanted. Usually Dioptas
        projects are saved as *.dio files.
        """
        f = h5py.File(filename, "w")

        f.attrs["__version__"] = __version__

        # save configuration
        configurations_group = f.create_group("configurations")
        configurations_group.attrs["selected_configuration"] = self.configuration_ind
        for ind, configuration in enumerate(self.configurations):
            configuration_group = configurations_group.create_group(str(ind))
            configuration.save_in_hdf5(configuration_group)

        # save overlays
        overlay_group = f.create_group("overlays")

        for ind, overlay in enumerate(self.overlay_model.overlays):
            ov = overlay_group.create_group(
                str(ind).zfill(5)
            )  # need to fill the ind string, in order to keep it
            # ordered also for larger numbers of overlays
            ov.attrs["name"] = overlay.name
            x, y = overlay.original_data
            ov.create_dataset("x", x.shape, "f", x)
            ov.create_dataset("y", y.shape, "f", y)
            ov.attrs["scaling"] = overlay.scaling
            ov.attrs["offset"] = overlay.offset

        # save phases
        phases_group = f.create_group("phases")
        for ind, phase in enumerate(self.phase_model.phases):
            phase_group = phases_group.create_group(str(ind))
            phase_group.attrs["name"] = phase._name
            phase_group.attrs["filename"] = phase._filename
            phase_parameter_group = phase_group.create_group("params")
            for key in phase.params:
                if key == "comments":
                    phases_comments_group = phase_group.create_group("comments")
                    for ind, comment in enumerate(phase.params["comments"]):
                        phases_comments_group.attrs[str(ind)] = comment
                else:
                    phase_parameter_group.attrs[key] = phase.params[key]
            phase_reflections_group = phase_group.create_group("reflections")
            for ind, reflection in enumerate(phase.reflections):
                phase_reflection_group = phase_reflections_group.create_group(str(ind))
                phase_reflection_group.attrs["d0"] = reflection.d0
                phase_reflection_group.attrs["d"] = reflection.d
                phase_reflection_group.attrs["intensity"] = reflection.intensity
                phase_reflection_group.attrs["h"] = reflection.h
                phase_reflection_group.attrs["k"] = reflection.k
                phase_reflection_group.attrs["l"] = reflection.l
        f.flush()
        f.close()

    def load(self, filename):
        """
        Loads a previously saved model (see save function) from an h5py file.
        """
        self.disconnect_models()

        f = h5py.File(filename, "r")

        # delete old configurations
        for config in self.configurations:
            del config.img_model
            del config.calibration_model
            del config.mask_model
            import gc

            gc.collect()

        # load_configurations
        self.configurations = []
        for ind, configuration_group in f.get("configurations").items():
            configuration = Configuration()
            configuration.load_from_hdf5(configuration_group)
            configuration.calibration_model.detector_reset.connect(
                self.invalidate_multi_geometry
            )
            self.configurations.append(configuration)
        self.configuration_ind = f.get("configurations").attrs["selected_configuration"]

        self.connect_models()
        self.invalidate_multi_geometry()
        self.configuration_added.emit()
        self.select_configuration(self.configuration_ind)

        # load phase model
        for ind, phase_group in f.get("phases").items():
            new_jcpds = jcpds()
            new_jcpds.name = phase_group.attrs.get("name")
            new_jcpds.filename = phase_group.attrs.get("filename")
            for p_key, p_value in phase_group.get("params").attrs.items():
                new_jcpds.params[p_key] = p_value
            for c_key, comment in phase_group.get("comments").attrs.items():
                new_jcpds.params["comments"].append(comment)
            for r_key, reflection in phase_group.get("reflections").items():
                new_jcpds.add_reflection(
                    reflection.attrs["h"],
                    reflection.attrs["k"],
                    reflection.attrs["l"],
                    reflection.attrs["intensity"],
                    reflection.attrs["d"],
                )
            new_jcpds.params["modified"] = bool(
                phase_group.get("params").attrs["modified"]
            )
            self.phase_model.phase_files.append(new_jcpds.filename)
            self.phase_model.add_jcpds_object(new_jcpds)

        # load overlay model
        for ind, overlay_group in f.get("overlays").items():
            self.overlay_model.add_overlay(
                overlay_group.get("x")[...],
                overlay_group.get("y")[...],
                overlay_group.attrs["name"],
            )
            index = len(self.overlay_model.overlays) - 1
            self.overlay_model.set_overlay_offset(index, overlay_group.attrs["offset"])
            self.overlay_model.set_overlay_scaling(
                index, overlay_group.attrs["scaling"]
            )

        f.close()

    def select_configuration(self, ind):
        """
        Selects a configuration specified by the ind(ex) as current model. This will reemit all needed signals, so that
        the GUI can update accordingly
        """
        if 0 <= ind < len(self.configurations):
            self.disconnect_models()
            self.configuration_ind = ind
            self.connect_models()
            self.configuration_selected.emit(ind)
            self.current_configuration.auto_integrate_pattern = False
            if self.combine_cakes:
                self.current_configuration.auto_integrate_cake = False
            self.img_changed.emit()
            self.current_configuration.auto_integrate_pattern = True
            if self.combine_cakes:
                self.current_configuration.auto_integrate_cake = True
            self.pattern_changed.emit()
            self.cake_changed.emit()

    def disconnect_models(self):
        """
        Disconnects signals of the currently selected configuration.
        """
        self.img_model.img_changed.disconnect(self.img_changed)
        self.pattern_model.pattern_changed.disconnect(self.pattern_changed)
        self.current_configuration.cake_changed.disconnect(self.cake_changed)

    def connect_models(self):
        """
        Connects signals of the currently selected configuration
        """
        self.img_model.img_changed.connect(self.img_changed, priority=True)
        self.pattern_model.pattern_changed.connect(self.pattern_changed)
        self.current_configuration.cake_changed.connect(self.cake_changed)

    @property
    def working_directories(self):
        return self.current_configuration.working_directories

    @working_directories.setter
    def working_directories(self, new):
        self.current_configuration.working_directories = new

    @property
    def current_configuration(self) -> Configuration:
        return self.configurations[self.configuration_ind]

    @property
    def img_model(self) -> ImgModel:
        return self.configurations[self.configuration_ind].img_model

    @property
    def mask_model(self) -> MaskModel:
        return self.configurations[self.configuration_ind].mask_model

    @property
    def calibration_model(self) -> CalibrationModel:
        return self.configurations[self.configuration_ind].calibration_model

    @property
    def pattern_model(self) -> PatternModel:
        return self.configurations[self.configuration_ind].pattern_model

    @property
    def overlay_model(self) -> OverlayModel:
        return self._overlay_model

    @property
    def phase_model(self) -> PhaseModel:
        return self._phase_model

    @property
    def batch_model(self) -> BatchModel:
        return self.configurations[self.configuration_ind].batch_model

    @property
    def map_model(self) -> MapModel:
        return self.configurations[self.configuration_ind].map_model

    @property
    def use_mask(self) -> bool:
        return self.configurations[self.configuration_ind].use_mask

    @use_mask.setter
    def use_mask(self, new_val):
        self.configurations[self.configuration_ind].use_mask = new_val

    @property
    def transparent_mask(self):
        return self.configurations[self.configuration_ind].transparent_mask

    @transparent_mask.setter
    def transparent_mask(self, new_val):
        self.configurations[self.configuration_ind].transparent_mask = new_val

    @property
    def integration_unit(self) -> str:
        return self.current_configuration.integration_unit

    @integration_unit.setter
    def integration_unit(self, new_val):
        self.current_configuration.integration_unit = new_val

    @property
    def img_data(self) -> np.ndarray:
        return self.img_model.img_data

    @property
    def cake_data(self) -> np.ndarray:
        if not self.combine_cakes:
            return self.calibration_model.cake_img
        else:
            return self._cake_data

    @property
    def pattern(self) -> Pattern:
        if not self.combine_patterns:
            return self.pattern_model.pattern
        else:
            return self._integrate_combined_1d()

    @property
    def combine_patterns(self) -> bool:
        return self._combine_patterns

    @combine_patterns.setter
    def combine_patterns(self, new_val):
        self._combine_patterns = new_val
        self.pattern_changed.emit()

    def save_combined_pattern(self, filename):
        """
        Saves the current integrated pattern
        :param filename: where to save the file
        """
        self.pattern.save(filename, unit=self.integration_unit)

    @property
    def combine_cakes(self):
        """
        :rtype: bool
        """
        return self._combine_cakes

    @combine_cakes.setter
    def combine_cakes(self, new_val):
        self._combine_cakes = new_val
        if new_val:
            for configuration in self.configurations:
                configuration.cake_changed.connect(self.calculate_combined_cake)
            self.calculate_combined_cake()
        else:
            for configuration in self.configurations:
                configuration.cake_changed.disconnect(self.calculate_combined_cake)
        self.cake_changed.emit()

    def _get_multi_geometry(self, unit="2th_deg"):
        """
        Returns a cached pyFAI MultiGeometry from all configurations' geometries.
        The MultiGeometry is recreated only when the unit changes or when invalidated.
        :param unit: radial unit for integration
        :return: MultiGeometry instance
        """
        if self._multi_geometry is None or self._multi_geometry_unit != unit:
            ais = [
                config.calibration_model.pattern_geometry
                for config in self.configurations
            ]
            self._multi_geometry = MultiGeometry(ais, unit=unit)
            self._multi_geometry_unit = unit
        return self._multi_geometry

    def invalidate_multi_geometry(self):
        """Invalidates the cached MultiGeometry so it is recreated on next use."""
        self._multi_geometry = None
        self._multi_geometry_unit = None

    def _get_lst_data_and_masks(self):
        """
        Collects image data and masks from all configurations.
        :return: (lst_data, lst_mask) tuple of lists
        """
        lst_data = []
        lst_mask = []
        for configuration in self.configurations:
            lst_data.append(configuration.img_model.img_data)
            if configuration.use_mask:
                lst_mask.append(configuration.mask_model.get_mask())
            elif configuration.mask_model.roi is not None:
                lst_mask.append(configuration.mask_model.roi_mask)
            else:
                lst_mask.append(None)
        return lst_data, lst_mask

    def _integrate_combined_1d(self) -> Pattern:
        """
        Uses pyFAI MultiGeometry to integrate all configurations into a single 1D pattern.
        """
        unit = self.integration_unit
        mg_unit = "2th_deg" if unit == "d_A" else unit

        mg = self._get_multi_geometry(unit=mg_unit)
        # Reset cached ranges so they're recalculated if geometry changed
        mg.radial_range = None
        mg.azimuth_range = None

        lst_data, lst_mask = self._get_lst_data_and_masks()

        num_points = self.current_configuration.integration_rad_points
        if num_points is None:
            num_points = self.calibration_model.calculate_number_of_pattern_points(
                self.img_model.img_data.shape, 2
            )

        polarization_factor = self.calibration_model.polarization_factor
        correct_solid_angle = self.calibration_model.correct_solid_angle

        result = mg.integrate1d(
            lst_data,
            npt=num_points,
            correctSolidAngle=correct_solid_angle,
            polarization_factor=polarization_factor,
            lst_mask=lst_mask,
        )

        x = result.radial
        y = result.intensity

        if unit == "d_A":
            wavelength = self.calibration_model.pattern_geometry.wavelength
            x = wavelength / (2 * np.sin(x / 360 * np.pi)) * 1e10

        return Pattern(x, y)

    def calculate_combined_cake(self):
        """
        Uses pyFAI MultiGeometry to combine cakes from all configurations.
        """
        self._activate_cake()

        unit = self.integration_unit
        mg_unit = "2th_deg" if unit == "d_A" else unit

        mg = self._get_multi_geometry(unit=mg_unit)
        # Reset cached ranges so they're recalculated if geometry changed
        mg.radial_range = None
        mg.azimuth_range = None

        lst_data, lst_mask = self._get_lst_data_and_masks()

        num_points = self.current_configuration.integration_rad_points
        if num_points is None:
            num_points = self.calibration_model.calculate_number_of_pattern_points(
                self.img_model.img_data.shape, 2
            )

        azimuth_points = self.current_configuration.cake_azimuth_points
        polarization_factor = self.calibration_model.polarization_factor
        correct_solid_angle = self.calibration_model.correct_solid_angle

        result = mg.integrate2d(
            lst_data,
            npt_rad=num_points,
            npt_azim=azimuth_points,
            correctSolidAngle=correct_solid_angle,
            polarization_factor=polarization_factor,
            lst_mask=lst_mask,
        )

        self._cake_data = result.intensity
        self._cake_tth = result.radial
        self._cake_azi = result.azimuthal

    def _activate_cake(self):
        """
        Activates cake integration in all configurations.
        """
        for configuration in self.configurations:
            if not configuration.auto_integrate_cake:
                configuration.auto_integrate_cake = True
                configuration.integrate_image_2d()

    @property
    def cake_tth(self):
        if not self.combine_cakes:
            return self.calibration_model.cake_tth
        else:
            return self._cake_tth

    @property
    def cake_azi(self):
        if not self.combine_cakes:
            return self.calibration_model.cake_azi
        else:
            return self._cake_azi

    def reset(self):
        """
        Resets the state of the model. It only remembers the current working directories of the currently selected
        configuration. Everything else including all configurations is deleted.
        """
        working_directories = self.working_directories
        self.disconnect_models()
        self.delete_configurations()
        self.configurations = [Configuration()]
        self.configurations[0].calibration_model.detector_reset.connect(
            self.invalidate_multi_geometry
        )
        self.configuration_ind = 0
        self.overlay_model.reset()
        self.phase_model.reset()
        self.invalidate_multi_geometry()
        self.connect_models()
        self.working_directories = working_directories
        self.configuration_removed.emit(0)
        self.configuration_selected.emit(0)
        self.img_model.img_changed.emit()
        self.pattern_model.pattern_changed.emit()

    def delete_configurations(self):
        """
        Deletes all configurations currently present in the model.
        """
        for configuration in self.configurations:
            configuration.calibration_model.pattern_geometry.reset()
            if configuration.calibration_model.cake_geometry is not None:
                configuration.calibration_model.cake_geometry.reset()
            del configuration.calibration_model.cake_geometry
            del configuration.calibration_model.pattern_geometry
            del configuration.img_model
            del configuration.mask_model
        del self.configurations

    def _setup_multiple_file_loading(self):
        """
        Performs tasks before multiple configuration load the next image. This is in particular to prevent multiple
        integrations, if only one is needed.
        """
        if self.combine_cakes:
            for configuration in self.configurations:
                configuration.cake_changed.disconnect(self.calculate_combined_cake)

    def _teardown_multiple_file_loading(self):
        """
        Performs everything after all configurations have loaded a new image.
        :return:
        """
        if self.combine_cakes:
            for configuration in self.configurations:
                configuration.cake_changed.connect(self.calculate_combined_cake)
            self.calculate_combined_cake()

    def next_image(self, pos=None):
        """
        Loads the next image for each configuration if it exists.
        :param pos: the position of the number in terms of numbers present in the filename string (not string position).
        """
        self._setup_multiple_file_loading()
        for configuration in self.configurations:
            configuration.img_model.load_next_file(pos=pos)
        self._teardown_multiple_file_loading()

    def previous_image(self, pos=None):
        """
        Loads the previous image for each configuration if it exists.
        :param pos: the position of the number in terms of numbers present in the filename string (not string position).
        """
        self._setup_multiple_file_loading()
        for configuration in self.configurations:
            configuration.img_model.load_previous_file(pos=pos)
        self._teardown_multiple_file_loading()

    def next_folder(self, mec_mode=False):
        """
        Loads an image in the next folder with the same filename. This assumes that the folders are sorted with run
        numbers, e.g. run101, run102, etc.
        :param mec_mode: flag for a special mode for the MEC beamline at LCLS-SLAC where it takes into account that also the
                         filenames have the run number included.
        :type mec_mode: bool
        """
        self._setup_multiple_file_loading()
        for configuration in self.configurations:
            configuration.img_model.load_next_folder(mec_mode=mec_mode)
        self._teardown_multiple_file_loading()

    def previous_folder(self, mec_mode=False):
        """
        Loads an image in the previous folder with the same filename. This assumes that the folders are sorted with run
        numbers, e.g. run101, run102, etc.
        :param mec_mode: flag for a special mode for the MEC beamline at LCLS-SLAC where it takes into account that also the
                         filenames have the run number included.
        :type mec_mode: bool
        """
        self._setup_multiple_file_loading()
        for configuration in self.configurations:
            configuration.img_model.load_previous_folder(mec_mode=mec_mode)
        self._teardown_multiple_file_loading()

    def blockSignals(self, block=True):
        for member in vars(self):
            attr = getattr(self, member)
            if isinstance(attr, Signal):
                attr.blocked = block

    def update_clicked_tth(self, tth):
        self.clicked_tth = tth

    def update_clicked_azi(self, azi):
        self.clicked_azi = azi
