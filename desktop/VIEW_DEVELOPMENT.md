# Mask, Integration and Map implementation

The reference is current Qt Dioptas source in
`/Users/clemens/Programming/Dioptas` (read-only), together with equivalent files
in this checkout. Preserve Qt organization and established user interactions,
making restrained visual improvements where controls are awkward. Existing
calibration and shared display behavior are regression requirements.

| View | Main Qt reference | Implementation branch |
| --- | --- | --- |
| Mask | `widgets/MaskWidget.py`, `controller/MaskController.py`, `model/MaskModel.py`, `widgets/MaskPluginWidget.py` | `codex/desktop-mask` |
| Integration | `widgets/integration/control/`, `widgets/integration/display/`, `controller/integration/`, configuration/image/pattern models | `codex/desktop-integration` |
| Map | `widgets/MapWidget.py`, `MapPanelWidget.py`, `MapLayerWidget.py`, `MapGridPopup.py`, `controller/MapController.py`, `MapPanelController.py`, `integration/MapRoiInPatternController.py`, `model/MapModel.py`, `BatchModel.py` | `codex/desktop-map` |

Paths in the table are relative to `dioptas/` in the Qt reference. Each view chat
must first compare actual controls and model/controller behavior, then implement
working UI connected to real data. Audit optional plugins/dependencies without
making them mandatory. Do not replace Qt science with simulated values.

Prefer MaskView, IntegrationView and MapView components and corresponding domain
modules. Shared session/transport extensions must retain progress/cancel
responsiveness, single-thread scientific ownership, error handling and native
file dialog support. Extend Tauri's file-command mapping if a new action needs
a chooser; a button that works only through a browser-test stub is incomplete.

Document Qt parity and remaining limitations for each view. Commit completed
changes on the assigned branch, without pushing or merging into the primary
preview. Report tests and commit IDs so the parent chat can integrate the views.
