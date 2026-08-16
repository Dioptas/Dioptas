# SPDX-License-Identifier: MIT

import pytest
from mock import MagicMock, patch
import os

import h5py
import numpy as np

from ...model.ImgModel import ImgModel, BackgroundDimensionWrongException
from ...model.util.ImgCorrection import DummyCorrection
from ...model.loader.KaraboLoader import extra_data_installed

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")
spe_path = os.path.join(data_path, "spe")


@pytest.fixture
def img_model():
    img_model = ImgModel()
    img_model.load(os.path.join(data_path, "image_001.tif"))
    return ImgModel()


def test_load_karabo_nexus_file(img_model):
    img_model.load(os.path.join(data_path, "karabo_epix.h5"))


def perform_transformations_tests(img_model):
    assert np.sum(np.absolute(img_model.img_data)) == 0
    img_model.rotate_img_m90()
    assert np.sum(np.absolute(img_model.img_data)) == 0
    img_model.flip_img_horizontally()
    assert np.sum(np.absolute(img_model.img_data)) == 0
    img_model.rotate_img_p90()
    assert np.sum(np.absolute(img_model.img_data)) == 0
    img_model.flip_img_vertically()
    assert np.sum(np.absolute(img_model.img_data)) == 0
    img_model.reset_transformations()
    assert np.sum(np.absolute(img_model.img_data)) == 0


def test_load_emits_signal(img_model):
    callback_fcn = MagicMock()
    img_model.img_changed.connect(callback_fcn)
    img_model.load(os.path.join(data_path, "image_001.tif"))
    callback_fcn.assert_called_once_with()


def test_flipping_images(img_model):
    original_image = np.copy(img_model._img_data)
    img_model.flip_img_vertically()
    assert np.array_equal(img_model._img_data, np.flipud(original_image))


def test_simple_background_subtraction(img_model):
    first_image = np.copy(img_model.img_data)
    img_model.load_next_file()
    second_image = np.copy(img_model.img_data)

    img_model.load(os.path.join(data_path, "image_001.tif"))
    img_model.load_background(os.path.join(data_path, "image_002.tif"))

    assert not np.array_equal(first_image, img_model.img_data)

    img_model.load_next_file()
    assert np.sum(img_model.img_data) == 0


def test_background_subtraction_with_transformation(img_model):
    img_model.load_background(os.path.join(data_path, "image_002.tif"))
    original_img = np.copy(img_model._img_data)
    original_background = np.copy(img_model._background_data)

    assert img_model._background_data is not None
    assert not np.array_equal(img_model.img_data, img_model._img_data)

    original_img_background_subtracted = np.copy(img_model.img_data)
    assert np.array_equal(
        original_img_background_subtracted, original_img - original_background
    )

    ### now comes the main process - flipping the image
    img_model.flip_img_vertically()
    flipped_img = np.copy(img_model._img_data)
    assert np.array_equal(np.flipud(original_img), flipped_img)

    flipped_background = np.copy(img_model._background_data)
    assert np.array_equal(np.flipud(original_background), flipped_background)

    flipped_img_background_subtracted = np.copy(img_model.img_data)
    assert np.array_equal(
        flipped_img_background_subtracted, flipped_img - flipped_background
    )

    assert np.array_equal(
        np.flipud(original_img_background_subtracted), flipped_img_background_subtracted
    )
    assert (
        np.sum(
            np.flipud(original_img_background_subtracted)
            - flipped_img_background_subtracted
        )
        == 0
    )

    img_model.load(os.path.join(data_path, "image_002.tif"))
    perform_transformations_tests(img_model)


def test_background_scaling_and_offset(img_model):
    img_model.load_background(os.path.join(data_path, "image_002.tif"))

    # assure that everything is correct before
    assert np.array_equal(
        img_model.img_data, img_model._img_data - img_model._background_data
    )

    # set scaling and see difference
    img_model.background_scaling = 2.4
    assert np.array_equal(
        img_model.img_data, img_model._img_data - 2.4 * img_model._background_data
    )

    # set offset and see the difference
    img_model.background_scaling = 1.0
    img_model.background_offset = 100.0
    assert np.array_equal(
        img_model.img_data, img_model._img_data - (img_model._background_data + 100.0)
    )

    # use offset and scaling combined
    img_model.background_scaling = 2.3
    img_model.background_offset = 100.0
    assert np.array_equal(
        img_model.img_data,
        img_model._img_data - (2.3 * img_model._background_data + 100),
    )


def test_background_with_different_shape(img_model):
    with pytest.raises(BackgroundDimensionWrongException):
        img_model.load_background(os.path.join(data_path, "CeO2_Pilatus1M.tif"))
    assert img_model._background_data is None

    img_model.load_background(os.path.join(data_path, "image_002.tif"))
    assert img_model._background_data is not None

    img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))
    assert img_model._background_data is None


def test_absorption_correction_with_different_image_sizes(img_model):
    dummy_correction = DummyCorrection(img_model.img_data.shape, 0.4)
    # self.img_data.set_absorption_correction(np.ones(self.img_data._img_data.shape)*0.4)
    img_model.add_img_correction(dummy_correction, "Dummy 1")
    assert img_model._img_corrections.has_items()

    img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))
    assert not img_model.has_corrections()


def test_adding_several_absorption_corrections(img_model):
    original_image = np.copy(img_model.img_data)
    img_shape = original_image.shape
    img_model.add_img_correction(DummyCorrection(img_shape, 0.4))
    img_model.add_img_correction(DummyCorrection(img_shape, 3))
    img_model.add_img_correction(DummyCorrection(img_shape, 5))

    assert np.sum(original_image) / (0.5 * 3 * 5) == np.sum(img_model.img_data)

    img_model.delete_img_correction(1)
    assert np.sum(original_image) / (0.5 * 5) == np.sum(img_model.img_data)


def test_saving_data(img_model, tmp_path):
    img_model.load(os.path.join(data_path, "image_001.tif"))
    filename = os.path.join(tmp_path, "test.tif")
    img_model.save(filename)
    first_img_array = np.copy(img_model._img_data)
    img_model.load(filename)
    assert np.array_equal(first_img_array, img_model._img_data)
    assert os.path.exists(filename)


def test_negative_rotation(img_model):
    pre_transformed_data = img_model.img_data
    img_model.rotate_img_m90()
    img_model.rotate_img_m90()
    img_model.rotate_img_m90()
    img_model.rotate_img_m90()
    assert np.array_equal(img_model.img_data, pre_transformed_data)


def test_combined_rotation(img_model):
    pre_transformed_data = img_model.img_data
    img_model.rotate_img_m90()
    img_model.rotate_img_p90()
    assert np.array_equal(img_model.img_data, pre_transformed_data)


def test_flip_img_horizontally(img_model):
    pre_transformed_data = img_model.img_data
    img_model.flip_img_horizontally()
    img_model.flip_img_horizontally()
    assert np.array_equal(img_model.img_data, pre_transformed_data)


def test_flip_img_vertically(img_model):
    pre_transformed_data = img_model.img_data
    img_model.flip_img_vertically()
    img_model.flip_img_vertically()
    assert np.array_equal(img_model.img_data, pre_transformed_data)


def test_combined_rotation_and_flipping(img_model):
    img_model.load(os.path.join(data_path, "image_001.tif"))
    img_model.flip_img_vertically()
    img_model.flip_img_horizontally()
    img_model.rotate_img_m90()
    img_model.rotate_img_p90()
    img_model.rotate_img_m90()
    img_model.rotate_img_m90()
    img_model.flip_img_horizontally()
    transformed_data = img_model.img_data
    img_model.load(os.path.join(data_path, "image_001.tif"))
    assert np.array_equal(img_model.img_data, transformed_data)


def test_reset_img_transformation(img_model):
    pre_transformed_data = img_model.img_data
    img_model.rotate_img_m90()
    img_model.reset_transformations()
    assert np.array_equal(img_model.img_data, pre_transformed_data)

    pre_transformed_data = img_model.img_data
    img_model.rotate_img_p90()
    img_model.reset_transformations()
    assert np.array_equal(img_model.img_data, pre_transformed_data)

    pre_transformed_data = img_model.img_data
    img_model.flip_img_horizontally()
    img_model.reset_transformations()
    assert np.array_equal(img_model.img_data, pre_transformed_data)

    pre_transformed_data = img_model.img_data
    img_model.flip_img_vertically()
    img_model.reset_transformations()
    assert np.array_equal(img_model.img_data, pre_transformed_data)

    pre_transformed_data = img_model.img_data
    img_model.flip_img_vertically()
    img_model.flip_img_horizontally()
    img_model.rotate_img_m90()
    img_model.rotate_img_p90()
    img_model.rotate_img_m90()
    img_model.rotate_img_m90()
    img_model.flip_img_horizontally()
    img_model.reset_transformations()
    assert np.array_equal(img_model.img_data, pre_transformed_data)


def test_loading_a_tagged_tif_file_and_retrieving_info_string(img_model):
    img_model.load(os.path.join(data_path, "attrib.tif"))
    assert "areaDetector" in img_model.file_info


def test_loading_spe_file(img_model):
    img_model.load(os.path.join(spe_path, "CeO2_PI_CCD_Mo.SPE"))
    assert img_model.img_data.shape == (1042, 1042)


def test_loading_ESRF_hdf5_file(img_model):
    img_model.load(os.path.join(data_path, "hdf5_dataset", "ma4500_demoh5.h5"))
    assert img_model.img_data.shape == (2048, 2048)

    img1 = img_model.img_data
    img_model.select_source(img_model.sources[2])
    img2 = img_model.img_data
    assert np.sum(img1 - img2) != 0


def test_loading_hdf5_with_missing_external_data_shows_clear_error(tmp_path):
    from dioptas.model.util.file_type import FileLoadingError

    master_filename = tmp_path / "scan_master.h5"
    companion_basename = "scan_data_000001.h5"
    with h5py.File(master_filename, "w") as master_file:
        data_group = master_file.create_group("entry/data")
        data_group["data_000001"] = h5py.ExternalLink(
            companion_basename, "/entry/data/data"
        )

    with pytest.raises(FileLoadingError) as exc_info:
        ImgModel().load(str(master_filename))

    message = str(exc_info.value)
    assert "external HDF5 companion file" in message
    assert "missing" in message
    assert str(tmp_path / companion_basename) in message


def test_loading_hdf5_follows_external_data_link(tmp_path):
    master_filename = tmp_path / "scan_master.h5"
    companion_basename = "scan_data_000001.h5"
    companion_filename = tmp_path / companion_basename
    image = np.arange(6, dtype=np.uint16).reshape(1, 2, 3)

    with h5py.File(companion_filename, "w") as companion_file:
        companion_file.create_dataset("entry/data/data", data=image)
    with h5py.File(master_filename, "w") as master_file:
        data_group = master_file.create_group("entry/data")
        data_group["data_000001"] = h5py.ExternalLink(
            companion_basename, "/entry/data/data"
        )

    img_model = ImgModel()
    img_model.load(str(master_filename))

    assert np.array_equal(img_model.img_data, image[0][::-1])


def test_summing_files(img_model):
    img_model.load(os.path.join(data_path, "image_001.tif"))
    data1 = np.copy(img_model._img_data).astype(np.uint64)
    img_model.add(os.path.join(data_path, "image_001.tif"))
    assert np.array_equal(2 * data1, img_model._img_data)


def test_summing_rotated(img_model):
    img_model.load(os.path.join(data_path, "image_001.tif"))
    img_model.rotate_img_m90()
    data1 = np.copy(img_model._img_data).astype(np.uint32)
    img_model.add(os.path.join(data_path, "image_001.tif"))
    assert np.array_equal(2 * data1, img_model._img_data)


def test_loading_karabo_file(img_model):
    img_model.load(os.path.join(data_path, "karabo_epix.h5"))
    assert img_model.img_data.shape == (356, 384)


def test_loading_karabo_file_without_extra_data(img_model):
    """Test that loading a karabo file when extra_data is not installed returns None"""
    with patch("dioptas.model.loader.KaraboLoader.extra_data_installed", False):
        # Try to load a karabo file
        result = img_model.load(os.path.join(data_path, "karabo_epix.h5"))
        assert result is None

        # Verify that other file types still work
        img_model.load(os.path.join(data_path, "image_001.tif"))
        assert img_model.img_data is not None


def test_img_model_settings_delegate_to_params():
    from dioptas.model.ImgModel import ImgModel

    img_model = ImgModel()
    emitted = []
    img_model.img_changed.connect(lambda: emitted.append(1))

    img_model.factor = 2.5
    assert img_model.params.factor == 2.5
    assert len(emitted) == 1  # property setter keeps its side effect

    img_model.params.factor = 3.0  # direct write behaves like the property
    assert img_model.factor == 3.0
    assert len(emitted) == 2

    img_model.file_iteration_mode = "time"
    assert img_model.params.file_iteration_mode == "time"


def test_transformations_are_canonical_in_params():
    from dioptas.model.ImgModel import ImgModel

    img_model = ImgModel()
    img_model.rotate_img_p90()
    img_model.flip_img_horizontally()
    assert img_model.params.transformations == ["rotate_matrix_p90", "fliplr"]
    assert img_model.get_transformations_string_list() == [
        "rotate_matrix_p90",
        "fliplr",
    ]

    # the callable list derives from the names
    import numpy as np
    from dioptas.model.util.HelperModule import rotate_matrix_p90

    assert img_model.img_transformations == [rotate_matrix_p90, np.fliplr]

    img_model.load_transformations_string_list(["flipud"])
    assert img_model.params.transformations == ["flipud"]

    img_model.load_transformations_string_list(["not_a_transformation"])
    assert img_model.params.transformations == []


def test_direct_img_params_writes_trigger_same_reactions():
    """Uniform writes: direct params writes behave like property writes."""
    from dioptas.model.ImgModel import ImgModel

    img_model = ImgModel()
    emitted = []
    img_model.img_changed.connect(lambda: emitted.append(1))

    img_model.params.factor = 2  # int, direct write
    assert len(emitted) == 1
    assert isinstance(img_model.params.factor, float)  # coerced in reaction

    img_model.params.background_scaling = 3
    assert len(emitted) == 2
    assert isinstance(img_model.params.background_scaling, float)

    img_model.params.autoprocess = True
    assert img_model._directory_watcher._active if hasattr(
        img_model._directory_watcher, "_active"
    ) else True
    img_model.params.autoprocess = False


def test_loading_rgb_png_converts_to_grayscale(tmp_path):
    """Color previews (e.g. beamline PNG exports) must not enter the 2D-only
    processing chain as 3D arrays; they are averaged to grayscale instead."""
    from PIL import Image

    rgb = np.zeros((40, 50, 3), dtype=np.uint8)
    rgb[..., 0] = 30
    rgb[..., 1] = 60
    rgb[..., 2] = 90
    filename = str(tmp_path / "preview_rgb.png")
    Image.fromarray(rgb).save(filename)

    img_model = ImgModel()
    img_model.load(filename)

    assert img_model.img_data.ndim == 2
    assert img_model.img_data.shape == (40, 50)
    assert np.allclose(img_model.img_data, 60.0)


def test_loading_rgba_png_ignores_alpha(tmp_path):
    from PIL import Image

    rgba = np.zeros((40, 50, 4), dtype=np.uint8)
    rgba[..., 0] = 30
    rgba[..., 1] = 60
    rgba[..., 2] = 90
    rgba[..., 3] = 255
    filename = str(tmp_path / "preview_rgba.png")
    Image.fromarray(rgba).save(filename)

    img_model = ImgModel()
    img_model.load(filename)

    assert img_model.img_data.ndim == 2
    assert np.allclose(img_model.img_data, 60.0)


def test_loading_grayscale_alpha_png_uses_luminance(tmp_path):
    from PIL import Image

    la = np.zeros((40, 50, 2), dtype=np.uint8)
    la[..., 0] = 120
    la[..., 1] = 255
    filename = str(tmp_path / "preview_la.png")
    Image.fromarray(la, mode="LA").save(filename)

    img_model = ImgModel()
    img_model.load(filename)

    assert img_model.img_data.ndim == 2
    assert np.allclose(img_model.img_data, 120.0)


def test_ensure_grayscale_refuses_unexpected_shapes():
    from dioptas.model.util.file_type import FileLoadingError

    with pytest.raises(FileLoadingError):
        ImgModel._ensure_grayscale(np.zeros((5, 5, 7)), "strange.h5")


def test_color_background_image_matches_grayscale_image(tmp_path):
    """A color PNG used as background goes through the same conversion, so it
    stays shape-compatible with a grayscale foreground of the same size."""
    from PIL import Image

    rgb = np.full((40, 50, 3), 90, dtype=np.uint8)
    filename = str(tmp_path / "background_rgb.png")
    Image.fromarray(rgb).save(filename)

    img_model = ImgModel()
    img_model._img_data = np.ones((40, 50))
    img_model.load_background(filename)

    assert img_model._background_data.shape == (40, 50)
