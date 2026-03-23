# SPDX-License-Identifier: MIT
"""Tests that non-ASCII (Chinese, accented, etc.) characters in file paths
are handled correctly throughout the application."""

import os
import shutil
import tempfile

import numpy as np
import pytest

from ...model.ImgModel import ImgModel
from ...model.MaskModel import MaskModel
from ...model.PatternModel import PatternModel
from ...model.DioptasModel import DioptasModel

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")


@pytest.fixture
def unicode_dir():
    """Create a temporary directory with Chinese characters in the path."""
    base = tempfile.mkdtemp()
    unicode_path = os.path.join(base, "数据_données_データ")
    os.makedirs(unicode_path)
    yield unicode_path
    shutil.rmtree(base)


@pytest.fixture
def img_model():
    return ImgModel()


def test_load_image_from_unicode_path(img_model, unicode_dir):
    """Images can be loaded when the path contains non-ASCII characters."""
    src = os.path.join(data_path, "image_001.tif")
    dst = os.path.join(unicode_dir, "图像_001.tif")
    shutil.copy2(src, dst)

    img_model.load(dst)
    assert img_model.img_data is not None
    assert img_model.filename == dst


def test_save_image_to_unicode_path(img_model, unicode_dir):
    """Images can be saved when the destination path contains non-ASCII characters."""
    img_model.load(os.path.join(data_path, "image_001.tif"))
    dst = os.path.join(unicode_dir, "保存_image.tif")
    img_model.save(dst)
    assert os.path.exists(dst)


def test_load_mask_from_unicode_path(unicode_dir):
    """Masks can be loaded from paths with non-ASCII characters."""
    mask_model = MaskModel(mask_dimension=(100, 100))
    mask_data = np.zeros((100, 100), dtype=bool)
    mask_data[10:20, 10:20] = True

    mask_path = os.path.join(unicode_dir, "掩膜.npy")
    np.save(mask_path, mask_data)

    mask_model.load_mask(mask_path)
    assert np.any(mask_model.get_mask())


def test_save_mask_to_unicode_path(unicode_dir):
    """Masks can be saved to paths with non-ASCII characters."""
    mask_model = MaskModel(mask_dimension=(100, 100))
    mask_model.mask_rect(10, 10, 20, 20)

    mask_path = os.path.join(unicode_dir, "掩膜.npy")
    mask_model.save_mask(mask_path)
    assert os.path.exists(mask_path)


def test_save_load_pattern_unicode_path(unicode_dir):
    """Patterns can be saved to and loaded from paths with non-ASCII characters."""
    pattern_model = PatternModel()
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    pattern_model.set_pattern(x, y)

    pattern_path = os.path.join(unicode_dir, "衍射_pattern.xy")
    pattern_model.save_pattern(pattern_path)
    assert os.path.exists(pattern_path)

    pattern_model2 = PatternModel()
    pattern_model2.load_pattern(pattern_path)
    assert len(pattern_model2.pattern.x) > 0


def test_save_load_project_unicode_path(dioptas_model, unicode_dir):
    """Dioptas .dio projects can be saved/loaded from paths with non-ASCII characters."""
    dioptas_model.img_model.load(os.path.join(data_path, "image_001.tif"))

    project_path = os.path.join(unicode_dir, "项目_project.dio")
    dioptas_model.save(project_path)
    assert os.path.exists(project_path)

    model2 = DioptasModel()
    model2.load(project_path)
    assert model2.img_model.img_data is not None


def test_load_background_from_unicode_path(img_model, unicode_dir):
    """Background images can be loaded from paths with non-ASCII characters."""
    src = os.path.join(data_path, "image_001.tif")
    dst = os.path.join(unicode_dir, "背景_background.tif")
    shutil.copy2(src, dst)

    img_model.load(os.path.join(data_path, "image_001.tif"))
    img_model.load_background(dst)
    assert img_model.has_background()
