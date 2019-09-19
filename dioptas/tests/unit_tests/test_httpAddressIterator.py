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

from ..utility import QtTest
from ...model.util.NameIterators import HttpAddressIterator


class HttpAddressIteratorTest(QtTest):
    def setUp(self):
        self.http_iterator = HttpAddressIterator()

    def test_get_next_frame(self):
        http_address = 'http://123.234.123.132:2315/run_1/frame_1'
        self.http_iterator.update_address(http_address)
        new_address = self.http_iterator.get_next_frame()
        self.assertEqual(new_address, 'http://123.234.123.132:2315/run_1/frame_2')

    def test_get_previous_frame(self):
        http_address = 'http://123.234.123.132:2315/run_1/frame_2'
        self.http_iterator.update_address(http_address)
        new_address = self.http_iterator.get_previous_frame()
        self.assertEqual(new_address, 'http://123.234.123.132:2315/run_1/frame_1')

    def test_get_next_run(self):
        http_address = 'http://123.234.123.132:2315/run_1/frame_1'
        self.http_iterator.update_address(http_address)
        new_address = self.http_iterator.get_next_run()
        self.assertEqual(new_address, 'http://123.234.123.132:2315/run_2/frame_1')

    def test_get_previous_run(self):
        http_address = 'http://123.234.123.132:2315/run_2/frame_1'
        self.http_iterator.update_address(http_address)
        new_address = self.http_iterator.get_previous_run()
        self.assertEqual(new_address, 'http://123.234.123.132:2315/run_1/frame_1')

