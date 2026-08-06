# SPDX-License-Identifier: MIT

"""Arithmetic over map layers.

Two windows answer more together than apart: the ratio of two peaks is a
phase fraction, a difference is what one phase contributes over another, and
``(A-B)/(A+B)`` is a contrast that survives changes in illumination. Rather
than build a fixed set of those, layers can be combined by writing the
expression.

Expressions are evaluated over whole layers at once, so ``A/B`` divides the
two arrays element-wise and yields a third layer. Only arithmetic on the
named layers and numbers is allowed — the expression is parsed into an AST
and walked, so nothing outside this grammar can run.

``ovl(overlay, window)`` brings an overlay in: the overlay put through the
given window — its range, value kind and background setting — as one number,
the same for every map point. ``A - ovl(bkg_empty)`` is then the difference
to that reference; with a single window in the expression the window
argument can be left out, otherwise it is required, since guessing which
window was meant would be worse than asking.
"""

from __future__ import annotations

import ast
import logging
import operator

import numpy as np

__all__ = [
    "OVL",
    "evaluate",
    "referenced_names",
    "rename",
    "reserved_names",
    "validate",
]

logger = logging.getLogger(__name__)

_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}

_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

#: element-wise functions an expression may call
_FUNCTIONS = {
    "abs": np.abs,
    "sqrt": np.sqrt,
    "log": np.log,
    "log10": np.log10,
    "exp": np.exp,
    "clip": np.clip,
    "minimum": np.minimum,
    "maximum": np.maximum,
}


#: name of the overlay-reference function
OVL = "ovl"


def reserved_names() -> set[str]:
    """Names the expression grammar claims for itself.

    A window called "sqrt" or "ovl" would shadow them and turn valid
    expressions ambiguous, so these are not usable as window names.
    """
    return set(_FUNCTIONS) | {OVL}


class ExpressionError(ValueError):
    """An expression that cannot be parsed, or refers to something unknown."""


def _ovl_parts(node: ast.Call) -> tuple[str, str | None]:
    """The (overlay name, window name or None) of an ``ovl(...)`` call."""
    if node.keywords or not 1 <= len(node.args) <= 2:
        raise ExpressionError(
            "ovl takes the overlay and optionally the window: "
            "ovl(overlay) or ovl(overlay, window)"
        )
    first = node.args[0]
    if isinstance(first, ast.Name):
        overlay = first.id
    elif isinstance(first, ast.Constant) and isinstance(first.value, str):
        # for overlay names that are not plain identifiers ("my bkg")
        overlay = first.value
    else:
        raise ExpressionError("ovl expects an overlay name")
    window = None
    if len(node.args) == 2:
        if not isinstance(node.args[1], ast.Name):
            raise ExpressionError("the second argument of ovl is a window name")
        window = node.args[1].id
    return overlay, window


def _parse(expression: str) -> ast.expr:
    try:
        return ast.parse(expression.strip(), mode="eval").body
    except SyntaxError as error:
        raise ExpressionError(str(error)) from error


def referenced_names(expression: str) -> set[str]:
    """Layer names an expression mentions.

    Function names are excluded, and so is the overlay argument of ovl():
    it names an overlay, not a layer — the window argument counts.
    """
    try:
        tree = _parse(expression)
    except ExpressionError:
        return set()
    overlay_args = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == OVL
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            overlay_args.add(id(node.args[0]))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id not in _FUNCTIONS and node.id != OVL and id(node) not in overlay_args:
                names.add(node.id)
    return names


def rename(expression: str, old_name: str, new_name: str) -> str:
    """Rewrites *expression* with one layer name changed.

    Done on the token level rather than by string replacement so a name that
    happens to be a substring of another is left alone.
    """
    if old_name not in referenced_names(expression):
        return expression
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError:
        return expression
    overlay_args = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == OVL
            and node.args
        ):
            # the overlay argument stays: it names an overlay, and a window
            # sharing its name is a coincidence
            overlay_args.add(id(node.args[0]))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Name)
            and node.id == old_name
            and id(node) not in overlay_args
        ):
            node.id = new_name
    return ast.unparse(tree.body)


def validate(
    expression: str, available: set[str], overlay_exists=None
) -> str | None:
    """Returns why *expression* cannot be used, or None if it can.

    *overlay_exists* is an optional callable checking ovl() references;
    without it, overlay names are taken on trust (they are checked again
    when the expression is evaluated).
    """
    try:
        tree = _parse(expression)
    except ExpressionError as error:
        return f"Cannot read the expression: {error}"
    try:
        _check(tree, available, overlay_exists)
        _check_single_arg_ovl(tree, available)
    except ExpressionError as error:
        return str(error)
    return None


def _check_single_arg_ovl(tree: ast.expr, available: set[str]) -> None:
    """ovl(overlay) without a window is only unambiguous with one window."""
    has_single = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == OVL
        and len(node.args) == 1
        for node in ast.walk(tree)
    )
    if not has_single:
        return
    windows = _referenced_windows(tree, available)
    if len(windows) != 1:
        raise ExpressionError(
            "ovl(overlay) needs the expression to use exactly one window — "
            "say which one: ovl(overlay, window)"
        )


def _referenced_windows(tree: ast.expr, available: set[str]) -> set[str]:
    overlay_args = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == OVL
            and node.args
        ):
            overlay_args.add(id(node.args[0]))
    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and node.id in available
        and id(node) not in overlay_args
    }


def _check(node: ast.expr, available: set[str], overlay_exists=None) -> None:
    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)):
            raise ExpressionError("Only numbers can be written directly")
        return
    if isinstance(node, ast.Name):
        if node.id in available or node.id in _FUNCTIONS:
            return
        raise ExpressionError(f"There is no layer called '{node.id}'")
    if isinstance(node, ast.BinOp):
        if type(node.op) not in _BINARY_OPERATORS:
            raise ExpressionError("That operator is not allowed here")
        _check(node.left, available, overlay_exists)
        _check(node.right, available, overlay_exists)
        return
    if isinstance(node, ast.UnaryOp):
        if type(node.op) not in _UNARY_OPERATORS:
            raise ExpressionError("That operator is not allowed here")
        _check(node.operand, available, overlay_exists)
        return
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == OVL:
            overlay, window = _ovl_parts(node)
            if overlay_exists is not None and not overlay_exists(overlay):
                raise ExpressionError(f"There is no overlay called '{overlay}'")
            if window is not None and window not in available:
                raise ExpressionError(f"There is no window called '{window}'")
            return
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
            raise ExpressionError(
                "Only "
                + ", ".join(sorted(_FUNCTIONS))
                + f" and {OVL} can be called"
            )
        if node.keywords:
            raise ExpressionError("Functions take plain arguments only")
        for argument in node.args:
            _check(argument, available, overlay_exists)
        return
    raise ExpressionError("Only arithmetic on the layer names is allowed")


def evaluate(expression: str, layers: dict[str, np.ndarray | None], ovl=None):
    """Evaluates *expression* over the given layers, element-wise.

    *ovl* resolves overlay references: called as ovl(overlay_name,
    window_name) and expected to return one number, or None when the
    overlay or window cannot be found.

    Returns None when the expression cannot be evaluated — an unknown name, a
    layer that has no values, or arithmetic that fails. Division by zero
    yields NaN for the affected points rather than failing outright, so one
    bad point does not cost the whole map.
    """
    usable = {name: values for name, values in layers.items() if values is not None}
    problem = validate(expression, set(usable))
    if problem is not None:
        logger.debug("map expression %r rejected: %s", expression, problem)
        return None
    try:
        tree = _parse(expression)
        windows = _referenced_windows(tree, set(usable))
        default_window = next(iter(windows)) if len(windows) == 1 else None
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            result = _evaluate(tree, usable, ovl, default_window)
    except (ExpressionError, ValueError, TypeError) as error:
        logger.debug("map expression %r failed: %s", expression, error)
        return None

    result = np.asarray(result, dtype=float)
    if result.ndim == 0:
        # a constant expression still has to cover every point
        length = len(next(iter(usable.values())))
        result = np.full(length, float(result))
    # infinities come from dividing by an empty window and are not values a
    # colour scale can do anything with
    return np.where(np.isfinite(result), result, np.nan)


def _evaluate(node, layers, ovl=None, default_window=None):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in layers:
            return layers[node.id]
        raise ExpressionError(f"There is no layer called '{node.id}'")
    if isinstance(node, ast.BinOp):
        function = _BINARY_OPERATORS[type(node.op)]
        return function(
            _evaluate(node.left, layers, ovl, default_window),
            _evaluate(node.right, layers, ovl, default_window),
        )
    if isinstance(node, ast.UnaryOp):
        function = _UNARY_OPERATORS[type(node.op)]
        return function(_evaluate(node.operand, layers, ovl, default_window))
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == OVL:
            if ovl is None:
                raise ExpressionError("Overlays are not available here")
            overlay, window = _ovl_parts(node)
            value = ovl(overlay, window or default_window)
            if value is None:
                raise ExpressionError(
                    f"The overlay '{overlay}' cannot be used here"
                )
            return float(value)
        function = _FUNCTIONS[node.func.id]
        return function(
            *[
                _evaluate(argument, layers, ovl, default_window)
                for argument in node.args
            ]
        )
    raise ExpressionError("Only arithmetic on the layer names is allowed")
