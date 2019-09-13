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
