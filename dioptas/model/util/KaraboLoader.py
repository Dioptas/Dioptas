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

from karabo_data import H5File

__all__ = ['KaraboFile']


class KaraboFile:
    def __init__(self, filename, source_ind=0):
        self.f = H5File(filename)
        self.series_max = len(self.f.train_ids)
        self.sources = [s for s in self.f.instrument_sources if "daqOutput" in s]
        self.current_source = self.sources[source_ind]

    def get_image(self, ind):
        tid, data = self.f.train_from_index(ind)
        return data[self.current_source]['data.image.pixels']
