# SPDX-License-Identifier: MIT

from .threshold import ThresholdMaskPlugin
from .cosmic import CosmicRayMaskPlugin

BUILTIN_MASK_PLUGINS = [
    ThresholdMaskPlugin,
    CosmicRayMaskPlugin,
]
