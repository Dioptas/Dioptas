# SPDX-License-Identifier: MIT

import fabio


class FabioLoader:
    def __init__(self, filename):
        """
        Loads an Hdf5 image produced by ESRF
        :param filename: path to the hdf5 file to be loaded
        """

        self.fabio_image = fabio.open(filename)
        self.series_max = self.fabio_image.nframes

    def get_image(self, ind=0):
        return self.fabio_image.get_frame(ind).data[::-1]
