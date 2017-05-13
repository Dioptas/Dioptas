"""Implements the SPE_File class for loading princeton instrument binary SPE files into Python
works for version 2 and version 3 files.

Usage:
mydata = SPE_File('data.spe')

most important properties:

num_frames - number of frames collected
exposure_time

img - 2d data if num_frames==1
      list of 2d data if num_frames>1  

x_calibration - wavelength information of x-axis



the data will be automatically loaded and all important parameters and the data 
can be requested from the object.
"""

import datetime
from xml.dom.minidom import parseString

import numpy as np
from numpy.polynomial.polynomial import polyval
from dateutil import parser


class SpeFile(object):
    def __init__(self, filename, debug=False):
        """Opens the PI SPE file and loads its content

        :param filename: filename of the PI SPE to open
        :param debug: if set to true, will automatically save <filename>.xml files for version 3 spe files in the spe
        directory
        """
        """"""
        self.filename = filename
        self.debug = debug
        self._fid = open(filename, 'rb')
        self._read_parameter()
        self._read_img()
        self._fid.close()

    def _read_parameter(self):
        """Reads in size and datatype. Decides wether it should check in the binary
        header (version 2) or in the xml-footer for the experimental parameters"""
        self._read_size()
        self._read_datatype()
        self.xml_offset = self._read_at(678, 1, np.long)
        if self.xml_offset == [0]:  # means that there is no XML present, hence it is a pre 3.0 version of the SPE
            # file
            self._read_parameter_from_header()
        else:
            self._read_parameter_from_dom()

    def _read_size(self):
        """reads the dimensions of the Model from the header into the object
        resulting object parameters are _xdim and _ydim"""
        self._xdim = np.int64(self._read_at(42, 1, np.int16)[0])
        self._ydim = np.int64(self._read_at(656, 1, np.int16)[0])

    def _read_parameter_from_header(self):
        """High level function which calls all the read_"parameter" function
        that are reading information from the binary header.
        """
        self._read_date_time_from_header()
        # self._read_calibration_from_header()
        self._read_exposure_from_header()
        # self._read_detector_from_header()
        # self._read_grating_from_header()
        # self._read_center_wavelength_from_header()
        # self._read_roi_from_header()
        self._read_num_frames_from_header()
        self._read_num_combined_frames_from_header()

    def _read_parameter_from_dom(self):
        """High level function which calls all the read_"parameter" function
        that are reading information from the xml footer.
        """
        self._get_xml_string()
        self._create_dom_from_xml()
        self._read_date_time_from_dom()
        self._read_calibration_from_dom()
        self._read_detector_from_dom()
        self._read_exposure_from_dom()
        self._read_grating_from_dom()
        self._read_center_wavelength_from_dom()
        self._read_roi_from_dom()
        self._select_wavelength_from_roi()
        self._read_num_frames_from_header()
        self._read_num_combined_frames_from_dom()

    def _read_date_time_from_header(self):
        """Reads the collection time from the header into the date_time field"""
        rawdate = self._read_at(20, 9, np.int8)
        rawtime = self._read_at(172, 6, np.int8)
        strdate = ''.join([chr(i) for i in rawdate])
        strdate += ''.join([chr(i) for i in rawtime])
        try:
            self.date_time = datetime.datetime.strptime(strdate, "%d%b%Y%H%M%S")
        except ValueError:
            # catching a strange error on Linux, where strptime does not work within Dioptas, but within the Terminal it
            # runs without problems...
            self.date_time = datetime.datetime(1, 1, 1)

    def _read_calibration_from_header(self):
        """Reads the calibration from the header into the x_calibration field"""
        x_polynocoeff = self._read_at(3263, 6, np.double)
        x_val = np.arange(self._xdim) + 1
        self.x_calibration = np.array(polyval(x_val, x_polynocoeff))

    def _read_exposure_from_header(self):
        """Reads the exposure time from the header into the exposure_time field"""
        self.exposure_time = self._read_at(10, 1, np.float32)
        self.exposure_time = self.exposure_time[0]

    def _read_detector_from_header(self):
        """Sets the detector value to unspecified, because the detector is not
        specified in the binary header. Only in the xml footer of version 3 SPE
        files """
        self.detector = 'unspecified'

    def _read_grating_from_header(self):
        """Reads grating position from the header into the grating field"""
        self.grating = str(self._read_at(650, 1, np.float32)[0])

    def _read_center_wavelength_from_header(self):
        """Reads center wavelength position from the header into the center_wavelength field"""
        self.center_wavelength = float(self._read_at(72, 1, np.float32)[0])

    def _read_roi_from_header(self):
        return

    def _read_num_frames_from_header(self):
        self.num_frames = self._read_at(1446, 1, np.int32)[0]

    def _read_num_combined_frames_from_header(self):
        self._num_combined_frames = 1

    def _create_dom_from_xml(self):
        """Creates a DOM representation of the xml footer and saves it in the
        dom field"""
        self.dom = parseString(self.xml_string)

    def _get_xml_string(self):
        """Reads out the xml string from the file end"""
        xml_size = self.get_file_size() - self.xml_offset
        xml = self._read_at(self.xml_offset, xml_size, np.byte)
        self.xml_string = ''.join([chr(i) for i in xml])
        if self.debug:
            fid = open(self.filename + '.xml', 'w')
            for line in self.xml_string:
                fid.write(line)
            fid.close()

    def _read_date_time_from_dom(self):
        """Reads the time of collection and saves it date_time field"""
        date_time_str = self.dom.getElementsByTagName('Origin')[0].getAttribute('created')
        self.date_time = parser.parse(date_time_str)

    def _read_calibration_from_dom(self):
        """Reads the x calibration of the image from the xml footer and saves 
        it in the x_calibration field"""
        spe_format = self.dom.childNodes[0]
        calibrations = spe_format.getElementsByTagName('Calibrations')[0]
        wavelengthmapping = calibrations.getElementsByTagName('WavelengthMapping')[0]
        wavelengths = wavelengthmapping.getElementsByTagName('Wavelength')[0]
        wavelength_values = wavelengths.childNodes[0]
        self.x_calibration = np.array([float(i) for i in wavelength_values.toxml().split(',')])

    def _read_exposure_from_dom(self):
        """Reads th exposure time of the experiment into the exposure_time field"""
        if len(self.dom.getElementsByTagName('Experiment')) != 1:  # check if it is a real v3.0 file
            if len(self.dom.getElementsByTagName('ShutterTiming')) == 1:  # check if it is a pixis detector
                self._exposure_time = self.dom.getElementsByTagName('ExposureTime')[0].childNodes[0]
                self.exposure_time = np.float(self._exposure_time.toxml()) / 1000.0
            else:
                self._exposure_time = self.dom.getElementsByTagName('ReadoutControl')[0]. \
                    getElementsByTagName('Time')[0].childNodes[0].nodeValue
                self._accumulations = self.dom.getElementsByTagName('Accumulations')[0].childNodes[0].nodeValue
                self.exposure_time = np.float(self._exposure_time) * np.float(self._accumulations)
        else:  # this is searching for legacy experiment:
            self._exposure_time = self.dom.getElementsByTagName('LegacyExperiment')[0]. \
                getElementsByTagName('Experiment')[0]. \
                getElementsByTagName('CollectionParameters')[0]. \
                getElementsByTagName('Exposure')[0].attributes["value"].value
            self.exposure_time = np.float(self._exposure_time.split()[0])

    def _read_detector_from_dom(self):
        """Reads the detector information from the dom object"""
        self._camera = self.dom.getElementsByTagName('Camera')
        if len(self._camera) >= 1:
            self.detector = self._camera[0].getAttribute('model')
        else:
            self.detector = 'unspecified'

    def _read_grating_from_dom(self):
        """Reads the type of grating from the dom Model"""
        try:
            self._grating = self.dom.getElementsByTagName('Devices')[0]. \
                getElementsByTagName('Spectrometer')[0]. \
                getElementsByTagName('Grating')[0]. \
                getElementsByTagName('Selected')[0].childNodes[0].toxml()
            self.grating = self._grating.split('[')[1].split(']')[0].replace(',', ' ')
        except IndexError:
            self._read_grating_from_header()

    def _read_center_wavelength_from_dom(self):
        """Reads the center wavelength from the dom Model and saves it center_wavelength field"""
        try:
            self._center_wavelength = self.dom.getElementsByTagName('Devices')[0]. \
                getElementsByTagName('Spectrometer')[0]. \
                getElementsByTagName('Grating')[0]. \
                getElementsByTagName('CenterWavelength')[0]. \
                childNodes[0].toxml()
            self.center_wavelength = float(self._center_wavelength)
        except IndexError:
            self._read_center_wavelength_from_header()

    def _read_roi_from_dom(self):
        """Reads the ROIs information defined in the SPE file.
        Depending on the modus it will read out:
        For CustomRegions
        roi_x, roi_y, roi_width, roi_height, roi_x_binning, roi_y_binning
        For FullSensor
        roi_x,roi_y, roi_width, roi_height"""
        try:
            self.roi_modus = str(self.dom.getElementsByTagName('ReadoutControl')[0]. \
                                 getElementsByTagName('RegionsOfInterest')[0]. \
                                 getElementsByTagName('Selection')[0]. \
                                 childNodes[0].toxml())
            if self.roi_modus == 'CustomRegions':
                self.roi_dom = self.dom.getElementsByTagName('ReadoutControl')[0]. \
                    getElementsByTagName('RegionsOfInterest')[0]. \
                    getElementsByTagName('CustomRegions')[0]. \
                    getElementsByTagName('RegionOfInterest')[0]
                self.roi_x = int(self.roi_dom.attributes['x'].value)
                self.roi_y = int(self.roi_dom.attributes['y'].value)
                self.roi_width = int(self.roi_dom.attributes['width'].value)
                self.roi_height = int(self.roi_dom.attributes['height'].value)
                self.roi_x_binning = int(self.roi_dom.attributes['xBinning'].value)
                self.roi_y_binning = int(self.roi_dom.attributes['yBinning'].value)
            elif self.roi_modus == 'FullSensor':
                self.roi_x = 0
                self.roi_y = 0
                self.roi_width = self._xdim
                self.roi_height = self._ydim

        except IndexError:
            self.roi_x = 0
            self.roi_y = 0
            self.roi_width = self._xdim
            self.roi_height = self._ydim

    def _read_num_combined_frames_from_dom(self):
        try:
            self.frame_combination = self.dom.getElementsByTagName('Experiment')[0]. \
                getElementsByTagName('Devices')[0]. \
                getElementsByTagName('Cameras')[0]. \
                getElementsByTagName('FrameCombination')[0]
            self.num_frames_combined = int(self.frame_combination.getElementsByTagName('FramesCombined')[0]. \
                                           childNodes[0].toxml())
        except IndexError:
            self._read_num_combined_frames_from_header()

    def _select_wavelength_from_roi(self):
        self.x_calibration = self.x_calibration[self.roi_x: self.roi_x + self.roi_width]

    def _read_datatype(self):
        self._data_type = self._read_at(108, 1, np.uint16)[0]

    def _read_at(self, pos, size, ntype):
        self._fid.seek(pos)
        return np.fromfile(self._fid, ntype, size)

    def _read_img(self):
        self.img = self._read_frame(4100)
        if self.num_frames > 1:
            img_temp = []
            img_temp.append(self.img)
            for n in range(self.num_frames - 1):
                img_temp.append(self._read_frame())
            self.img = img_temp

    def _read_frame(self, pos=None):
        """Reads in a frame at a specific binary position. The following parameters have to
        be predefined before calling this function:
        datatype - either 0,1,2,3 for float32, int32, int16 or uint16
        _xdim, _ydim - being the dimensions.
        """
        if pos == None:
            pos = self._fid.tell()
        if self._data_type == 0:
            img = self._read_at(pos, self._xdim * self._ydim, np.float32)
        elif self._data_type == 1:
            img = self._read_at(pos, self._xdim * self._ydim, np.int32)
        elif self._data_type == 2:
            img = self._read_at(pos, self._xdim * self._ydim, np.int16)
        elif self._data_type == 3:
            img = self._read_at(pos, self._xdim * self._ydim, np.uint16)
        return img.reshape((self._ydim, self._xdim))

    def get_index_from(self, wavelength):
        """
        calculating image index for a given index
        :param wavelength: wavelength in nm
        :return: index
        """
        result = []
        xdata = self.x_calibration
        try:
            for w in wavelength:
                try:
                    base_ind = max(max(np.where(xdata <= w)))
                    if base_ind < len(xdata) - 1:
                        result.append(int(np.round((w - xdata[base_ind]) / \
                                                   (xdata[base_ind + 1] - xdata[base_ind]) \
                                                   + base_ind)))
                    else:
                        result.append(base_ind)
                except:
                    result.append(0)
            return np.array(result)
        except TypeError:
            base_ind = max(max(np.where(xdata <= wavelength)))
            return int(np.round((wavelength - xdata[base_ind]) / \
                                (xdata[base_ind + 1] - xdata[base_ind]) \
                                + base_ind))

    def get_wavelength_from(self, index):
        if isinstance(index, list):
            result = []
            for c in index:
                result.append(self.x_calibration[c])
            return np.array(result)
        else:
            return self.x_calibration[index]

    def get_dimension(self):
        """Returns (xdim, ydim)"""
        return (self._xdim, self._ydim)

    def get_roi(self):
        """Returns the ROI which was defined by WinSpec or Lightfield for datacollection"""
        return [self.roi_x, self.roi_x + self.roi_width - 1,
                self.roi_y, self.roi_y + self.roi_height - 1]

    def get_file_size(self):
        self._fid.seek(0, 2)
        self.file_size = self._fid.tell()
        return self.file_size
