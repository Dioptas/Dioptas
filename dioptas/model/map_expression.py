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
"""

from __future__ import annotations

import ast
import logging
import operator

import numpy as np

__all__ = ["evaluate", "referenced_names", "rename", "validate"]

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


class ExpressionError(ValueError):
    """An expression that cannot be parsed, or refers to something unknown."""


def _parse(expression: str) -> ast.expr:
    try:
        return ast.parse(expression.strip(), mode="eval").body
    except SyntaxError as error:
        raise ExpressionError(str(error)) from error


def referenced_names(expression: str) -> set[str]:
    """Layer names an expression mentions (function names excluded)."""
    try:
        tree = _parse(expression)
    except ExpressionError:
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id not in _FUNCTIONS:
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
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == old_name:
            node.id = new_name
    return ast.unparse(tree.body)


def validate(expression: str, available: set[str]) -> str | None:
    """Returns why *expression* cannot be used, or None if it can."""
    try:
        tree = _parse(expression)
    except ExpressionError as error:
        return f"Cannot read the expression: {error}"
    try:
        _check(tree, available)
    except ExpressionError as error:
        return str(error)
    return None


def _check(node: ast.expr, available: set[str]) -> None:
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
        _check(node.left, available)
        _check(node.right, available)
        return
    if isinstance(node, ast.UnaryOp):
        if type(node.op) not in _UNARY_OPERATORS:
            raise ExpressionError("That operator is not allowed here")
        _check(node.operand, available)
        return
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
            raise ExpressionError(
                "Only " + ", ".join(sorted(_FUNCTIONS)) + " can be called"
            )
        if node.keywords:
            raise ExpressionError("Functions take plain arguments only")
        for argument in node.args:
            _check(argument, available)
        return
    raise ExpressionError("Only arithmetic on the layer names is allowed")


def evaluate(expression: str, layers: dict[str, np.ndarray | None]):
    """Evaluates *expression* over the given layers, element-wise.

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
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            result = _evaluate(_parse(expression), usable)
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


def _evaluate(node: ast.expr, layers: dict[str, np.ndarray]):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in layers:
            return layers[node.id]
        raise ExpressionError(f"There is no layer called '{node.id}'")
    if isinstance(node, ast.BinOp):
        function = _BINARY_OPERATORS[type(node.op)]
        return function(_evaluate(node.left, layers), _evaluate(node.right, layers))
    if isinstance(node, ast.UnaryOp):
        function = _UNARY_OPERATORS[type(node.op)]
        return function(_evaluate(node.operand, layers))
    if isinstance(node, ast.Call):
        function = _FUNCTIONS[node.func.id]
        return function(*[_evaluate(argument, layers) for argument in node.args])
    raise ExpressionError("Only arithmetic on the layer names is allowed")
