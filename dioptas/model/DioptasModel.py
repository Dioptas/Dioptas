# -*- coding: utf8 -*-
import os

from scipy.interpolate import interp1d, interp2d
import numpy as np
from qtpy import QtCore

from copy import deepcopy

import h5py

from .util import Pattern, jcpds

from . import ImgModel, CalibrationModel, MaskModel, PhaseModel, PatternModel, OverlayModel


class ImgConfiguration(QtCore.QObject):
    cake_changed = QtCore.Signal()
    autosave_integrated_pattern_changed = QtCore.Signal()
    integrated_patterns_file_formats_changed = QtCore.Signal()

    def __init__(self, working_directories):
        super(ImgConfiguration, self).__init__()

        self.img_model = ImgModel()
        self.mask_model = MaskModel()
        self.calibration_model = CalibrationModel(self.img_model)
        self.pattern_model = PatternModel()

        if working_directories is not None:
            self.working_directories = working_directories
        else:
            self.working_directories = {}

        self.use_mask = False

        self.transparent_mask = False

        self._integration_num_points = None
        self._integration_azimuth_points = 2048
        self._integration_unit = '2th_deg'

        self._integrate_cake = False

        self._autosave_integrated_pattern = False
        self._integrated_patterns_file_formats = ['.xy']

        self.connect_signals()

    def connect_signals(self):
        self.img_model.img_changed.connect(self.update_mask_dimension)
        self.img_model.img_changed.connect(self.integrate_image_1d)

    def integrate_image_1d(self):
        if self.calibration_model.is_calibrated:
            if self.use_mask:
                if self.mask_model.supersampling_factor != self.img_model.supersampling_factor:
                    self.mask_model.set_supersampling(self.img_model.supersampling_factor)
                mask = self.mask_model.get_mask()
            elif self.mask_model.roi is not None:
                mask = self.mask_model.roi_mask
            else:
                mask = None

            x, y = self.calibration_model.integrate_1d(mask=mask, unit=self.integration_unit,
                                                       num_points=self.integration_num_points)

            self.pattern_model.set_pattern(x, y, self.img_model.filename, unit=self.integration_unit)  #

            if self.autosave_integrated_pattern:
                self.save_pattern()

    def integrate_image_2d(self):
        if self.use_mask:
            if self.mask_model.supersampling_factor != self.img_model.supersampling_factor:
                self.mask_model.set_supersampling(self.img_model.supersampling_factor)
            mask = self.mask_model.get_mask()
        elif self.mask_model.roi is not None:
            mask = self.mask_model.roi_mask
        else:
            mask = None

        self.calibration_model.integrate_2d(mask=mask,
                                            dimensions=(2048, 2048))
        self.cake_changed.emit()

    def save_pattern(self):
        filename = self.img_model.filename
        for file_ending in self.integrated_patterns_file_formats:
            if filename is not '':
                filename = os.path.join(
                    self.working_directories['spectrum'],
                    os.path.basename(str(self.img_model.filename)).split('.')[:-1][0] + file_ending)
                filename = filename.replace('\\', '/')
            if file_ending == '.xy':
                self.pattern_model.save_pattern(filename, header=self._create_xy_header())
            else:
                self.pattern_model.save_pattern(filename)

        if self.pattern_model.pattern.has_background():
            for file_ending in self.integrated_patterns_file_formats:
                directory = os.path.join(self.working_directories['spectrum'], 'bkg_subtracted')
                if not os.path.exists(directory):
                    os.mkdir(directory)
                filename = os.path.join(directory, self.pattern_model.pattern.name + file_ending)
                filename = filename.replace('\\', '/')
                if file_ending == '.xy':
                    self.pattern_model.save_pattern(filename, header=self._create_xy_header(),
                                                    subtract_background=True)
                else:
                    self.pattern_model.save_pattern(filename, subtract_background=True)

    def _create_xy_header(self):
        header = self.calibration_model.create_file_header()
        header = header.replace('\r\n', '\n')
        header = header + '\n#\n# ' + self._integration_unit + '\t I'
        return header

    def update_mask_dimension(self):
        self.mask_model.set_dimension(self.img_model._img_data.shape)

    @property
    def integration_num_points(self):
        return self._integration_num_points

    @integration_num_points.setter
    def integration_num_points(self, new_value):
        self._integration_num_points = new_value
        self.integrate_image_1d()

    @property
    def autosave_integrated_pattern(self):
        return self._autosave_integrated_pattern

    @autosave_integrated_pattern.setter
    def autosave_integrated_pattern(self, new_value):
        self._autosave_integrated_pattern = new_value
        self.autosave_integrated_pattern_changed.emit()

    @property
    def integrated_patterns_file_formats(self):
        return self._integrated_patterns_file_formats

    @integrated_patterns_file_formats.setter
    def integrated_patterns_file_formats(self, new_value):
        self._integrated_patterns_file_formats = list(new_value)
        self.integrated_patterns_file_formats_changed.emit()

    @property
    def integration_unit(self):
        return self._integration_unit

    @integration_unit.setter
    def integration_unit(self, new_value):
        self._integration_unit = new_value
        self.integrate_image_1d()

    @property
    def integrate_cake(self):
        return self._integrate_cake

    @integrate_cake.setter
    def integrate_cake(self, new_value):
        self._integrate_cake = new_value
        if new_value:
            self.img_model.img_changed.connect(self.integrate_image_2d)
        else:
            self.img_model.img_changed.disconnect(self.integrate_image_2d)

    @property
    def cake_img(self):
        return self.calibration_model.cake_img

    @property
    def roi(self):
        return self.mask_model.roi

    @roi.setter
    def roi(self, new_val):
        self.mask_model.roi = new_val
        self.integrate_image_1d()

    def copy(self):
        new_configuration = ImgConfiguration(self.working_directories)
        new_configuration.img_model._img_data = self.img_model._img_data
        new_configuration.img_model.img_transformations = deepcopy(self.img_model.img_transformations)

        new_configuration.calibration_model.set_pyFAI(self.calibration_model.get_calibration_parameter()[0])
        new_configuration.integrate_image_1d()

        return new_configuration


class DioptasModel(QtCore.QObject):
    configuration_added = QtCore.Signal()
    configuration_selected = QtCore.Signal(int)  # new index
    configuration_removed = QtCore.Signal(int)  # removed index

    img_changed = QtCore.Signal()
    pattern_changed = QtCore.Signal()
    cake_changed = QtCore.Signal()
    use_mask_changed = QtCore.Signal()
    transparent_mask_changed = QtCore.Signal()

    def __init__(self, working_directories=None):
        super(DioptasModel, self).__init__()
        self.working_directories = working_directories
        self.configurations = []
        self.configuration_ind = 0
        self.configurations.append(ImgConfiguration(self.working_directories))

        self._overlay_model = OverlayModel()
        self._phase_model = PhaseModel()

        self._combine_patterns = False
        self._combine_cakes = False
        self._cake_data = None

        self.connect_models()

    def add_configuration(self):
        self.configurations.append(ImgConfiguration(self.working_directories))
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

    def save_configuration(self, filename):
        if filename is '' or filename is None:
            return
        # print(self.current_configuration.roi)
        # im.attrs['img_correction'] = self.current_configuration.img_model.get_img_correction()

        f = h5py.File(filename, 'w')

        cc = f.create_group('current_config')
        cc.attrs['integration_unit'] = self.current_configuration.integration_unit
        if self.current_configuration.integration_num_points:
            cc.attrs['integration_num_points'] = self.current_configuration.integration_num_points
        else:
            cc.attrs['integration_num_points'] = 0
        cc.attrs['integrate_cake'] = self.current_configuration.integrate_cake
        cc.attrs['use_mask'] = self.use_mask
        cc.attrs['transparent_mask'] = self.transparent_mask
        cc.attrs['autosave_integrated_pattern'] = self.current_configuration.autosave_integrated_pattern
        formats = [n.encode("ascii", "ignore") for n in self.current_configuration.integrated_patterns_file_formats]
        cc.create_dataset('integrated_patterns_file_formats', (len(formats), 1), 'S10', formats)

        wd = f.create_group('working_directories')
        try:
            for key in self.working_directories:
                wd.attrs[key] = self.working_directories[key]
        except TypeError:
            self.working_directories = {'calibration': '', 'mask': '', 'image': '', 'spectrum': '', 'overlay': '',
                                        'phase': ''}
            for key in self.working_directories:
                wd.attrs[key] = self.working_directories[key]

        im = f.create_group('image_model')
        im.attrs['auto_process'] = self.current_configuration.img_model.autoprocess
        im.attrs['factor'] = self.current_configuration.img_model.factor
        im.attrs['has_background'] = self.current_configuration.img_model.has_background()
        im.attrs['background_offset'] = self.current_configuration.img_model.background_offset
        im.attrs['background_scaling'] = self.current_configuration.img_model.background_scaling
        background_data = self.current_configuration.img_model.background_data
        if self.current_configuration.img_model.has_background():
            im.create_dataset('background_data', background_data.shape, 'f', background_data)

        (base_filename, ext) = self.current_configuration.img_model.filename.rsplit('.', 1)
        im.attrs['filename'] = base_filename + '_temp.' + ext
        current_raw_image = self.current_configuration.img_model.raw_img_data
        raw_image_data = im.create_dataset("raw_image_data", current_raw_image.shape, dtype='f')
        raw_image_data[...] = current_raw_image

        mm = f.create_group('mask_model')
        current_mask = self.current_configuration.mask_model.get_mask()
        mask_data = mm.create_dataset('mask_data', current_mask.shape, dtype=bool)
        mask_data[...] = current_mask
        cm = f.create_group('calibration_model')
        calibration_filename = self.current_configuration.calibration_model.filename
        if calibration_filename.endswith('.poni'):
            base_filename, ext = self.current_configuration.calibration_model.filename.rsplit('.', 1)
        else:
            base_filename = self.current_configuration.calibration_model.filename
            ext = 'poni'
        cm.attrs['calibration_filename'] = base_filename + '_temp.' + ext
        pyfai_param, fit2d_param = self.current_configuration.calibration_model.get_calibration_parameter()
        pfp = cm.create_group('pyfai_parameters')
        for key in pyfai_param:
            try:
                pfp.attrs[key] = pyfai_param[key]
            except TypeError:
                pfp.attrs[key] = ''
        # maybe don't need these:
        # cm.attrs['wavelength'] = self.calibration_model.wavelength
        # cm.attrs['num_points'] = self.calibration_model.num_points

        bpm = f.create_group('background_pattern')
        try:
            background_pattern_x = self.current_configuration.pattern_model.background_pattern.original_x
            background_pattern_y = self.current_configuration.pattern_model.background_pattern.original_y
        except (TypeError, AttributeError):
            background_pattern_x = None
            background_pattern_y = None
        if background_pattern_x is not None and background_pattern_y is not None:
            bgx = bpm.create_dataset("background_pattern_x", background_pattern_x.shape, dtype='f')
            bgy = bpm.create_dataset("background_pattern_y", background_pattern_y.shape, dtype='f')
            bgx[...] = background_pattern_x
            bgy[...] = background_pattern_y

        pm = f.create_group('pattern')
        try:
            pattern_x = self.current_configuration.pattern_model.pattern.original_x
            pattern_y = self.current_configuration.pattern_model.pattern.original_y
        except (TypeError, AttributeError):
            pattern_x = None
            pattern_y = None
        if pattern_x is not None and pattern_y is not None:
            px = pm.create_dataset('pattern_x', pattern_x.shape, dtype='f')
            py = pm.create_dataset('pattern_y', pattern_y.shape, dtype='f')
            px[...] = pattern_x
            py[...] = pattern_y
        pm.attrs['pattern_filename'] = self.current_configuration.pattern_model.pattern_filename
        pm.attrs['unit'] = self.current_configuration.pattern_model.unit
        pm.attrs['file_iteration_mode'] = self.current_configuration.pattern_model.file_iteration_mode

        ovs = f.create_group('overlay_model')
        for overlay in self.overlay_model.overlays:
            ov = ovs.create_group('overlay_' + overlay.name)
            ov.attrs['overlay_name'] = overlay.name
            overlay_x_data = overlay.original_x
            overlay_y_data = overlay.original_y
            ov.create_dataset('overlay_x_data', overlay_x_data.shape, 'f', overlay_x_data)
            ov.create_dataset('overlay_y_data', overlay_y_data.shape, 'f', overlay_y_data)
            ov.attrs['scaling'] = overlay.scaling
            ov.attrs['offset'] = overlay.offset

        phm = f.create_group('phase_model')
        for phase in self.phase_model.phases:
            ph = phm.create_group('phase_' + phase.name)
            ph.attrs['name'] = phase.name
            ph.attrs['filename'] = phase.filename
            phpars = ph.create_group('params')
            for key in phase.params:
                if key == 'comments':
                    phc = ph.create_group('comments')
                    ind = 0
                    for comment in phase.params['comments']:
                        phc.attrs['comment_' + str(ind)] = comment
                        ind += 1
                else:
                    phpars.attrs[key] = phase.params[key]
            phrefs = ph.create_group('reflections')
            ind = 0
            for reflection in phase.reflections:
                phref = phrefs.create_group('reflection_' + str(ind))
                phref.attrs['d0'] = reflection.d0
                phref.attrs['d'] = reflection.d
                phref.attrs['intensity'] = reflection.intensity
                phref.attrs['h'] = reflection.h
                phref.attrs['k'] = reflection.k
                phref.attrs['l'] = reflection.l
                ind += 1

        f.flush()
        f.close()

    def load_configuration(self, filename):
        if filename is '' or filename is None:
            return
        f = h5py.File(filename, 'r')
        temp_path = os.path.join(os.getcwd(), 'temp')
        if not os.path.isdir(temp_path):
            os.mkdir(temp_path)
        working_directories = {'temp': temp_path}
        for key, value in f.get('working_directories').attrs.items():
            if os.path.isdir(value):
                working_directories[key] = value
            else:
                working_directories[key] = temp_path
        self.working_directories = working_directories
        pyfai_parameters = {}
        for key, value in f.get('calibration_model').get('pyfai_parameters').attrs.items():
            pyfai_parameters[key] = value

        try:
            self.current_configuration.calibration_model.set_pyFAI(pyfai_parameters)
            self.current_configuration.calibration_model.save(f.get('calibration_model').attrs['calibration_filename'])
        except (KeyError, ValueError):
            print("Problem with saved pyFAI calibration parameters")
            pass

        self.current_configuration.integration_unit = f.get('current_config').attrs['integration_unit']
        if f.get('current_config').attrs['integration_num_points']:
            self.current_configuration.integration_num_points = f.get('current_config').attrs['integration_num_points']
        # self.current_configuration.integrate_cake = f.get('current_config').attrs['integrate_cake']
        self.use_mask = f.get('current_config').attrs['use_mask']
        self.use_mask_changed.emit()
        self.transparent_mask = f.get('current_config').attrs['transparent_mask']
        self.transparent_mask_changed.emit()
        self.current_configuration.mask_model.save_mask(os.path.join(self.working_directories['temp'], 'temp_mask.mask'))

        self.current_configuration.autosave_integrated_pattern = \
            f.get('current_config').attrs['autosave_integrated_pattern']
        self.current_configuration.integrated_patterns_file_formats = []
        file_formats = []
        for file_format in f.get('current_config').get('integrated_patterns_file_formats'):
            file_formats.append(file_format[0].decode("utf-8"))
        self.current_configuration.integrated_patterns_file_formats = file_formats

        self.current_configuration.img_model._img_data = np.copy(f.get('image_model').get('raw_image_data')[...])
        filename = f.get('image_model').attrs['filename']
        (file_path, base_name) = os.path.split(filename)
        filename = os.path.join(self.working_directories['temp'], base_name)
        self.current_configuration.img_model.save(filename)

        self.current_configuration.img_model.autoprocess = f.get('image_model').attrs['auto_process']
        self.current_configuration.img_model.autoprocess_changed.emit()
        self.current_configuration.img_model.load(filename)
        self.current_configuration.img_model.factor = f.get('image_model').attrs['factor']
        if f.get('image_model').attrs['has_background']:
            self.current_configuration.img_model.background_data = f.get('image_model').get('background_data')
            self.current_configuration.img_model.background_scaling = f.get('image_model').attrs['background_scaling']
            self.current_configuration.img_model.background_offset = f.get('image_model').attrs['background_offset']

        self.current_configuration.mask_model.set_mask(np.copy(f.get('mask_model').get('mask_data')[...]))

        if f.get('pattern').get('pattern_x') and f.get('pattern').get('pattern_y'):
            self.current_configuration.pattern_model.set_pattern(f.get('pattern').get('pattern_x')[...],
                                                                 f.get('pattern').get('pattern_y')[...],
                                                                 f.get('pattern').attrs['pattern_filename'],
                                                                 f.get('pattern').attrs['unit'])
            self.current_configuration.pattern_model.file_iteration_mode = f.get('pattern').attrs['file_iteration_mode']

        if f.get('background_pattern') and f.get('background_pattern').get('background_pattern_x'):
            bg_pattern = self.overlay_model.add_overlay(f.get('background_pattern').get('background_pattern_x')[...],
                                                        f.get('background_pattern').get('background_pattern_y')[...],
                                                        'background_pattern')
            self.current_configuration.pattern_model.background_pattern = bg_pattern

        def load_overlay_from_configuration(name):
            if isinstance(f.get('overlay_model').get(name), h5py.Group):
                self.overlay_model.add_overlay(f.get('overlay_model').get(name).get('overlay_x_data')[...],
                                               f.get('overlay_model').get(name).get('overlay_y_data')[...],
                                               f.get('overlay_model').get(name).attrs['overlay_name'])
                ind = len(self.overlay_model.overlays) - 1
                self.overlay_model.set_overlay_offset(ind, f.get('overlay_model').get(name).attrs['offset'])
                self.overlay_model.set_overlay_scaling(ind, f.get('overlay_model').get(name).attrs['scaling'])

        f.get('overlay_model').visit(load_overlay_from_configuration)

        def load_phase_from_configuration(name):
            if isinstance(f.get('phase_model').get(name), h5py.Group):
                no_file = False
                p_filename = f.get('phase_model').get(name).attrs.get('filename', None)
                if p_filename is not None:
                    if os.path.isfile(p_filename):
                        if p_filename.endswith('.jcpds'):
                            self.phase_model.add_jcpds(p_filename)
                        elif p_filename.endswith('.cif'):
                            self.phase_model.add_cif(p_filename)
                        ind = len(self.phase_model.phases) - 1
                        for p_key, p_value in f.get('phase_model').get(name).get('params').attrs.items():
                            self.phase_model.phases[ind].params[p_key] = p_value
                        for c_key, c_value in f.get('phase_model').get(name).get('comments').attrs.items():
                            self.phase_model.phases[ind].params['comments'].append(c_value)
                    else:
                        no_file = True
                        new_jcpds = jcpds()
                        for p_key, p_value in f.get('phase_model').get(name).get('params').attrs.items():
                            new_jcpds.params[p_key] = p_value
                        for c_key, c_value in f.get('phase_model').get(name).get('comments').attrs.items():
                            new_jcpds.params['comments'].append(c_value)
                        for r_key, r_value in f.get('phase_model').get(name).get('reflections').items():
                            ref = f.get('phase_model').get(name).get('reflections').get(r_key)
                            new_jcpds.add_reflection(ref.attrs['h'], ref.attrs['k'], ref.attrs['l'],
                                                     ref.attrs['intensity'], ref.attrs['d'])
                        (p_path, p_base_name) = os.path.split(p_filename)
                        new_jcpds.save_file(os.path.join(self.working_directories['temp'], p_base_name))
                        ind = len(self.phase_model.phases) - 1
                        self.phase_model.phases.append(new_jcpds)
                        self.phase_model.reflections.append([])

                    self.phase_model.phases[ind].compute_d()
                    self.phase_model.send_added_signal()

        f.get('phase_model').visit(load_phase_from_configuration)

        f.close()

    def select_configuration(self, ind):
        if 0 <= ind < len(self.configurations):
            self.disconnect_models()
            self.configuration_ind = ind
            self.connect_models()
            self.configuration_selected.emit(ind)
            self.img_model.img_changed.disconnect(self.current_configuration.integrate_image_1d)
            if self.combine_cakes:
                self.img_model.img_changed.disconnect(self.current_configuration.integrate_image_2d)
            self.img_changed.emit()
            self.img_model.img_changed.connect(self.current_configuration.integrate_image_1d)
            if self.combine_cakes:
                self.img_model.img_changed.connect(self.current_configuration.integrate_image_2d)
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
    def current_configuration(self):
        """
        :rtype: ImgConfiguration
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
            if not configuration.integrate_cake:
                configuration.integrate_cake = True
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
            del configuration.calibration_model.spectrum_geometry
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
