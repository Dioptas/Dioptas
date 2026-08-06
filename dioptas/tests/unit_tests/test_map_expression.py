# SPDX-License-Identifier: MIT

import numpy as np
import pytest

from dioptas.model import map_expression


LAYERS = {
    "A": np.array([10.0, 20.0, 30.0]),
    "B": np.array([1.0, 2.0, 5.0]),
}


def test_ratio_of_two_layers():
    result = map_expression.evaluate("A/B", LAYERS)
    np.testing.assert_allclose(result, [10.0, 10.0, 6.0])


def test_contrast_expression():
    result = map_expression.evaluate("(A-B)/(A+B)", LAYERS)
    np.testing.assert_allclose(result, [9 / 11, 18 / 22, 25 / 35])


def test_numbers_and_functions():
    np.testing.assert_allclose(
        map_expression.evaluate("2*A - 5", LAYERS), [15.0, 35.0, 55.0]
    )
    np.testing.assert_allclose(
        map_expression.evaluate("sqrt(B)", LAYERS), np.sqrt(LAYERS["B"])
    )


def test_division_by_zero_gives_blank_points_not_a_failure():
    layers = {"A": np.array([1.0, 2.0]), "B": np.array([0.0, 2.0])}
    result = map_expression.evaluate("A/B", layers)
    assert np.isnan(result[0])
    assert result[1] == pytest.approx(1.0)


def test_constant_expression_covers_every_point():
    result = map_expression.evaluate("1", LAYERS)
    np.testing.assert_allclose(result, [1.0, 1.0, 1.0])


def test_unknown_layer_is_rejected():
    assert map_expression.evaluate("A/Z", LAYERS) is None
    assert "no layer called 'Z'" in map_expression.validate("A/Z", {"A"})


def test_layer_without_values_is_treated_as_unknown():
    assert map_expression.evaluate("A/B", {"A": LAYERS["A"], "B": None}) is None


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('echo hi')",
        "open('/etc/passwd').read()",
        "A.__class__",
        "[x for x in range(3)]",
        "lambda: 1",
        "A if A else B",
        "'a string'",
    ],
)
def test_only_arithmetic_is_allowed(expression):
    assert map_expression.evaluate(expression, LAYERS) is None
    assert map_expression.validate(expression, set(LAYERS)) is not None


def test_syntax_error_is_reported_not_raised():
    assert map_expression.evaluate("A/", LAYERS) is None
    assert map_expression.validate("A/", set(LAYERS)) is not None


def test_referenced_names_ignores_functions():
    assert map_expression.referenced_names("sqrt(A)/B") == {"A", "B"}


def test_rename_only_touches_whole_names():
    assert map_expression.rename("A/AB", "A", "C") == "C / AB"
    assert map_expression.rename("A/B", "Z", "C") == "A/B"
