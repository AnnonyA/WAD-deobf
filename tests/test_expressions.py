import pytest

from wad_deobf import expressions


def test_eval_int_expr_handles_wad_arithmetic():
    assert expressions.eval_int_expr("-886631+886632") == 1
    assert expressions.eval_int_expr("-649519-(-649520)") == 1
    assert expressions.eval_int_expr("(10 + 2) * 3 % 7") == 1


def test_eval_int_expr_uses_integer_exact_division():
    assert expressions.eval_int_expr("65536 / 256") == 256


def test_eval_int_expr_rejects_names_and_calls():
    with pytest.raises(ValueError):
        expressions.eval_int_expr("math.random(1, 2)")
    with pytest.raises(ValueError):
        expressions.eval_int_expr("x + 1")


def test_eval_int_expr_rejects_non_integral_division():
    with pytest.raises(ValueError):
        expressions.eval_int_expr("3 / 2")


def test_fold_int_expressions_folds_parenthesized_numeric_noise():
    source = "local a=(-886631+886632); local b=x+(-649519-(-649520))"
    assert expressions.fold_int_expressions(source) == "local a=1; local b=x+1"
