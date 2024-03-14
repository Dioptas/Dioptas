import os
import subprocess

import numpy as np
from unittest.mock import MagicMock
import json
from dioptas.controller.MainController import MainController
from ..utility import click_button

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, os.pardir, "data")


def test_image_is_shown_correctly_after_tab_change(main_controller: MainController):
    dioptas_model = main_controller.model
    main_widget = main_controller.widget

    calibration_controller = main_controller.calibration_controller
    mask_controller = main_controller.mask_controller
    integration_controller = main_controller.integration_controller
    dioptas_model.img_model.load(os.path.join(data_path, "image_001.tif"))
    img_data = dioptas_model.img_model.img_data

    calibration_img_widget = calibration_controller.widget.img_widget
    assert np.array_equal(calibration_img_widget.img_data, img_data)

    click_button(main_widget.mask_mode_btn)
    mask_img_widget = mask_controller.widget.img_widget
    assert np.array_equal(mask_img_widget.img_data, img_data)

    click_button(main_widget.integration_mode_btn)
    integration_img_widget = integration_controller.widget.img_widget
    assert np.array_equal(integration_img_widget.img_data, img_data)

    click_button(main_widget.map_mode_btn)
    map_img_widget = main_controller.map_controller.widget.img_plot_widget
    assert np.array_equal(map_img_widget.img_data, img_data)

    dioptas_model.img_model.load(os.path.join(data_path, "image_002.tif"))
    img_data = dioptas_model.img_model.img_data
    click_button(main_widget.calibration_mode_btn)
    assert np.array_equal(calibration_img_widget.img_data, img_data)


def test_map_image_listening_is_enabled_after_tab_change(main_controller: MainController):
    dioptas_model = main_controller.model
    main_widget = main_controller.widget
    map_img_widget = main_controller.map_controller.widget.img_plot_widget
    click_button(main_widget.map_mode_btn)

    dioptas_model.img_model.load(os.path.join(data_path, "image_002.tif"))
    img_data = dioptas_model.img_model.img_data
    assert np.array_equal(map_img_widget.img_data, img_data)


def test_calibration_image_listener_is_enabled_after_tab_change(main_controller: MainController):
    dioptas_model = main_controller.model
    main_widget = main_controller.widget
    calibration_controller = main_controller.calibration_controller
    calibration_img_widget = calibration_controller.widget.img_widget

    click_button(main_widget.calibration_mode_btn)

    dioptas_model.img_model.load(os.path.join(data_path, "image_001.tif"))
    img_data = dioptas_model.img_model.img_data
    assert np.array_equal(calibration_img_widget.img_data, img_data)


def test_integration_image_listener_is_enabled_after_tab_change(main_controller: MainController):
    dioptas_model = main_controller.model
    main_widget = main_controller.widget
    integration_controller = main_controller.integration_controller
    integration_img_widget = integration_controller.widget.img_widget

    click_button(main_widget.integration_mode_btn)
    dioptas_model.img_model.load(os.path.join(data_path, "image_002.tif"))
    img_data = dioptas_model.img_model.img_data
    assert np.array_equal(integration_img_widget.img_data, img_data)


def test_load_with_configuration(qapp, tmp_path):
    config_file = tmp_path / "config.ini"
    config = {
        "external_actions":
            [
                {
                    "name": "A",
                    "command": "echo",
                    "arguments": "",
                },
                {
                    "name": "B",
                    "command": "sub",
                    "arguments": "-t tree",
                },
            ]
    }
    json.dump(config, open(config_file, "w"))

    main_controller = MainController(use_settings=False, config_file=config_file)
    assert main_controller.configuration == config
    assert main_controller.widget.external_action_btns["A"].text() == "A"
    assert main_controller.widget.external_action_btns["B"].text() == "B"

    img_model = main_controller.model.img_model
    img_model.load(os.path.join(data_path, "image_001.tif"))

    subprocess.Popen = MagicMock()
    click_button(main_controller.widget.external_action_btns["A"])
    subprocess.Popen.assert_called_once_with(
        [
            "echo",
            img_model.filename,
            str(img_model.series_pos),
        ],
        shell=True)

    click_button(main_controller.widget.external_action_btns["B"])
    subprocess.Popen.assert_called_with(
        [
            "sub",
            "-t",
            "tree",
            img_model.filename,
            str(img_model.series_pos),
        ],
        shell=True)