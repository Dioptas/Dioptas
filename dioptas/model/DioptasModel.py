# -*- coding: utf8 -*-
import os
import time
from scipy.interpolate import interp1d, interp2d
import numpy as np
from qtpy import QtCore

from copy import deepcopy

import h5py

from .util import Pattern, jcpds
from .util.ImgCorrection import CbnCorrection, ObliqueAngleDetectorAbsorptionCorrection

from .util import Pattern
from .util.calc import convert_units
from . import ImgModel, CalibrationModel, MaskModel, PhaseModel, PatternModel, OverlayModel


class ImgConfiguration(QtCore.QObject):
    cake_changed = QtCore.Signal()

    def __init__(self, working_directories=None):
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

        self._auto_integrate_pattern = True
        self._auto_integrate_cake = False

        self.auto_save_integrated_pattern = False
        self.integrated_patterns_file_formats = ['.xy']

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

            if self.auto_save_integrated_pattern:
                self._auto_save_patterns()

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

    def save_pattern(self, filename=None, subtract_background=False):
        if filename is None:
            filename = self.img_model.filename

        if filename.endswith('.xy'):
            self.pattern_model.save_pattern(filename, header=self._create_xy_header(),
                                            subtract_background=subtract_background)
        elif filename.endswith('.fxye'):
            self.pattern_model.save_pattern(filename, header=self._create_fxye_header(filename),
                                            subtract_background=subtract_background)
        else:
            self.pattern_model.save_pattern(filename, subtract_background=subtract_background)

    def _create_xy_header(self):
        header = self.calibration_model.create_file_header()
        header = header.replace('\r\n', '\n')
        header = header + '\n#\n# ' + self._integration_unit + '\t I'
        return header

    def _create_fxye_header(self, filename):
        header = 'Generated file ' + filename + ' using DIOPTAS\n'
        header = header + self.calibration_model.create_file_header()
        unit = self._integration_unit
        lam = self.calibration_model.wavelength
        if unit == 'q_A^-1':
            con = 'CONQ'
        else:
            con = 'CONS'

        header = header + '\nBANK\t1\tNUM_POINTS\tNUM_POINTS ' + con + '\tMIN_X_VAL\tSTEP_X_VAL ' + \
                 '{0:.5g}'.format(lam * 1e10) + ' 0.0 FXYE'
        return header

    def _auto_save_patterns(self):
        for file_ending in self.integrated_patterns_file_formats:
            filename = os.path.join(
                self.working_directories['pattern'],
                os.path.basename(str(self.img_model.filename)).split('.')[:-1][0] + file_ending)
            filename = filename.replace('\\', '/')
            self.save_pattern(filename)

        if self.pattern_model.pattern.has_background():
            for file_ending in self.integrated_patterns_file_formats:
                directory = os.path.join(self.working_directories['pattern'], 'bkg_subtracted')
                if not os.path.exists(directory):
                    os.mkdir(directory)
                filename = os.path.join(directory, self.pattern_model.pattern.name + file_ending)
                filename = filename.replace('\\', '/')
                self.save_pattern(filename, subtract_background=True)

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
    def integration_unit(self):
        return self._integration_unit

    @integration_unit.setter
    def integration_unit(self, new_unit):
        old_unit = self.integration_unit
        self._integration_unit = new_unit

        auto_bg_subtraction = self.pattern_model.pattern.auto_background_subtraction
        if auto_bg_subtraction:
            self.pattern_model.pattern.auto_background_subtraction = False

        self.integrate_image_1d()

        self.update_auto_background_parameters_unit(old_unit, new_unit)

        if auto_bg_subtraction:
            self.pattern_model.pattern.auto_background_subtraction = True
            self.pattern_model.pattern.recalculate_pattern()
            self.pattern_model.pattern_changed.emit()

    def update_auto_background_parameters_unit(self, old_unit, new_unit):
        self.pattern_model.pattern.auto_background_subtraction_parameters = \
            convert_units(self.pattern_model.pattern.auto_background_subtraction_parameters[0],
                          self.calibration_model.wavelength,
                          old_unit,
                          new_unit), \
            self.pattern_model.pattern.auto_background_subtraction_parameters[1], \
            self.pattern_model.pattern.auto_background_subtraction_parameters[2]

        if self.pattern_model.pattern.auto_background_subtraction_roi is not None:
            self.pattern_model.pattern.auto_background_subtraction_roi = \
                convert_units(self.pattern_model.pattern.auto_background_subtraction_roi[0],
                              self.calibration_model.wavelength,
                              old_unit,
                              new_unit), \
                convert_units(self.pattern_model.pattern.auto_background_subtraction_roi[1],
                              self.calibration_model.wavelength,
                              old_unit,
                              new_unit)

    @property
    def auto_integrate_cake(self):
        return self._auto_integrate_cake

    @auto_integrate_cake.setter
    def auto_integrate_cake(self, new_value):
        if self._auto_integrate_cake == new_value:
            return

        self._auto_integrate_cake = new_value
        if new_value:
            self.img_model.img_changed.connect(self.integrate_image_2d)
        else:
            self.img_model.img_changed.disconnect(self.integrate_image_2d)

    @property
    def auto_integrate_pattern(self):
        return self._auto_integrate_pattern

    @auto_integrate_pattern.setter
    def auto_integrate_pattern(self, new_value):
        if self._auto_integrate_pattern == new_value:
            return

        self._auto_integrate_pattern = new_value
        if new_value:
            self.img_model.img_changed.connect(self.integrate_image_1d)
        else:
            self.img_model.img_changed.disconnect(self.integrate_image_1d)

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

    def save_in_hdf5(self, hdf5_group):
        """
        Saves the configuration group in the given hdf5_group.
        :type hdf5_group: h5py.Group
        """

        f = hdf5_group
        # save general information
        general_information = f.create_group('general_information')
        general_information.attrs['integration_unit'] = self.integration_unit
        if self.integration_num_points:
            general_information.attrs['integration_num_points'] = self.integration_num_points
        else:
            general_information.attrs['integration_num_points'] = 0
        general_information.attrs['auto_integrate_cake'] = self.auto_integrate_cake
        general_information.attrs['use_mask'] = self.use_mask
        general_information.attrs['transparent_mask'] = self.transparent_mask
        general_information.attrs['auto_save_integrated_pattern'] = self.auto_save_integrated_pattern
        formats = [n.encode('ascii', 'ignore') for n in self.integrated_patterns_file_formats]
        general_information.create_dataset('integrated_patterns_file_formats', (len(formats), 1), 'S10', formats)

        # save working directories
        working_directories_gp = f.create_group('working_directories')
        try:
            for key in self.working_directories:
                working_directories_gp.attrs[key] = self.working_directories[key]
        except TypeError:
            self.working_directories = {'calibration': '', 'mask': '', 'image': '', 'pattern': '', 'overlay': '',
                                        'phase': ''}
            for key in self.working_directories:
                working_directories_gp.attrs[key] = self.working_directories[key]

        # save image model
        image_group = f.create_group('image_model')
        image_group.attrs['auto_process'] = self.img_model.autoprocess
        image_group.attrs['factor'] = self.img_model.factor
        image_group.attrs['has_background'] = self.img_model.has_background()
        image_group.attrs['background_offset'] = self.img_model.background_offset
        image_group.attrs['background_scaling'] = self.img_model.background_scaling
        background_data = self.img_model.background_data
        if self.img_model.has_background():
            image_group.create_dataset('background_data', background_data.shape, 'f', background_data)

        corrections_group = image_group.create_group('corrections')
        corrections_group.attrs['has_corrections'] = self.img_model.has_corrections()
        for correction, correction_object in self.img_model.img_corrections.corrections.items():
            correction_data = correction_object.get_data()
            imcd = corrections_group.create_dataset(correction, correction_data.shape, 'f', correction_data)
            if correction == 'cbn':
                for param, value in correction_object.get_params().items():
                    imcd.attrs[param] = value
            elif correction == 'oiadac':
                for param, value in correction_object.get_params().items():
                    imcd.attrs[param] = value

        image_group.attrs['filename'] = self.img_model.filename
        current_raw_image = self.img_model.raw_img_data
        raw_image_data = image_group.create_dataset('raw_image_data', current_raw_image.shape, dtype='f')
        raw_image_data[...] = current_raw_image

        # save roi data
        if self.roi is not None:
            image_group.attrs['has_roi'] = True
            image_group.create_dataset('roi', (4,), 'i8', tuple(self.roi))
        else:
            image_group.attrs['has_roi'] = False

        # save mask model
        mask_group = f.create_group('mask')
        current_mask = self.mask_model.get_mask()
        mask_data = mask_group.create_dataset('data', current_mask.shape, dtype=bool)
        mask_data[...] = current_mask

        # save calibration model
        calibration_group = f.create_group('calibration_model')
        calibration_filename = self.calibration_model.filename
        if calibration_filename.endswith('.poni'):
            base_filename, ext = self.calibration_model.filename.rsplit('.', 1)
        else:
            base_filename = self.calibration_model.filename
            ext = 'poni'
        calibration_group.attrs['calibration_filename'] = base_filename + '.' + ext
        pyfai_param, fit2d_param = self.calibration_model.get_calibration_parameter()
        pfp = calibration_group.create_group('pyfai_parameters')
        for key in pyfai_param:
            try:
                pfp.attrs[key] = pyfai_param[key]
            except TypeError:
                pfp.attrs[key] = ''

        # save background pattern and pattern model
        background_pattern_group = f.create_group('background_pattern')
        try:
            background_pattern_x = self.pattern_model.background_pattern.original_x
            background_pattern_y = self.pattern_model.background_pattern.original_y
        except (TypeError, AttributeError):
            background_pattern_x = None
            background_pattern_y = None
        if background_pattern_x is not None and background_pattern_y is not None:
            background_pattern_group.attrs['has_background_pattern'] = True
            bgx = background_pattern_group.create_dataset('x', background_pattern_x.shape, dtype='f')
            bgy = background_pattern_group.create_dataset('y', background_pattern_y.shape, dtype='f')
            bgx[...] = background_pattern_x
            bgy[...] = background_pattern_y
        else:
            background_pattern_group.attrs['has_background_pattern'] = False

        pattern_group = f.create_group('pattern')
        try:
            pattern_x = self.pattern_model.pattern.original_x
            pattern_y = self.pattern_model.pattern.original_y
        except (TypeError, AttributeError):
            pattern_x = None
            pattern_y = None
        if pattern_x is not None and pattern_y is not None:
            px = pattern_group.create_dataset('x', pattern_x.shape, dtype='f')
            py = pattern_group.create_dataset('y', pattern_y.shape, dtype='f')
            px[...] = pattern_x
            py[...] = pattern_y
        pattern_group.attrs['pattern_filename'] = self.pattern_model.pattern_filename
        pattern_group.attrs['unit'] = self.pattern_model.unit
        pattern_group.attrs['file_iteration_mode'] = self.pattern_model.file_iteration_mode
        if self.pattern_model.pattern.auto_background_subtraction:
            pattern_group.attrs['auto_background_subtraction'] = True
            auto_background_group = pattern_group.create_group('auto_background_settings')
            auto_background_group.attrs['smoothing'] = \
                self.pattern_model.pattern.auto_background_subtraction_parameters[0]
            auto_background_group.attrs['iterations'] = \
                self.pattern_model.pattern.auto_background_subtraction_parameters[1]
            auto_background_group.attrs['poly_order'] = \
                self.pattern_model.pattern.auto_background_subtraction_parameters[2]
            auto_background_group.attrs['x_start'] = self.pattern_model.pattern.auto_background_subtraction_roi[0]
            auto_background_group.attrs['x_end'] = self.pattern_model.pattern.auto_background_subtraction_roi[1]
        else:
            pattern_group.attrs['auto_background_subtraction'] = False

    def load_from_hdf5(self, hdf5_group):
        """
        loads a configuration from the specified hdf5_group.
        :type hdf5_group: h5py.Group
        """

        f = hdf5_group

        # disable all automatic functions
        self.auto_integrate_pattern = False
        self.auto_integrate_cake = False
        self.auto_save_integrated_pattern = False

        # get working directories
        working_directories = {}
        for key, value in f.get('working_directories').attrs.items():
            if os.path.isdir(value):
                working_directories[key] = value
            else:
                working_directories[key] = ''
        self.working_directories = working_directories

        # load pyFAI parameters
        pyfai_parameters = {}
        for key, value in f.get('calibration_model').get('pyfai_parameters').attrs.items():
            pyfai_parameters[key] = value

        try:
            self.calibration_model.set_pyFAI(pyfai_parameters)
            filename = f.get('calibration_model').attrs['calibration_filename']
            (file_path, base_name) = os.path.split(filename)
            self.calibration_model.filename = filename
            self.calibration_model.calibration_name = base_name

        except (KeyError, ValueError):
            print('Problem with saved pyFAI calibration parameters')
            pass

        # load img_model
        self.img_model._img_data = np.copy(f.get('image_model').get('raw_image_data')[...])
        filename = f.get('image_model').attrs['filename']
        self.img_model.filename = filename

        self.img_model.autoprocess = f.get('image_model').attrs['auto_process']
        self.img_model.autoprocess_changed.emit()
        self.img_model.factor = f.get('image_model').attrs['factor']

        if f.get('image_model').attrs['has_background']:
            self.img_model.background_data = f.get('image_model').get('background_data')
            self.img_model.background_scaling = f.get('image_model').attrs['background_scaling']
            self.img_model.background_offset = f.get('image_model').attrs['background_offset']

        # load roi data
        if f.get('image_model').attrs['has_roi']:
            self.roi = tuple(f.get('image_model').get('roi')[...])

        # load mask model
        self.mask_model.set_mask(np.copy(f.get('mask').get('data')[...]))

        # load pattern model
        if f.get('pattern').get('x') and f.get('pattern').get('y'):
            self.pattern_model.set_pattern(f.get('pattern').get('x')[...],
                                           f.get('pattern').get('y')[...],
                                           f.get('pattern').attrs['pattern_filename'],
                                           f.get('pattern').attrs['unit'])
            self.pattern_model.file_iteration_mode = f.get('pattern').attrs['file_iteration_mode']

        if f.get('background_pattern').attrs['has_background_pattern']:
            self.pattern_model.background_pattern = Pattern(f.get('background_pattern').get('x')[...],
                                                            f.get('background_pattern').get('y')[...],
                                                            'background_pattern')

        if f.get('pattern').attrs['auto_background_subtraction']:
            bg_params = []
            bg_roi = []
            bg_params.append(f.get('pattern').get('auto_background_settings').attrs['smoothing'])
            bg_params.append(f.get('pattern').get('auto_background_settings').attrs['iterations'])
            bg_params.append(f.get('pattern').get('auto_background_settings').attrs['poly_order'])
            bg_roi.append(f.get('pattern').get('auto_background_settings').attrs['x_start'])
            bg_roi.append(f.get('pattern').get('auto_background_settings').attrs['x_end'])
            self.pattern_model.pattern.set_auto_background_subtraction(bg_params, bg_roi,
                                                                       recalc_pattern=False)

        # load general configuration
        self.integration_unit = f.get('general_information').attrs['integration_unit']
        if f.get('general_information').attrs['integration_num_points']:
            self.integration_num_points = f.get('general_information').attrs['integration_num_points']

        self.auto_integrate_cake = f.get('general_information').attrs['auto_integrate_cake']
        self.use_mask = f.get('general_information').attrs['use_mask']
        self.transparent_mask = f.get('general_information').attrs['transparent_mask']

        self.auto_save_integrated_pattern = f.get('general_information').attrs['auto_save_integrated_pattern']
        self.integrated_patterns_file_formats = []
        for file_format in f.get('general_information').get('integrated_patterns_file_formats'):
            self.integrated_patterns_file_formats.append(file_format[0].decode('utf-8'))

        self.integrate_image_1d()

        if f.get('image_model').get('corrections').attrs['has_corrections']:
            for name, correction_group in f.get('image_model').get('corrections').items():
                if name == 'cbn':
                    tth_array = 180.0 / np.pi * self.calibration_model.pattern_geometry.ttha
                    azi_array = 180.0 / np.pi * self.calibration_model.pattern_geometry.chia
                    cbn_correction = CbnCorrection(tth_array=tth_array, azi_array=azi_array)
                    params = {}
                    for param, val in correction_group.attrs.items():
                        params[param] = val
                    cbn_correction.set_params(params)
                    cbn_correction.update()
                    self.img_model.add_img_correction(cbn_correction, name, name)
                elif name == 'oiadac':
                    tth_array = 180.0 / np.pi * self.calibration_model.pattern_geometry.ttha
                    azi_array = 180.0 / np.pi * self.calibration_model.pattern_geometry.chia
                    oiadac = ObliqueAngleDetectorAbsorptionCorrection(tth_array=tth_array, azi_array=azi_array)
                    params = {}
                    for param, val in correction_group.attrs.items():
                        params[param] = val
                    oiadac.set_params(params)
                    oiadac.update()
                    self.img_model.add_img_correction(oiadac, name, name)


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
        self.configurations.append(ImgConfiguration())
        self.working_directories = working_directories

        self._overlay_model = OverlayModel()
        self._phase_model = PhaseModel()

        self._combine_patterns = False
        self._combine_cakes = False
        self._cake_data = None

        self.connect_models()

    def add_configuration(self):
        self.configurations.append(ImgConfiguration(self.working_directories))

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
            configuration = ImgConfiguration()
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
