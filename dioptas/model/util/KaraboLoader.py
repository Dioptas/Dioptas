from karabo_data import H5File

__all__ = ['KaraboFile']


class KaraboFile:
    def __init__(self, filename, source_ind=0):
        self.f = H5File(filename)
        self.series_max = len(self.f.train_ids)
        self.sources = [s for s in self.f.instrument_sources if "daqOutput" in s]
        print(self.f.instrument_sources)
        self.current_source = self.sources[source_ind]
        print(self.f.keys_for_source(self.current_source))

        for tid, data in self.f.trains():
            print("Processing train", tid)
            print(data)
            break

    def get_image(self, ind):
        pass
