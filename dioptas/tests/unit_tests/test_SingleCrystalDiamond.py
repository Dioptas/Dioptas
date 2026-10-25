# SPDX-License-Identifier: MIT
from types import SimpleNamespace

import numpy as np
import pytest

from ...model.single_crystal_diamond import (
    DiamondMaskPlan, exclude_overlapping_spots, exclude_overlapping_tracks,
    observation_key,
)
from ...model.util.mask_plugins.diamond_roi import AffineDiamondGeometry, DiamondROIDetector
from ...model.util.mask_plugins.diamond_reference import diamond_d_spacings


def test_reference_against_independent_structure_factor():
    fcc = np.array([[0,0,0],[0,.5,.5],[.5,0,.5],[.5,.5,0]])
    atoms = np.vstack([fcc, fcc+.25])
    expected = set()
    for h in range(7):
        for k in range(7):
            for l in range(7):
                n=h*h+k*k+l*l
                if 0<n<=36 and abs(np.exp(2j*np.pi*(atoms@[h,k,l])).sum())>1e-8:
                    expected.add(n)
    assert set(np.rint((3.567/diamond_d_spacings(3.567,3.567/6))**2).astype(int)) == expected


def test_affine_geometry_and_worker_copy_match_full_map():
    shape=(224,280)
    y,x=np.indices(shape)
    theta=2*np.arcsin(.31/(2*(3.567/4)))
    vectors=np.array([[np.tan(theta)*.04-70*79e-6,-70*79e-6,.04],
                      [79e-6,0,0],[0,79e-6,0],[0,0,1],[1,0,0]])
    affine=AffineDiamondGeometry(shape,vectors,.31e-10)
    full=SimpleNamespace(tth_array=affine.angles(y,x),wavelength=.31e-10)
    direct=DiamondROIDetector(full,background_radius=40)
    small=DiamondROIDetector(affine,background_radius=40)
    np.testing.assert_allclose(direct._arguments[0],small._arguments[0],rtol=1e-14,atol=1e-15)
    np.testing.assert_allclose(direct._arguments[1],small._arguments[1],rtol=1e-14)
    image=600+np.random.default_rng(99).normal(0,4,shape)+1000*np.exp(-((x-70)**2+(y-70)**2)/128)
    expected=direct.compute_mask(image)
    assert expected.any()
    np.testing.assert_array_equal(small.compute_mask(image),expected)
    copied=small.copy()
    np.testing.assert_array_equal(copied.compute_mask(image),expected)
    assert not copied.compute_mask(np.zeros_like(image)).any()
    np.testing.assert_array_equal(small.compute_mask(image),expected)


def test_whole_aperture_is_rejected_even_with_centroid_outside_mask():
    from phasesmith.experimental.spots import SpotTable

    table=SpotTable(np.array([[2,2,8,8],[12,12,18,18]]),
                    np.ones((2,11)),np.zeros(2,np.uint32))
    mask=np.zeros((20,20),bool)
    mask[7,7]=True
    kept,rejected=exclude_overlapping_spots(table,mask)
    assert rejected==1
    np.testing.assert_array_equal(kept.boxes,table.boxes[1:])
    assert len(table)==2  # Original immutable measurements unchanged.


def test_one_overlapping_observation_rejects_whole_linked_track():
    from phasesmith.experimental.rotation import PositionTable

    table=PositionTable(np.array([[2,2,8,8],[12,12,18,18]]),np.array([[0,2],[0,2]]),
                        np.ones((2,5)),np.zeros(2,np.uint32),
                        np.array([[0,0,4,4,.5],[0,1,5,4,1.5],
                                  [1,0,14,14,.5],[1,1,15,14,1.5]]),
                        np.array([[0,1],[1,2]]),('first','second'))
    kept,rejected=exclude_overlapping_tracks(table,{observation_key(1,5,4)})
    assert rejected==1 and len(kept)==1
    assert np.all(kept.observations[:,0]==0)
    np.testing.assert_array_equal(kept.observations[:,1:],table.observations[2:,1:])
    assert kept.frame_hashes==table.frame_hashes


def test_failed_or_slow_mask_aborts_series_instead_of_using_unmasked_data(tmp_path):
    from .test_RotationSeries import make_run
    from ...model.rotation_series import SeriesTask, import_series, locate_positions

    class FailedPlan:
        def compute(self,*args,**kwargs):
            raise RuntimeError("Diamond ROI detection exceeded 10 ms; no mask returned")
    task=SeriesTask(import_series(make_run(tmp_path)),np.zeros((48,60),bool),{},
                    diamond_plan=FailedPlan())
    with pytest.raises(RuntimeError,match="exceeded 10 ms"):
        locate_positions(task)


def test_series_uses_each_frames_mask_and_rejects_touching_tracks(tmp_path):
    from .test_RotationSeries import make_run
    from ...model.rotation_series import SeriesTask, import_series, locate_positions, read_frame

    class MovingPlan:
        def __init__(self):self.calls=[]
        def compute(self,image,existing_mask=None,*,frame=None):
            self.calls.append(frame)
            mask=np.zeros(image.shape,bool)
            # Test fixture's peak moves with the frame; touch its aperture in
            # only one frame so the whole track must be rejected after linking.
            if frame==2:mask[24,24]=True
            return mask
        def metadata(self):return dict(algorithm='test-moving-mask')
    series=import_series(make_run(tmp_path))
    plan=MovingPlan()
    task=SeriesTask(series,np.zeros((48,60),bool),{},diamond_plan=plan)
    previews=[]
    result=locate_positions(task,preview=previews.append)
    assert plan.calls==list(range(5))
    assert [p.index for p in previews]==list(range(5))
    for p in previews:
        assert p.mask is not None and not p.mask.flags.writeable
        np.testing.assert_array_equal(p.image,read_frame(series.files[p.index]))
    assert result.metadata['diamond_mask']['algorithm']=='test-moving-mask'
    assert result.metadata['diamond_mask']['rejected_tracks']==1
    assert result.metadata['diamond_mask']['rejected_observations']==1
    assert len(result.table)==0 and len(result.table.observations)==0
