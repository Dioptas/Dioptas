"""Qt OverlayWidget operations against the existing OverlayModel, without Qt."""

from pathlib import Path

import numpy as np

from .integration import boolean, finite


def set_background(session, overlay):
    """Mirror Qt's background assignment and checkbox visibility callbacks."""
    pattern = session.configuration.pattern_model
    previous = pattern.background_pattern
    if previous is not None and previous is not overlay:
        previous.visible = True
    pattern.params.background_overlay_uid = (
        overlay.params.uid if overlay is not None else ""
    )
    # Also handles anonymous backgrounds in older projects.
    if pattern.background_pattern is not overlay:
        pattern.background_pattern = overlay
    if overlay is not None:
        overlay.visible = False


def update_overlay(session, operation, index=None, path=None, paths=None, **changes):
    model = session._model.overlay_model
    pattern = session.configuration.pattern_model
    if operation == "original_color":
        pattern.params.color = session._integration_color(changes.get("color"))
    elif operation == "original_visibility":
        pattern.params.visible = boolean(changes.get("visible"), "visible")
    elif operation == "load":
        if paths is None:
            if path is not None:
                paths = [path]
            elif session._choose_file is not None:
                paths = session._choose_file("overlays", False)
            else:
                raise ValueError("Choose overlay files in the desktop application.")
        if not paths:
            return {"cancelled": True}
        if isinstance(paths, str):
            paths = [paths]
        resolved = [session._path(p, "pattern") for p in paths]
        for filename in resolved:
            model.add_overlay_file(filename)
        session._model.working_directories["overlay"] = str(Path(resolved[0]).parent)
    elif operation in {"capture", "capture_background"}:
        if not len(pattern.pattern.x):
            raise ValueError("Load or integrate a pattern first.")
        model.add_overlay_pattern(pattern.pattern)
        if operation == "capture_background":
            set_background(session, model.overlays[-1])
    elif operation == "clear":
        if pattern.background_pattern in model.overlays:
            set_background(session, None)
        model.reset()
        pattern.params.visible = True
    elif operation in {"waterfall", "waterfall_separation"}:
        separation = finite(
            changes.get("separation", session._model.view.waterfall_separation),
            "Separation",
            -100000,
            100000,
        )
        session._model.view.waterfall_separation = separation
        if operation == "waterfall":
            model.overlay_waterfall(separation)
    elif operation == "reset_offsets":
        model.reset_overlay_offsets()
    elif operation == "color_scale":
        colors = changes.get("colors")
        if not isinstance(colors, list) or len(colors) != len(model.overlays):
            raise ValueError("Choose one color for every overlay.")
        validated = [session._integration_color(color) for color in colors]
        for i, color in enumerate(validated):
            model.set_overlay_color(i, color)
    elif operation == "visibility":
        visible = boolean(changes["visible"], "visible")
        for i in range(len(model.overlays)):
            model.set_overlay_visible(i, visible)
    else:
        index = finite(index, "Overlay index", 0, len(model.overlays) - 1, True)
        overlay = model.overlays[index]
        if operation == "remove":
            if pattern.background_pattern is overlay:
                set_background(session, None)
            model.remove_overlay(index)
            if not model.overlays:
                pattern.params.visible = True
        elif operation == "background":
            set_background(
                session, None if pattern.background_pattern is overlay else overlay
            )
        elif operation == "move":
            direction = finite(changes.get("direction"), "Direction", -1, 1, True)
            if direction not in {-1, 1}:
                raise ValueError("Direction must be -1 or 1.")
            if direction < 0:
                model.move_overlay_up(index)
            else:
                model.move_overlay_down(index)
        elif operation == "match_intensity":
            # Same overlap/interpolation and least-squares factor as Qt's
            # OverlayController.match_intensity; discard offset only on success.
            px, py = pattern.pattern.data
            ox, oy = overlay._original_x, overlay._original_y
            if len(ox) and len(px):
                lower, upper = max(ox.min(), px.min()), min(ox.max(), px.max())
                if lower < upper:
                    mask = (px >= lower) & (px <= upper)
                    interpolated = np.interp(px[mask], ox, oy)
                    denominator = interpolated @ interpolated
                    if denominator != 0:
                        scale = float((interpolated @ py[mask]) / denominator)
                        model.set_overlay_offset(index, 0)
                        model.set_overlay_scaling(index, scale)
        elif operation == "update":
            # Validate the complete edit before mutating the scientific model.
            validated = {}
            for key, value in changes.items():
                if key in {"scale", "offset"}:
                    value = finite(value, key, -9999999, 9999999)
                elif key == "visible":
                    value = boolean(value, key)
                elif key == "color":
                    value = session._integration_color(value)
                elif key == "name":
                    if not isinstance(value, str):
                        raise ValueError("Overlay name must be text.")
                else:
                    raise ValueError("Unknown overlay option.")
                validated[key] = value
            for key, value in validated.items():
                getattr(model, "set_overlay_" + {"scale": "scaling"}.get(key, key))(
                    index, value
                )
        else:
            raise ValueError("Unknown overlay operation.")
    session._refresh_integration_pattern()
    session._revision += 1
    return {**session._state(), "pattern": session._pattern, "patternOnly": True}
