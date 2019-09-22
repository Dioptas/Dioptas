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

import io
import time

try:
    import requests

    requests_available = True
except ModuleNotFoundError:
    requests_available = False

import numpy as np

from .ImgLoader import ImageLoader


class HttpLoader(ImageLoader):
    def load(self, http_address):
        if not requests_available:
            raise IOError('Please install requests Library in order to use http for images')

        try:
            r = requests.get(http_address)
            t1 = time.time()
            self.img_data = np.load(io.BytesIO(r.content))
            print("Loading the data takes: {}".format(time.time() - t1))
            self.filename = http_address
        except ValueError:
            raise IOError
