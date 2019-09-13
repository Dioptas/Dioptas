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
import os

import numpy as np

from ..utility import QtTest, unittest_data_path
from ...model.ImgModel import ImgModel

from flask import Flask

app = Flask(__name__)


@app.route('/run_<run>/train_<train>')
def get_image(run, train):
    data = ImgModel.load_PIL(None, os.path.join(unittest_data_path, 'image_001.tif'))
    bytestream = io.BytesIO()
    np.save(bytestream, data)
    return bytestream.getvalue()


class ImgModelRestTest(QtTest):
    def setUp(self):
        self.img_model = ImgModel()
        self.client = app.test_client()

    def test_server_is_working(self):
        response = self.client.get('/run_1/train_1')
        img = response.data
        print('#######################')
