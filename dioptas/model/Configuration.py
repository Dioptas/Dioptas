# -*- coding: utf8 -*-
import os
import numpy as np
from qtpy import QtCore

from copy import deepcopy

import h5py

from .util.ImgCorrection import CbnCorrection, ObliqueAngleDetectorAbsorptionCorrection

from .util import Pattern
from .util.calc import convert_units
from . import ImgModel, CalibrationModel, MaskModel, PatternModel


class Configuration(QtCore.QObject):
    cake_changed = QtCore.Signal()

    def __init__(self):
        super(Configuration, self).__init__()

        self.img_model = ImgModel()
        self.mask_model = MaskModel()
        self.calibration_model = CalibrationModel(self.img_model)
        self.pattern_model = PatternModel()

        self.working_directories =  {'calibration': '', 'mask': '', 'image': '', 'pattern': '', 'overlay': '',
                                    'phase': ''}

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
        new_configuration = Configuration(self.working_directories)
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
        image_group.attrs['background_filename'] = self.img_model.background_filename
        image_group.attrs['background_offset'] = self.img_model.background_offset
        image_group.attrs['background_scaling'] = self.img_model.background_scaling
        if self.img_model.has_background():
            background_data = self.img_model.background_data
            # remove image transformations
            for transformation in reversed(self.img_model.img_transformations):
                background_data = transformation(background_data)
            image_group.create_dataset('background_data', background_data.shape, 'f', background_data)

        # image corrections
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

        # the actual image
        image_group.attrs['filename'] = self.img_model.filename
        current_raw_image = np.copy(self.img_model.raw_img_data)
        # remove image transformations
        for transformation in reversed(self.img_model.img_transformations):
            current_raw_image = transformation(current_raw_image)

        raw_image_data = image_group.create_dataset('raw_image_data', current_raw_image.shape, dtype='f')
        raw_image_data[...] = current_raw_image

        # image transformations
        transformations_group = image_group.create_group('image_transformations')
        for ind, transformation in enumerate(self.img_model.get_transformations_string_list()):
            transformations_group.attrs[str(ind)] = transformation

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
            self.img_model.background_data = np.copy(f.get('image_model').get('background_data')[...])
            self.img_model.background_filename = f.get('image_model').attrs['background_filename']
            self.img_model.background_scaling = f.get('image_model').attrs['background_scaling']
            self.img_model.background_offset = f.get('image_model').attrs['background_offset']

        # load image transformations
        transformation_group = f.get('image_model').get('image_transformations')
        transformation_list = []
        for key, transformation in transformation_group.attrs.items():
            transformation_list.append(transformation)
        self.img_model.load_transformations_string_list(transformation_list)

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
