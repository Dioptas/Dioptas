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
import pytest
from ...model.OverlayModel import OverlayModel

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, '../data')


@pytest.fixture
def overlay_model():
    return OverlayModel()


def test_add_overlay(overlay_model: OverlayModel):
    x_overlay = np.linspace(0, 10)
    y_overlay = np.linspace(0, 100)
    overlay_model.add_overlay(x_overlay, y_overlay, "dummy")

    assert len(overlay_model.overlays) == 1
    new_overlay = overlay_model.get_overlay(0)
    assert new_overlay.name == "dummy"
    assert np.array_equal(new_overlay.x, x_overlay)
    assert np.array_equal(new_overlay.y, y_overlay)


def test_add_overlay_from_file(overlay_model: OverlayModel):
    filename = os.path.join(data_path, 'pattern_001.xy')
    overlay_model.add_overlay_file(filename)

    assert len(overlay_model.overlays) == 1
    assert overlay_model.get_overlay(0).name == ''.join(os.path.basename(filename).split('.')[0:-1])
