# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019 DESY, Hamburg, Germany
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


import fabio

from .ImgLoader import ImageLoader


class FabioLoader(ImageLoader):
    def load(self, filename):
        """
        Loads an image using the fabio library.
        :param filename: path to the image file to be loaded
        :return: dictionary with image_data and image_data_fabio, None if unsuccessful
        """
        try:
            img_data_fabio = fabio.open(filename)
            self.img_data = img_data_fabio.data[::-1]
        except (IOError, fabio.fabioutils.NotGoodReader):
            return None
