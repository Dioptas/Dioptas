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
import numpy as np

from copy import deepcopy

import h5py

from .util import Signal
from .util.ImgCorrection import CbnCorrection, ObliqueAngleDetectorAbsorptionCorrection

from .util import Pattern
from .util.calc import convert_units
from . import ImgModel, CalibrationModel, MaskModel, PatternModel, BatchModel
from .CalibrationModel import DetectorModes


class Configuration(object):
    """
    The configuration class contains a working combination of an ImgModel, PatternModel, MaskModel and CalibrationModel.
    It does handles the core data manipulation of Dioptas.
    The management of multiple Configurations is done by the DioptasModel.
    """

    def __init__(self, working_directories=None):
        super(Configuration, self).__init__()

        self.img_model = ImgModel()
        self.mask_model = MaskModel()
        self.calibration_model = CalibrationModel(self.img_model)
        self.batch_model = BatchModel(self.calibration_model, self.mask_model)
        self.pattern_model = PatternModel()

        if working_directories is None:
            self.working_directories = {'calibration': '', 'mask': '', 'image': os.path.expanduser("~"), 'pattern': '',
                                        'overlay': '', 'phase': '', 'batch': os.path.expanduser("~")}
        else:
            self.working_directories = working_directories

        self.use_mask = False

        self.transparent_mask = False

        self._integration_rad_points = None
        self._integration_unit = '2th_deg'
        self._oned_azimuth_range = None

        self._cake_azimuth_points = 360
        self._cake_azimuth_range = None

        self._auto_integrate_pattern = True
        self._auto_integrate_cake = False

        self.auto_save_integrated_pattern = False
        self.integrated_patterns_file_formats = ['.xy']

        self.cake_changed = Signal()
        self._connect_signals()

    def _connect_signals(self):
        """
        Connects the img_changed signal to responding functions.
        """
        self.img_model.img_changed.connect(self.update_mask_dimension)
        self.img_model.img_changed.connect(self.integrate_image_1d)

    def integrate_image_1d(self):
        """
        Integrates the image in the ImageModel to a Pattern. Will also automatically save the integrated pattern, if
        auto_save_integrated is True.
        """
        if self.calibration_model.is_calibrated:
            if self.use_mask:
                mask = self.mask_model.get_mask()
            elif self.mask_model.roi is not None:
                mask = self.mask_model.roi_mask
            else:
                mask = None

            x, y = self.calibration_model.integrate_1d(azi_range=self.oned_azimuth_range, mask=mask, unit=self.integration_unit,
                                                       num_points=self.integration_rad_points)

            self.pattern_model.set_pattern(x, y, self.img_model.filename, unit=self.integration_unit)  #

            if self.auto_save_integrated_pattern:
                self._auto_save_patterns()

    def integrate_image_2d(self):
        """
        Integrates the image in the ImageModel to a Cake.
        """
        if self.use_mask:
            mask = self.mask_model.get_mask()
        elif self.mask_model.roi is not None:
            mask = self.mask_model.roi_mask
        else:
            mask = None

        self.calibration_model.integrate_2d(mask=mask,
                                            rad_points=self._integration_rad_points,
                                            azimuth_points=self._cake_azimuth_points,
                                            azimuth_range=self._cake_azimuth_range)

        self.cake_changed.emit()

    def save_pattern(self, filename=None, subtract_background=False):
        """
        Saves the current integrated pattern. The format depends on the file ending. Possible file formats:
            [*.xy, *.chi, *.dat, *.fxye]
        :param filename: where to save the file
        :param subtract_background: flat whether the pattern should be saved with or without subtracted background
        """
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

    def save_background_pattern(self, filename=None):
        """
        Saves the current fit background as a pattern. The format depends on the file ending. Possible file formats:
            [*.xy, *.chi, *.dat, *.fxye]
        """
        if filename is None:
            filename = self.img_model.filename

        if filename.endswith('.xy'):
            self.pattern_model.save_auto_background_as_pattern(filename, header=self._create_xy_header())
        elif filename.endswith('.fxye'):
            self.pattern_model.save_auto_background_as_pattern(filename, header=self._create_fxye_header(filename))
        else:
            self.pattern_model.save_pattern(filename)

    def _create_xy_header(self):
        """
        Creates the header for the xy file format (contains information about calibration parameters).
        :return: header string
        """
        header = self.calibration_model.create_file_header()
        header = header.replace('\r\n', '\n')
        header = header + '\n#\n# ' + self._integration_unit + '\t I'
        return header

    def _create_fxye_header(self, filename):
        """
        Creates the header for the fxye file format (used by GSAS and GSAS-II) containing the calibration information
        :return: header string
        """
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
        """
        Saves the current pattern in the pattern working directory (specified in self.working_directories['pattern'].
        When background subtraction is enabled in the pattern model the pattern will be saved with background
        subtraction and without in another sub-folder. ('bkg_subtracted')
        """
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
        """
        Updates the shape of the mask in the MaskModel to the shape of the image in the ImageModel.
        """
        self.mask_model.set_dimension(self.img_model._img_data.shape)

    @property
    def integration_rad_points(self):
        return self._integration_rad_points

    @integration_rad_points.setter
    def integration_rad_points(self, new_value: int):
        self._integration_rad_points = new_value
        self.integrate_image_1d()
        if self.auto_integrate_cake:
            self.integrate_image_2d()

    @property
    def cake_azimuth_points(self):
        return self._cake_azimuth_points

    @cake_azimuth_points.setter
    def cake_azimuth_points(self, new_value):
        self._cake_azimuth_points = new_value
        if self.auto_integrate_cake:
            self.integrate_image_2d()

    @property
    def cake_azimuth_range(self):
        return self._cake_azimuth_range

    @cake_azimuth_range.setter
    def cake_azimuth_range(self, new_value):
        self._cake_azimuth_range = new_value
        if self.auto_integrate_cake:
            self.integrate_image_2d()

    @property
    def oned_azimuth_range(self):
        return self._oned_azimuth_range

    @oned_azimuth_range.setter
    def oned_azimuth_range(self, new_value):
        self._oned_azimuth_range = new_value
        if self.auto_integrate_pattern:
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

    @property
    def correct_solid_angle(self):
        return self.calibration_model.correct_solid_angle

    @correct_solid_angle.setter
    def correct_solid_angle(self, new_val):
        self.calibration_model.correct_solid_angle = new_val
        if self.auto_integrate_pattern:
            self.integrate_image_1d()
        if self._auto_integrate_cake:
            self.integrate_image_2d()

    def update_auto_background_parameters_unit(self, old_unit, new_unit):
        """
        This handles the changes for the auto background subtraction parameters in the PatternModel when the integration
        unit is changed.
        :param old_unit: possible values are '2th_deg', 'q_A^-1', 'd_A'
        :param new_unit: possible values are '2th_deg', 'q_A^-1', 'd_A'
        """
        par_0 = convert_units(self.pattern_model.pattern.auto_background_subtraction_parameters[0],
                          self.calibration_model.wavelength,
                          old_unit,
                          new_unit)
        # Value of 0.1 let background subtraction algorithm work without crash.
        if np.isnan(par_0):
            par_0 = 0.1
        self.pattern_model.pattern.auto_background_subtraction_parameters = \
            par_0, \
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
        """
        Creates a copy of the current working directory
        :return: copied configuration
        :rtype: Configuration
        """
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
        # integration parameters:
        general_information.attrs['integration_unit'] = self.integration_unit
        if self.integration_rad_points:
            general_information.attrs['integration_num_points'] = self.integration_rad_points
        else:
            general_information.attrs['integration_num_points'] = 0

        # cake parameters:
        general_information.attrs['auto_integrate_cake'] = self.auto_integrate_cake
        general_information.attrs['cake_azimuth_points'] = self.cake_azimuth_points
        if self.cake_azimuth_range is None:
            general_information.attrs['cake_azimuth_range'] = "None"
        else:
            general_information.attrs['cake_azimuth_range'] = self.cake_azimuth_range

        # mask parameters
        general_information.attrs['use_mask'] = self.use_mask
        general_information.attrs['transparent_mask'] = self.transparent_mask

        # auto save parameters
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
                                        'phase': '', 'batch': ''}
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
            background_data = self.img_model.untransformed_background_data
            image_group.create_dataset('background_data', background_data.shape, 'f', background_data)

        image_group.attrs['series_max'] = self.img_model.series_max
        image_group.attrs['series_pos'] = self.img_model.series_pos

        # image corrections
        corrections_group = image_group.create_group('corrections')
        corrections_group.attrs['has_corrections'] = self.img_model.has_corrections()
        for correction, correction_object in self.img_model.img_corrections.corrections.items():
            if correction in ['cbn', 'oiadac']:
                correction_data = correction_object.get_data()
                imcd = corrections_group.create_dataset(correction, correction_data.shape, 'f', correction_data)
                for param, value in correction_object.get_params().items():
                    imcd.attrs[param] = value
            elif correction == 'transfer':
                params = correction_object.get_params()
                transfer_group = corrections_group.create_group('transfer')
                original_data = params['original_data']
                response_data = params['response_data']
                original_ds = transfer_group.create_dataset('original_data', original_data.shape, 'f', original_data)
                original_ds.attrs['filename'] = params['original_filename']
                response_ds = transfer_group.create_dataset('response_data', response_data.shape, 'f', response_data)
                response_ds.attrs['filename'] = params['response_filename']

        # the actual image
        image_group.attrs['filename'] = self.img_model.filename
        current_raw_image = self.img_model.untransformed_raw_img_data

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

        # save detector information
        detector_group = f.create_group('detector')
        detector_mode = self.calibration_model.detector_mode
        detector_group.attrs['detector_mode'] = detector_mode.value
        if detector_mode == DetectorModes.PREDEFINED:
            detector_group.attrs['detector_name'] = self.calibration_model.detector.name
        elif detector_mode == DetectorModes.NEXUS:
            detector_group.attrs['nexus_filename'] =self.calibration_model.detector.filename

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
        calibration_group.attrs['correct_solid_angle'] = self.correct_solid_angle
        if self.calibration_model.distortion_spline_filename is not None:
            calibration_group.attrs['distortion_spline_filename'] = self.calibration_model.distortion_spline_filename

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
        Loads a configuration from the specified hdf5_group.
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

        try:
            self.correct_solid_angle = f.get('calibration_model').attrs['correct_solid_angle']
        except KeyError:
            pass

        try:
            distortion_spline_filename = f.get('calibration_model').attrs['distortion_spline_filename']
            self.calibration_model.load_distortion(distortion_spline_filename)
        except KeyError:
            pass

        # load detector definition
        try:
            detector_mode = f.get('detector').attrs['detector_mode']
            if detector_mode == DetectorModes.PREDEFINED.value:
                detector_name = f.get('detector').attrs['detector_name']
                self.calibration_model.load_detector(detector_name)
            elif detector_mode == DetectorModes.NEXUS.value:
                nexus_filename = f.get('detector').attrs['nexus_filename']
                self.calibration_model.load_detector_from_file(nexus_filename)
        except AttributeError: # to ensure backwards compatibility
            pass

        # load img_model
        self.img_model._img_data = np.copy(f.get('image_model').get('raw_image_data')[...])
        filename = f.get('image_model').attrs['filename']
        self.img_model.filename = filename

        try:
            self.img_model.file_name_iterator.update_filename(filename)
            self.img_model._directory_watcher.path = os.path.dirname(filename)
        except EnvironmentError:
            pass

        self.img_model.autoprocess = f.get('image_model').attrs['auto_process']
        self.img_model.autoprocess_changed.emit()
        self.img_model.factor = f.get('image_model').attrs['factor']

        try:
            self.img_model.series_max = f.get('image_model').attrs['series_max']
            self.img_model.series_pos = f.get('image_model').attrs['series_pos']
        except KeyError:
            pass

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
        self.calibration_model.load_transformations_string_list(transformation_list)
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
        self.integration_unit = f.get('general_information').attrs['integration_unit']

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
        if f.get('general_information').attrs['integration_num_points']:
            self.integration_rad_points = int(f.get('general_information').attrs['integration_num_points'])

        # cake parameters:
        self.auto_integrate_cake = f.get('general_information').attrs['auto_integrate_cake']
        try:
            self.cake_azimuth_points = f.get('general_information').attrs['cake_azimuth_points']
        except KeyError as e:
            pass
        try:
            if f.get('general_information').attrs['cake_azimuth_range'] == "None":
                self.cake_azimuth_range = None
            else:
                self.cake_azimuth_range = f.get('general_information').attrs['cake_azimuth_range']
        except KeyError as e:
            pass

        # mask parameters
        self.use_mask = f.get('general_information').attrs['use_mask']
        self.transparent_mask = f.get('general_information').attrs['transparent_mask']

        # corrections
        if f.get('image_model').get('corrections').attrs['has_corrections']:
            for name, correction_group in f.get('image_model').get('corrections').items():
                params = {}
                for param, val in correction_group.attrs.items():
                    params[param] = val
                if name == 'cbn':
                    tth_array = 180.0 / np.pi * self.calibration_model.pattern_geometry.ttha
                    azi_array = 180.0 / np.pi * self.calibration_model.pattern_geometry.chia
                    cbn_correction = CbnCorrection(tth_array=tth_array, azi_array=azi_array)

                    cbn_correction.set_params(params)
                    cbn_correction.update()
                    self.img_model.add_img_correction(cbn_correction, name)
                elif name == 'oiadac':
                    tth_array = 180.0 / np.pi * self.calibration_model.pattern_geometry.ttha
                    azi_array = 180.0 / np.pi * self.calibration_model.pattern_geometry.chia
                    oiadac = ObliqueAngleDetectorAbsorptionCorrection(tth_array=tth_array, azi_array=azi_array)

                    oiadac.set_params(params)
                    oiadac.update()
                    self.img_model.add_img_correction(oiadac, name)
                elif name == 'transfer':
                    params = {
                        'original_data': correction_group.get('original_data')[...],
                        'original_filename': correction_group.get('original_data').attrs['filename'],
                        'response_data': correction_group.get('response_data')[...],
                        'response_filename': correction_group.get('response_data').attrs['filename']
                    }

                    self.img_model.transfer_correction.set_params(params)
                    self.img_model.enable_transfer_function()

        # autosave parameters
        self.auto_save_integrated_pattern = f.get('general_information').attrs['auto_save_integrated_pattern']
        self.integrated_patterns_file_formats = []
        for file_format in f.get('general_information').get('integrated_patterns_file_formats'):
            self.integrated_patterns_file_formats.append(file_format[0].decode('utf-8'))

        if self.calibration_model.is_calibrated:
            self.integrate_image_1d()
        else:
            self.pattern_model.pattern.recalculate_pattern()
