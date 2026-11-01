"""Export installed pyqtgraph gradients/maps as frontend lookup tables (build time only)."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
from pathlib import Path
import shutil
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets
from pyqtgraph.graphicsItems.GradientEditorItem import Gradients, GradientEditorItem

root = Path(__file__).resolve().parents[1]
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
# Dioptas additions from HistogramLUTItem.py, without importing its GUI at runtime.
Gradients["grey_inverse"] = {"mode":"rgb", "ticks":[(0,(255,255,255,255)),(1,(0,0,0,255))]}
Gradients["jet"] = {"mode":"rgb", "ticks":[(0,(0,0,128,255)),(.1,(0,0,255,255)),(.4,(0,255,255,255)),(.5,(0,255,0,255)),(.6,(255,255,0,255)),(.9,(255,0,0,255)),(1,(128,0,0,255))]}
catalog = {}
for name in Gradients:
    editor = GradientEditorItem()
    editor.restoreState(Gradients[name])
    colors = editor.getLookupTable(512, alpha=False)
    catalog[name] = {"label":name.replace("_", " ").capitalize(), "colors":colors[:,:3].astype(int).tolist()}
for name in sorted(pg.colormap.listMaps()):
    if name in catalog or name.startswith(("CET", "PAL")):
        continue
    colors = pg.colormap.get(name).map(np.linspace(0,1,512), mode="byte")
    catalog[name] = {"label":name, "colors":colors[:,:3].astype(int).tolist()}
(root / "src/pyqtgraph-colormaps.json").write_text(json.dumps(catalog,separators=(",",":"))+"\n")
licenses = root / "licenses/colormaps"
licenses.mkdir(parents=True,exist_ok=True)
package = Path(pg.__file__).parent
for path in (package / "colors/maps").glob("*.txt"):
    if path.name.startswith("CC0"):
        shutil.copyfile(path, licenses / path.name)
(licenses / "CC-BY license - applies to CET color map data.txt").unlink(missing_ok=True)
shutil.copyfile(package.parent / f"pyqtgraph-{pg.__version__}.dist-info/LICENSE.txt", licenses / "pyqtgraph-MIT.txt")
(licenses / "README.md").write_text(f'''# Colour lookup tables

Generated from installed pyqtgraph {pg.__version__} by `desktop/scripts/export_colormaps.py`.
The frontend samples each gradient/map at 512 positions. HSV gradients are sampled
by pyqtgraph itself. Dioptas's `grey_inverse` and `jet` additions are included.

Pyqtgraph gradient definitions are MIT licensed; see pyqtgraph-MIT.txt.
CET and PAL maps are excluded. Only the standard Dioptas/pyqtgraph choices are shipped.
Viridis, magma, plasma, inferno and cividis include the upstream CC0 dedication.
The tables are resampled representations, not new colour-map definitions.
Source: https://github.com/pyqtgraph/pyqtgraph/tree/pyqtgraph-{pg.__version__}/pyqtgraph/colors
''')
print(f"Exported {len(catalog)} pyqtgraph colour scales")
