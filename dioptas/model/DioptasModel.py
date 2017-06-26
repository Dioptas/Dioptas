# -*- coding: utf8 -*-
import os
from scipy.interpolate import interp1d, interp2d
import numpy as np
from qtpy import QtCore

import h5py

from .util import jcpds
from .util import Pattern
from .Configuration import Configuration
from . import ImgModel, CalibrationModel, MaskModel, PhaseModel, PatternModel, OverlayModel


class DioptasModel(QtCore.QObject):
    configuration_added = QtCore.Signal()
    configuration_selected = QtCore.Signal(int)  # new index
    configuration_removed = QtCore.Signal(int)  # removed index

    img_changed = QtCore.Signal()
    pattern_changed = QtCore.Signal()
    cake_changed = QtCore.Signal()

    def __init__(self, working_directories=None):
        super(DioptasModel, self).__init__()
        self.configurations = []
        self.configuration_ind = 0
        self.configurations.append(Configuration())
        self.working_directories = working_directories

        self._overlay_model = OverlayModel()
        self._phase_model = PhaseModel()

        self._combine_patterns = False
        self._combine_cakes = False
        self._cake_data = None

        self.connect_models()

    def add_configuration(self):
        self.configurations.append(Configuration(self.working_directories))

        if self.current_configuration.calibration_model.is_calibrated:
            dioptas_config_folder = os.path.join(os.path.expanduser('~'), '.Dioptas')
            if not os.path.isdir(dioptas_config_folder):
                os.mkdir(dioptas_config_folder)
            self.current_configuration.calibration_model.save(
                os.path.join(dioptas_config_folder, 'transfer.poni'))
            self.configurations[-1].calibration_model.load(
                os.path.join(dioptas_config_folder, 'transfer.poni'))

        self.configurations[-1].img_model._img_data = self.current_configuration.img_model.img_data

        self.select_configuration(len(self.configurations) - 1)
        self.configuration_added.emit()

    def remove_configuration(self):
        ind = self.configuration_ind
        self.disconnect_models()
        del self.configurations[ind]
        if ind == len(self.configurations) or ind == -1:
            self.configuration_ind = len(self.configurations) - 1
        self.connect_models()
        self.configuration_removed.emit(self.configuration_ind)

    def save(self, filename):
        # save configuration
        f = h5py.File(filename, 'w')

        configurations_group = f.create_group('configurations')
        configurations_group.attrs['selected_configuration'] = self.configuration_ind
        for ind, configuration in enumerate(self.configurations):
            configuration_group = configurations_group.create_group(str(ind))
            configuration.save_in_hdf5(configuration_group)

        # save overlays
        overlay_group = f.create_group('overlays')

        for ind, overlay in enumerate(self.overlay_model.overlays):
            ov = overlay_group.create_group(str(ind))
            ov.attrs['name'] = overlay.name
            ov.create_dataset('x', overlay.original_x.shape, 'f', overlay.original_x)
            ov.create_dataset('y', overlay.original_y.shape, 'f', overlay.original_y)
            ov.attrs['scaling'] = overlay.scaling
            ov.attrs['offset'] = overlay.offset

        # save phases
        phases_group = f.create_group('phases')
        for ind, phase in enumerate(self.phase_model.phases):
            phase_group = phases_group.create_group(str(ind))
            phase_group.attrs['name'] = phase.name
            phase_group.attrs['filename'] = phase.filename
            phase_parameter_group = phase_group.create_group('params')
            for key in phase.params:
                if key == 'comments':
                    phases_comments_group = phase_group.create_group('comments')
                    ind = 0
                    for comment in phase.params['comments']:
                        phases_comments_group.attrs[str(ind)] = comment
                        ind += 1
                else:
                    phase_parameter_group.attrs[key] = phase.params[key]
            phase_reflections_group = phase_group.create_group('reflections')
            ind = 0
            for reflection in phase.reflections:
                phase_reflection_group = phase_reflections_group.create_group(str(ind))
                phase_reflection_group.attrs['d0'] = reflection.d0
                phase_reflection_group.attrs['d'] = reflection.d
                phase_reflection_group.attrs['intensity'] = reflection.intensity
                phase_reflection_group.attrs['h'] = reflection.h
                phase_reflection_group.attrs['k'] = reflection.k
                phase_reflection_group.attrs['l'] = reflection.l
                ind += 1

        f.flush()
        f.close()

    def load(self, filename):
        self.disconnect_models()

        f = h5py.File(filename, 'r')

        # load_configurations
        self.configurations = []
        for ind, configuration_group in f.get('configurations').items():
            configuration = Configuration()
            configuration.load_from_hdf5(configuration_group)
            self.configurations.append(configuration)
        self.configuration_ind = f.get('configurations').attrs['selected_configuration']

        # load overlay model
        for ind, overlay_group in f.get('overlays').items():
            self.overlay_model.add_overlay(overlay_group.get('x')[...],
                                           overlay_group.get('y')[...],
                                           overlay_group.attrs['name'])
            ind = len(self.overlay_model.overlays) - 1
            self.overlay_model.set_overlay_offset(ind, overlay_group.attrs['offset'])
            self.overlay_model.set_overlay_scaling(ind, overlay_group.attrs['scaling'])

        # load phase model
        for ind, phase_group in f.get('phases').items():
            p_filename = phase_group.attrs.get('filename', None)
            if p_filename is not None:
                new_jcpds = jcpds()
                for p_key, p_value in phase_group.get('params').attrs.items():
                    new_jcpds.params[p_key] = p_value
                for c_key, comment in phase_group.get('comments').attrs.items():
                    new_jcpds.params['comments'].append(comment)
                for r_key, reflection in phase_group.get('reflections').items():
                    new_jcpds.add_reflection(reflection.attrs['h'], reflection.attrs['k'], reflection.attrs['l'],
                                             reflection.attrs['intensity'], reflection.attrs['d'])
                self.phase_model.phases.append(new_jcpds)
                self.phase_model.reflections.append([])
                self.phase_model.send_added_signal()

        f.close()

        self.connect_models()
        self.configuration_added.emit()
        self.select_configuration(self.configuration_ind)

    def select_configuration(self, ind):
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
        self.img_model.img_changed.disconnect(self.img_changed)
        self.pattern_model.pattern_changed.disconnect(self.pattern_changed)
        self.current_configuration.cake_changed.disconnect(self.cake_changed)

    def connect_models(self):
        self.img_model.img_changed.connect(self.img_changed)
        self.pattern_model.pattern_changed.connect(self.pattern_changed)
        self.current_configuration.cake_changed.connect(self.cake_changed)

    @property
    def working_directories(self):
        return self.current_configuration.working_directories

    @working_directories.setter
    def working_directories(self, new):
        self.current_configuration.working_directories = new

    @property
    def current_configuration(self):
        """
        :rtype: Configuration
        """
        return self.configurations[self.configuration_ind]

    @property
    def img_model(self):
        """
        :rtype: ImgModel
        """
        return self.configurations[self.configuration_ind].img_model

    @property
    def mask_model(self):
        """
        :rtype: MaskModel
        """
        return self.configurations[self.configuration_ind].mask_model

    @property
    def calibration_model(self):
        """
        :rtype: CalibrationModel
        """
        return self.configurations[self.configuration_ind].calibration_model

    @property
    def pattern_model(self):
        """
        :rtype: PatternModel
        """
        return self.configurations[self.configuration_ind].pattern_model

    @property
    def overlay_model(self):
        """
        :rtype: OverlayModel
        """
        return self._overlay_model

    @property
    def phase_model(self):
        """
        :rtype: PhaseModel
        """
        return self._phase_model

    @property
    def use_mask(self):
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
    def integration_unit(self):
        return self.current_configuration.integration_unit

    @integration_unit.setter
    def integration_unit(self, new_val):
        self.current_configuration.integration_unit = new_val

    @property
    def img_data(self):
        return self.img_model.img_data

    @property
    def cake_data(self):
        if not self.combine_cakes:
            return self.calibration_model.cake_img
        else:
            return self._cake_data

    def calculate_combined_cake(self):
        self._activate_cake()
        tth = self._get_combined_cake_tth()
        azi = self._get_combined_cake_azi()
        combined_tth, combined_azi = np.meshgrid(tth, azi)
        combined_intensity = np.zeros(combined_azi.shape)
        for configuration in self.configurations:
            cake_interp2d = interp2d(configuration.calibration_model.cake_tth,
                                     configuration.calibration_model.cake_azi,
                                     configuration.calibration_model.cake_img,
                                     fill_value=0)
            combined_intensity += cake_interp2d(tth, azi)
        self._cake_data = combined_intensity

    def _activate_cake(self):
        for configuration in self.configurations:
            if not configuration.auto_integrate_cake:
                configuration.auto_integrate_cake = True
                configuration.integrate_image_2d()

    def _get_cake_tth_range(self):
        self._activate_cake()
        min_tth = []
        max_tth = []
        for ind in range(len(self.configurations)):
            min_tth.append(np.min(self.configurations[ind].calibration_model.cake_tth))
            max_tth.append(np.max(self.configurations[ind].calibration_model.cake_tth))
        return np.min(min_tth), np.max(max_tth)

    def _get_cake_azi_range(self):
        self._activate_cake()
        min_azi = []
        max_azi = []
        for ind in range(len(self.configurations)):
            min_azi.append(np.min(self.configurations[ind].calibration_model.cake_azi))
            max_azi.append(np.max(self.configurations[ind].calibration_model.cake_azi))
        return np.min(min_azi), np.max(max_azi)

    def _get_combined_cake_tth(self):
        min_tth, max_tth = self._get_cake_tth_range()
        return np.linspace(min_tth, max_tth, 2048)

    def _get_combined_cake_azi(self):
        min_azi, max_azi = self._get_cake_azi_range()
        return np.linspace(min_azi, max_azi, 2048)

    @property
    def cake_tth(self):
        if not self.combine_cakes:
            return self.calibration_model.cake_tth
        else:
            return self._get_combined_cake_tth()

    @property
    def cake_azi(self):
        if not self.combine_cakes:
            return self.calibration_model.cake_azi
        else:
            return self._get_combined_cake_azi()

    @property
    def pattern(self):
        if not self.combine_patterns:
            return self.pattern_model.pattern
        else:
            x_min = []
            for ind in range(0, len(self.configurations)):
                # determine ranges
                x = self.configurations[ind].pattern_model.pattern.x
                x_min.append(np.min(x))

            sorted_pattern_ind = np.argsort(x_min)

            pattern = self.configurations[sorted_pattern_ind[0]].pattern_model.pattern
            for ind in sorted_pattern_ind[1:]:
                x1, y1 = pattern.data
                x2, y2 = self.configurations[ind].pattern_model.pattern.data

                pattern2_interp1d = interp1d(x2, y2, kind='linear')

                overlap_ind_pattern1 = np.where((x1 <= np.max(x2)) & (x1 >= np.min(x2)))[0]
                left_ind_pattern1 = np.where((x1 <= np.min(x2)))[0]
                right_ind_pattern2 = np.where((x2 >= np.max(x1)))[0]

                combined_x1 = x1[left_ind_pattern1]
                combined_y1 = y1[left_ind_pattern1]
                combined_x2 = x1[overlap_ind_pattern1]
                combined_y2 = (y1[overlap_ind_pattern1] + pattern2_interp1d(combined_x2)) / 2
                combined_x3 = x2[right_ind_pattern2]
                combined_y3 = y2[right_ind_pattern2]

                combined_x = np.hstack((combined_x1, combined_x2, combined_x3))
                combined_y = np.hstack((combined_y1, combined_y2, combined_y3))

                pattern = Pattern(combined_x, combined_y)

            pattern.name = "Combined Pattern"
            return pattern

    @property
    def combine_patterns(self):
        return self._combine_patterns

    @combine_patterns.setter
    def combine_patterns(self, new_val):
        self._combine_patterns = new_val
        self.pattern_changed.emit()

    @property
    def combine_cakes(self):
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

    def clear(self):
        for configuration in self.configurations:
            del configuration.calibration_model.cake_geometry
            del configuration.calibration_model.pattern_geometry
            del configuration.img_model
            del configuration.mask_model
        del self.configurations

    def _setup_multiple_file_loading(self):
        if self.combine_cakes:
            for configuration in self.configurations:
                configuration.cake_changed.disconnect(self.calculate_combined_cake)

    def _teardown_multiple_file_loading(self):
        if self.combine_cakes:
            for configuration in self.configurations:
                configuration.cake_changed.connect(self.calculate_combined_cake)
            self.calculate_combined_cake()

    def next_image(self, pos=None):
        self._setup_multiple_file_loading()
        for configuration in self.configurations:
            configuration.img_model.load_next_file(pos=pos)
        self._teardown_multiple_file_loading()

    def previous_image(self, pos=None):
        self._setup_multiple_file_loading()
        for configuration in self.configurations:
            configuration.img_model.load_previous_file(pos=pos)
        self._teardown_multiple_file_loading()

    def next_folder(self, mec_mode=False):
        self._setup_multiple_file_loading()
        for configuration in self.configurations:
            configuration.img_model.load_next_folder(mec_mode=mec_mode)
        self._teardown_multiple_file_loading()

    def previous_folder(self, mec_mode=False):
        self._setup_multiple_file_loading()
        for configuration in self.configurations:
            configuration.img_model.load_previous_folder(mec_mode=mec_mode)
        self._teardown_multiple_file_loading()
