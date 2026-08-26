from wad_deobf.lua_expr import emit_expr, parse_expr
from wad_deobf.semantic_ir import (
    Assign,
    Attribute,
    BinaryExpr,
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
    TableExpr,
    Vararg,
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


def test_parse_expr_recovers_binary_precedence():
    assert parse_expr("p^a") == BinaryExpr(Name("p"), "^", Name("a"))
    assert parse_expr("f+K") == BinaryExpr(Name("f"), "+", Name("K"))
    assert parse_expr("u%Q") == BinaryExpr(Name("u"), "%", Name("Q"))
    assert parse_expr("g==t") == BinaryExpr(Name("g"), "==", Name("t"))
    assert parse_expr("O<S") == BinaryExpr(Name("O"), "<", Name("S"))
    assert parse_expr("a+b*c") == BinaryExpr(
        Name("a"),
        "+",
        BinaryExpr(Name("b"), "*", Name("c")),
    )
    assert parse_expr("a^b^c") == BinaryExpr(
        Name("a"),
        "^",
        BinaryExpr(Name("b"), "^", Name("c")),
    )


def test_parse_expr_recovers_positional_tables_and_varargs():
    assert parse_expr("...") == Vararg()
    assert parse_expr("{}") == TableExpr(())
    assert parse_expr("{a,b;...}") == TableExpr((Name("a"), Name("b"), Vararg()))
    assert parse_expr("G(l,{i},y,x)") == CallExpr(
        Name("G"),
        (Name("l"), TableExpr((Name("i"),)), Name("y"), Name("x")),
    )


def test_parse_expr_falls_back_without_guessing():
    expr = parse_expr('function() return 1 end')
    assert expr == RawExpr('function() return 1 end')
    assert emit_expr(expr) == 'function() return 1 end'
    assert parse_expr("{key=value}") == RawExpr("{key=value}")


def test_emit_expr_is_deterministic():
    expr = CallExpr(Attribute(Name("table"), "concat"), (Name("parts"), Literal("")))
    assert emit_expr(expr) == 'table.concat(parts, "")'
    assert emit_expr(BinaryExpr(Name("a"), "+", BinaryExpr(Name("b"), "*", Name("c")))) == "(a + (b * c))"
    assert emit_expr(TableExpr((Name("a"), Vararg()))) == "{a, ...}"


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
