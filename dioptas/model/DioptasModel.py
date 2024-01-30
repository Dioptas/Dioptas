# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
from scipy.interpolate import interp2d
import numpy as np

import h5py

from .util import Signal
from .util import jcpds
from .util.Pattern import Pattern, combine_patterns
from .Configuration import Configuration
from . import ImgModel, CalibrationModel, MaskModel, PhaseModel, PatternModel, OverlayModel, MapModel, BatchModel
from .MapModel2 import MapModel2
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
        """
        Removes the currently selected configuration.
        """
        if len(self.configurations) == 1:
            return
        ind = self.configuration_ind
        self.disconnect_models()
        del self.configurations[ind]
        if ind == len(self.configurations) or ind == -1:
            self.configuration_ind = len(self.configurations) - 1
        self.connect_models()
        self.configuration_removed.emit(self.configuration_ind)

    def save(self, filename):
        """
        Saves the current state of the model in a h5py file. file-ending can be chosen as wanted. Usually Dioptas
        projects are saved as *.dio files.
        """
        f = h5py.File(filename, 'w')

        f.attrs['__version__'] = __version__

        # save configuration
        configurations_group = f.create_group('configurations')
        configurations_group.attrs['selected_configuration'] = self.configuration_ind
        for ind, configuration in enumerate(self.configurations):
            configuration_group = configurations_group.create_group(str(ind))
            configuration.save_in_hdf5(configuration_group)

        # save overlays
        overlay_group = f.create_group('overlays')

        for ind, overlay in enumerate(self.overlay_model.overlays):
            ov = overlay_group.create_group(str(ind).zfill(5))  # need to fill the ind string, in order to keep it
            # ordered also for larger numbers of overlays
            ov.attrs['name'] = overlay.name
            ov.create_dataset('x', overlay.original_x.shape, 'f', overlay.original_x)
            ov.create_dataset('y', overlay.original_y.shape, 'f', overlay.original_y)
            ov.attrs['scaling'] = overlay.scaling
            ov.attrs['offset'] = overlay.offset

        # save phases
        phases_group = f.create_group('phases')
        for ind, phase in enumerate(self.phase_model.phases):
            phase_group = phases_group.create_group(str(ind))
            phase_group.attrs['name'] = phase._name
            phase_group.attrs['filename'] = phase._filename
            phase_parameter_group = phase_group.create_group('params')
            for key in phase.params:
                if key == 'comments':
                    phases_comments_group = phase_group.create_group('comments')
                    for ind, comment in enumerate(phase.params['comments']):
                        phases_comments_group.attrs[str(ind)] = comment
                else:
                    phase_parameter_group.attrs[key] = phase.params[key]
            phase_reflections_group = phase_group.create_group('reflections')
            for ind, reflection in enumerate(phase.reflections):
                phase_reflection_group = phase_reflections_group.create_group(str(ind))
                phase_reflection_group.attrs['d0'] = reflection.d0
                phase_reflection_group.attrs['d'] = reflection.d
                phase_reflection_group.attrs['intensity'] = reflection.intensity
                phase_reflection_group.attrs['h'] = reflection.h
                phase_reflection_group.attrs['k'] = reflection.k
                phase_reflection_group.attrs['l'] = reflection.l
        f.flush()
        f.close()

    def load(self, filename):
        """
        Loads a previously saved model (see save function) from an h5py file.
        """
        self.disconnect_models()

        f = h5py.File(filename, 'r')

        # delete old configurations
        for config in self.configurations:
            del config.img_model
            del config.calibration_model
            del config.mask_model
            import gc
            gc.collect()

        # load_configurations
        self.configurations = []
        for ind, configuration_group in f.get('configurations').items():
            configuration = Configuration()
            configuration.load_from_hdf5(configuration_group)
            self.configurations.append(configuration)
        self.configuration_ind = f.get('configurations').attrs['selected_configuration']

        self.connect_models()
        self.configuration_added.emit()
        self.select_configuration(self.configuration_ind)

        # load phase model
        for ind, phase_group in f.get('phases').items():
            new_jcpds = jcpds()
            new_jcpds.name = phase_group.attrs.get('name')
            new_jcpds.filename = phase_group.attrs.get('filename')
            for p_key, p_value in phase_group.get('params').attrs.items():
                new_jcpds.params[p_key] = p_value
            for c_key, comment in phase_group.get('comments').attrs.items():
                new_jcpds.params['comments'].append(comment)
            for r_key, reflection in phase_group.get('reflections').items():
                new_jcpds.add_reflection(reflection.attrs['h'], reflection.attrs['k'], reflection.attrs['l'],
                                         reflection.attrs['intensity'], reflection.attrs['d'])
            new_jcpds.params['modified'] = bool(phase_group.get('params').attrs['modified'])
            self.phase_model.phase_files.append(new_jcpds.filename)
            self.phase_model.add_jcpds_object(new_jcpds)

        # load overlay model
        for ind, overlay_group in f.get('overlays').items():
            self.overlay_model.add_overlay(overlay_group.get('x')[...],
                                           overlay_group.get('y')[...],
                                           overlay_group.attrs['name'])
            index = len(self.overlay_model.overlays) - 1
            self.overlay_model.set_overlay_offset(index, overlay_group.attrs['offset'])
            self.overlay_model.set_overlay_scaling(index, overlay_group.attrs['scaling'])

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
    def batch_model(self):
        """
        :rtype: BatchModel
        """
        return self.configurations[self.configuration_ind].batch_model

    @property
    def map_model(self) -> MapModel2:
        """
        :rtype: MapModel2
        """
        return self.configurations[self.configuration_ind].map_model

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
        """
        Combines cakes from all configurations into one large cake.
        """
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
        """
        Activates cake integration in all configurations.
        """
        for configuration in self.configurations:
            if not configuration.auto_integrate_cake:
                configuration.auto_integrate_cake = True
                configuration.integrate_image_2d()

    def _get_cake_tth_range(self):
        """
        Gives the range of two theta values of all cakes in the different configurations.
        :return: (minimum two theta, maximum two theta)
        """
        self._activate_cake()
        min_tth = []
        max_tth = []
        for ind in range(len(self.configurations)):
            min_tth.append(np.min(self.configurations[ind].calibration_model.cake_tth))
            max_tth.append(np.max(self.configurations[ind].calibration_model.cake_tth))
        return np.min(min_tth), np.max(max_tth)

    def _get_cake_azi_range(self):
        """
        Gives the range of azimuth values of all cakes in the different configurations.
        :return: (minimum azimuth, maximum azimuth)
        """
        self._activate_cake()
        min_azi = []
        max_azi = []
        for ind in range(len(self.configurations)):
            min_azi.append(np.min(self.configurations[ind].calibration_model.cake_azi))
            max_azi.append(np.max(self.configurations[ind].calibration_model.cake_azi))
        return np.min(min_azi), np.max(max_azi)

    def _get_combined_cake_tth(self):
        """
        Gives an 1d array of two theta values which covers the two theta range of the cakes in all configurations.
        :return: two theta array
        """
        min_tth, max_tth = self._get_cake_tth_range()
        return np.linspace(min_tth, max_tth, 2048)

    def _get_combined_cake_azi(self):
        """
        Gives an 1d array of azimuth values which covers the azimuth range of the cakes in all configurations.
        :return: two theta array
        """
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
        """
        :rtype: Pattern
        """
        if not self.combine_patterns:
            return self.pattern_model.pattern
        else:
            patterns = [configuration.pattern_model.pattern for configuration in self.configurations]
            return combine_patterns(patterns)

    @property
    def combine_patterns(self):
        """
        :rtype: bool
        """
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

    def reset(self):
        """
        Resets the state of the model. It only remembers the current working directories of the currently selected
        configuration. Everything else including all configurations is deleted.
        """
        working_directories = self.working_directories
        self.disconnect_models()
        self.delete_configurations()
        self.configurations = [Configuration()]
        self.configuration_ind = 0
        self.overlay_model.reset()
        self.phase_model.reset()
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
