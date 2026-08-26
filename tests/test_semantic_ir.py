from wad_deobf.lua_expr import emit_expr, parse_expr
from wad_deobf.semantic_ir import Attribute, CallExpr, Concat, Index, Literal, Name, RawExpr


def test_parse_expr_recovers_semantic_shapes():
    assert parse_expr('42') == Literal(42)
    assert parse_expr('"hello"') == Literal("hello")
    assert parse_expr('math.random') == Attribute(Name("math"), "random")
    assert parse_expr('regs[key]') == Index(Name("regs"), Name("key"))
    assert parse_expr('a .. "x" .. b') == Concat((Name("a"), Literal("x"), Name("b")))
    assert parse_expr('math.random(1, 100)') == CallExpr(
        Attribute(Name("math"), "random"),
        (Literal(1), Literal(100)),
    )


def test_parse_expr_falls_back_without_guessing():
    expr = parse_expr('a + unknown(x)')
    assert expr == RawExpr('a + unknown(x)')
    assert emit_expr(expr) == 'a + unknown(x)'


def test_emit_expr_is_deterministic():
    expr = CallExpr(Attribute(Name("table"), "concat"), (Name("parts"), Literal("")))
    assert emit_expr(expr) == 'table.concat(parts, "")'
