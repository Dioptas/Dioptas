"""Full-resolution transfer, content invalidation, and bounded display caches."""
import io
import json
from pathlib import Path
import struct

import numpy as np
import pytest

from dioptas.desktop.binary import RasterCache, encode_frame
from dioptas.desktop.session import DesktopSession, raster
from dioptas.desktop.stdio import serve

DATA = Path(__file__).resolve().parents[2] / 'dioptas/tests/data'


def unpack(parts):
    wire = b''.join(parts)
    n, = struct.unpack('<I', wire[:4])
    header = json.loads(wire[4:4+n])
    offset = 4 + n
    buffers = {}
    for entry in header['buffers']:
        end = offset + entry['length']
        buffers[entry['id']] = wire[offset:end]
        offset = end
    assert offset == len(wire)
    return header, buffers


def call(s, action, **payload):
    r = s.invoke(action, payload)
    assert r['ok'], r.get('error')
    return r


def test_binary_frame_preserves_every_detector_pixel_and_deduplicates_buffers():
    s = DesktopSession(binary_images=True)
    result = call(s, 'open_image', path=str(DATA/'image_001.tif'))
    header, buffers = unpack(encode_frame(5, {**result, 'duplicateImage': result['image']}))
    descriptor = header['result']['image']
    source = s.configuration.img_model.img_data
    assert descriptor['step'] == 1
    assert (descriptor['height'], descriptor['width']) == source.shape == (2048, 2048)
    assert 'data' not in descriptor
    assert len(buffers) == 2  # detector plus mask, not a second detector copy
    image = np.frombuffer(buffers[descriptor['bufferId']], dtype='<f4').reshape(source.shape)
    np.testing.assert_array_equal(image, source.astype('<f4'))
    assert len(buffers[descriptor['bufferId']]) == source.size * 4
    assert header['id'] == 5
    assert sum(descriptor['histogram']['counts']) == source.size
    assert header['result']['duplicateImage'] == descriptor
    header, buffers = unpack(encode_frame(6, result, list(buffers)))
    assert not header['buffers'] and not buffers
    assert header['result']['image'] == descriptor


def test_previous_next_reuses_full_image_statistics_and_unchanged_mask(monkeypatch):
    import dioptas.desktop.session as module
    s = DesktopSession(binary_images=True)
    first = call(s, 'open_image', path=str(DATA/'image_001.tif'))
    second = call(s, 'next_image', direction=1)
    assert first['image']['bufferId'] != second['image']['bufferId']
    assert first['mask']['bufferId'] == second['mask']['bufferId']
    assert first['mask']['data'] is second['mask']['data']
    def unexpected(*a, **kw):
        pytest.fail('Unchanged raster statistics were rebuilt')
    monkeypatch.setattr(module, 'raster', unexpected)
    again = call(s, 'next_image', direction=-1)
    assert again['image']['data'] is first['image']['data']
    assert again['image']['histogram'] == first['image']['histogram']
    assert again['image']['limits'] == first['image']['limits']
    known = [first['image']['bufferId'], second['image']['bufferId'], first['mask']['bufferId']]
    header, _ = unpack(encode_frame(3, again, known))
    assert header['buffers'] == []


def test_mutation_and_mask_undo_redo_invalidate_content_ids():
    s = DesktopSession(binary_images=True)
    first = call(s, 'example')
    changed = call(s, 'mask_stroke', points=[[100, 100]], radius=3, erase=False)
    assert first['mask']['bufferId'] != changed['mask']['bufferId']
    undone = call(s, 'undo_mask')
    redone = call(s, 'redo_mask')
    assert undone['mask']['data'] is first['mask']['data']
    assert redone['mask']['data'] is changed['mask']['data']
    assert s.configuration.img_model.img_data.dtype != np.float32  # source precision retained


def test_raster_cache_detects_in_place_edits_and_full_precision_statistics():
    cache = RasterCache()
    source = np.array([[1., 2.], [3., 4.]])
    first = cache.raster(source, raster, binary=True, max_side=None, histogram=True)
    source[1, 1] += 1e-8  # same float32 display bytes, changed scientific values
    changed = cache.raster(source, raster, binary=True, max_side=None, histogram=True)
    assert changed['bufferId'] == first['bufferId']
    assert changed['limits'] != first['limits']
    source[0, 0] = -37.
    assert cache.raster(source, raster, binary=True)['bufferId'] != first['bufferId']


def test_cache_eviction_is_bounded_and_a_missing_client_copy_is_resent():
    cache = RasterCache(max_bytes=32)
    a = np.zeros((2, 2)); b = np.ones((2, 2)); c = np.full((2, 2), 2.)
    old = cache.raster(a, raster, binary=True)
    for source in [b, c]: cache.raster(source, raster, binary=True)
    assert cache.size == 32 and len(cache.entries) == 2
    rebuilt = cache.raster(a, raster, binary=True)
    assert rebuilt['bufferId'] == old['bufferId']
    assert rebuilt['data'] == old['data']
    header, buffers = unpack(encode_frame(1, {'image': rebuilt}, []))
    assert len(buffers) == 1 and header['buffers'][0]['length'] == 16
    cache.raster(np.zeros((100, 100)), raster, binary=True)
    assert cache.size <= 32


def test_binary_serve_rejects_invalid_cache_advertisement_before_mutation():
    class Session:
        actions = []
        def invoke(self, action, payload=None):
            self.actions.append(action)
            return {'ok': True}
        def close(self): pass
    s = Session(); output = io.BytesIO()
    serve(io.StringIO(json.dumps({'id': 1, 'action': 'open_image', 'cachedBuffers': 'invalid'})+'\n'), output, s, binary=True)
    header, _ = unpack([output.getvalue()])
    assert header['result']['ok'] is False
    assert 'open_image' not in s.actions


def test_ring_contours_reused_until_actual_geometry_changes(monkeypatch):
    import skimage.measure
    s = DesktopSession(binary_images=True)
    call(s, 'example')
    call(s, 'open_calibration', path=str(DATA/'CeO2_Pilatus1M.poni'))
    before = s._rings
    original = skimage.measure.find_contours
    monkeypatch.setattr(skimage.measure, 'find_contours', lambda *a, **k: pytest.fail('Unchanged ring geometry rebuilt'))
    s._calculate()
    assert s._rings is before
    monkeypatch.setattr(skimage.measure, 'find_contours', original)
    calibration = s.configuration.calibration_model
    calibration.pattern_geometry.dist += .001
    calibration.pattern_geometry.reset()
    s._calculate()
    assert s._rings is not before
