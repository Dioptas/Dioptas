# SPDX-License-Identifier: MIT
"""Counts, ownership, selection and lifetime checks for the production reader."""
from pathlib import Path
import os
import shutil
from unittest.mock import MagicMock

import h5py
import numpy as np
import pytest

from dioptas.model.Configuration import Configuration
from dioptas.model.loader.hdf5Loader import Hdf5Image
from dioptas.model.loader import fastHdf5
from dioptas.model.util.integration import prefetch_series, iter_frames_indexed, _selected_reader

FIXTURE = Path(__file__).parents[1] / 'data/fast_hdf5/counts-bitshuffle-lz4.h5'


@pytest.fixture
def counts():
    with h5py.File(FIXTURE) as f:
        return np.ascontiguousarray(f['detector/data'][:][:, ::-1], dtype=np.float64)


@pytest.mark.parametrize('workers', [1, 2, 8])
@pytest.mark.parametrize('fallback', [False, True])
def test_prefetched_counts_and_owned_arrays(counts, monkeypatch, workers, fallback):
    if fallback:
        monkeypatch.setattr(fastHdf5, '_codec', None)
    else:
        pytest.importorskip('bslz4_to_sparse')
    reader = Hdf5Image(str(FIXTURE))
    try:
        frames = list(reader.gen_frames(decomp_workers=workers))
        np.testing.assert_array_equal(frames, counts)
        assert all(frame.flags.c_contiguous and frame.dtype == np.float64 for frame in frames)
        assert not np.shares_memory(frames[0], frames[1])
        before = frames[0].copy()
        list(reader.gen_frames(decomp_workers=workers))
        np.testing.assert_array_equal(frames[0], before)
        np.testing.assert_array_equal(list(reader.gen_frames(start_frame=1, decomp_workers=workers)), counts[1:])
    finally:
        reader.f.close()


def test_no_codec_general_filter_fallback(tmp_path):
    data = np.arange(24, dtype='>u4').reshape(2, 3, 4)
    path = tmp_path/'general.h5'
    with h5py.File(path,'w') as f:
        f.create_dataset('data', data=data, compression='gzip')
    reader = Hdf5Image(str(path))
    try:
        np.testing.assert_array_equal(list(reader.gen_frames(decomp_workers=2)), data[:, ::-1])
    finally:
        reader.f.close()


def test_source_change_fails_and_closes_workers(tmp_path, monkeypatch):
    pytest.importorskip('bslz4_to_sparse')
    path = tmp_path/'counts.h5'
    shutil.copyfile(FIXTURE, path)
    opened=[]
    original = fastHdf5.FastChunkReader.__init__
    def tracked(self,*args,**kwargs):
        original(self,*args,**kwargs); opened.append(self)
    monkeypatch.setattr(fastHdf5.FastChunkReader,'__init__',tracked)
    reader = Hdf5Image(str(path))
    frames = reader.gen_frames(decomp_workers=1)
    next(frames)
    stat = path.stat()
    os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns+1_000_000))
    try:
        with pytest.raises(OSError,match='changed'):
            list(frames)
        assert opened and all(x.fd is None for x in opened)
    finally:
        frames.close(); reader.f.close()


def test_prefetch_restores_callback_after_abort_and_random_access(counts, monkeypatch):
    config = Configuration(); config.auto_integrate_pattern=False
    model = config.img_model; model.load(str(FIXTURE))
    original = model.series_get_image
    readers=[]
    open_reader = __import__('dioptas.model.util.integration',fromlist=['_selected_reader'])._selected_reader
    def track(*args):
        reader=open_reader(*args);readers.append(reader);return reader
    monkeypatch.setattr('dioptas.model.util.integration._selected_reader',track)
    with pytest.raises(RuntimeError,match='cancel'):
        with prefetch_series(model,workers=2):
            for index in [1,0,1,1]:
                np.testing.assert_array_equal(model.series_get_image(index),counts[index])
            raise RuntimeError('cancel')
    assert model.series_get_image is original
    assert all(not x.f.id.valid for x in readers)
    np.testing.assert_array_equal(model.series_get_image(0),counts[0])


@pytest.mark.parametrize('background', [False, True])
def test_prefetch_retains_frame_corrections(counts, background):
    config=Configuration();config.auto_integrate_pattern=False
    model=config.img_model;model.load(str(FIXTURE))
    model.factor=1.25
    model.rotate_img_p90()
    if background:
        model._background_data=np.full(model.raw_img_data.shape,2.)
        model._calculate_img_data()
    # Compare the ordinary loader and the prefetched callback after exactly
    # the same ImgModel transformation/correction pipeline.
    model.load_series_img(2)
    expected=model.img_data.copy()
    model.load_series_img(1)
    with prefetch_series(model,workers=2):
        model.load_series_img(2)
        np.testing.assert_array_equal(model.img_data,expected)


def test_indexed_stream_supports_skips_repeats_and_reverse(counts):
    config=Configuration();config.auto_integrate_pattern=False
    source=np.array([(0,0),(0,1)])
    frames=list(iter_frames_indexed(config.img_model,[str(FIXTURE)],source,[1,0,1,1],workers=2))
    np.testing.assert_array_equal(frames,counts[[1,0,1,1]])


def test_ambiguous_dataset_keeps_existing_loader(monkeypatch):
    reader=MagicMock();reader.image_sources=['/first','/second']
    monkeypatch.setattr('dioptas.model.util.integration.try_open_bitshuffle_hdf5',lambda _:reader)
    model=MagicMock();model.selected_source=None;model._select_source=None
    assert _selected_reader('scan.h5',model) is None
    reader.f.close.assert_called_once()
    model.selected_source='/second';model._select_source=lambda _:None
    assert _selected_reader('scan.h5',model) is reader
    reader.select_source.assert_called_once_with('/second')


@pytest.mark.parametrize('dtype', [np.uint16, np.uint32])
def test_typed_fast_decoder_matches_independent_bitshuffle(tmp_path, dtype):
    import struct
    from types import SimpleNamespace
    import bitshuffle
    pytest.importorskip('bslz4_to_sparse')
    values = np.arange(24, dtype=dtype).reshape(4, 6)
    values[0, 0] = np.iinfo(dtype).max
    # Independent encoder supplies the raw bitshuffle stream; the synthetic
    # dataset metadata only supplies its indexed location and scalar type.
    encoded = struct.pack('>QI', values.nbytes, 8192) + bitshuffle.compress_lz4(values).tobytes()
    path = tmp_path/'chunk.bin'; path.write_bytes(encoded)
    properties=MagicMock();properties.get_nfilters.return_value=1
    properties.get_filter.return_value=(32008, 0, (0, 5, np.dtype(dtype).itemsize, 0, 2), b'bitshuffle')
    dataset=MagicMock();dataset.shape=(1,*values.shape);dataset.dtype=np.dtype(dtype)
    dataset.chunks=(1,*values.shape);dataset.file.filename=str(path)
    dataset.id.get_create_plist.return_value=properties
    dataset.id.get_chunk_info_by_coord.return_value=SimpleNamespace(filter_mask=0,byte_offset=0,size=len(encoded))
    reader=fastHdf5.FastChunkReader(dataset)
    try:
        np.testing.assert_array_equal(reader.read(0),values[::-1].astype(float))
        # Bad length/header must be rejected before calling the native decoder.
        path.write_bytes(b'bad')
        with pytest.raises(OSError,match='changed'):
            reader.read(0)
    finally:
        reader.close()


def test_hard_link_aliases_are_one_source_and_selected_channels_stay_distinct(tmp_path):
    from types import SimpleNamespace
    path=tmp_path/'channels.h5';shutil.copyfile(FIXTURE,path)
    with h5py.File(path,'r+') as f:
        f['alias']=f['detector/data']
    model=SimpleNamespace(selected_source=None,_select_source=None,loader=None)
    reader=_selected_reader(str(path),model)
    assert reader is not None
    try:
        assert all(reader.f[name].id==reader.dataset.id for name in reader.image_sources)
    finally:
        reader.f.close()
    with h5py.File(path,'r+') as f:
        f.create_dataset('other',data=np.zeros((2,3,4),np.uint32))
    assert _selected_reader(str(path),model) is None
    # A real dataset selected by the established image loader is authoritative,
    # even if another channel has precisely the same dimensions and dtype.
    with h5py.File(path) as f:
        model.loader=SimpleNamespace(fabio_image=SimpleNamespace(dataset=f['other']))
        reader=_selected_reader(str(path),model)
        assert reader is not None
        try:
            assert reader.dataset.id==f['other'].id
            np.testing.assert_array_equal(list(reader.gen_frames(decomp_workers=2)),0)
        finally:
            reader.f.close()
