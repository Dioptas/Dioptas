# SPDX-License-Identifier: MIT

from .threshold import ThresholdMaskPlugin
from .cosmic import CosmicRayMaskPlugin
from .powder_outlier import PowderDiffSpotMaskPlugin

BUILTIN_MASK_PLUGINS = [
    ThresholdMaskPlugin,
    CosmicRayMaskPlugin,
    PowderDiffSpotMaskPlugin,
]
