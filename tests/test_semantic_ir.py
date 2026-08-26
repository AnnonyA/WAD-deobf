from wad_deobf.lua_expr import emit_expr, parse_expr
from wad_deobf.semantic_ir import (
    Assign,
    Attribute,
    Branch,
    Call,
    CallExpr,
    Concat,
    Index,
    Jump,
    Literal,
    Name,
    Opaque,
    RawExpr,
    Return,
    SemanticBlock,
    SemanticProgram,
)


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


def test_semantic_instruction_model_keeps_state_and_edges():
    assign = Assign(5, Name("x"), Literal(1))
    call = Call(5, CallExpr(Name("print"), (Name("x"),)))
    branch = Branch(5, Name("ok"), 10, 20)
    jump = Jump(10, 30)
    ret = Return(30, (Name("x"),))
    opaque = Opaque(20, "mystery()")
    block = SemanticBlock(5, (assign, call, branch))
    program = SemanticProgram(5, (block,), (99,))

    assert block.instructions == (assign, call, branch)
    assert branch.targets == (10, 20)
    assert jump.targets == (30,)
    assert ret.targets == ()
    assert opaque.source == "mystery()"
    assert program.block_for_state(5) == block
    assert program.block_for_state(6) is None
    assert program.unresolved_targets == (99,)
