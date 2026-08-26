from wad_deobf.dataflow import propagate_straight_line_facts
from wad_deobf.semantic_ir import (
    Assign,
    BinaryExpr,
    Call,
    CallExpr,
    Jump,
    Literal,
    Name,
    Return,
    SemanticBlock,
    SemanticProgram,
    TableExpr,
)
from wad_deobf.semantic_opt import optimize_program
from wad_deobf.structure import structure_program
from wad_deobf.structured_emit import emit_structured


def test_optimizer_substitutes_names_inside_binary_expressions():
    program = SemanticProgram(
        1,
        (
            SemanticBlock(
                1,
                (
                    Assign(1, Name("x"), Literal(1)),
                    Assign(1, Name("y"), BinaryExpr(Name("x"), "+", Literal(2))),
                    Return(1, (Name("y"),)),
                ),
            ),
        ),
    )

    optimized = optimize_program(program)

    assert optimized.block_for_state(1).instructions == (
        Assign(1, Name("y"), BinaryExpr(Literal(1), "+", Literal(2))),
        Return(1, (Name("y"),)),
    )


def test_dataflow_finds_nested_calls_inside_rich_expressions():
    program = SemanticProgram(
        5,
        (
            SemanticBlock(
                5,
                (
                    Assign(5, Name("cached"), Literal(9)),
                    Assign(
                        5,
                        Name("result"),
                        BinaryExpr(CallExpr(Name("mutate"), ()), "+", Literal(1)),
                    ),
                    Jump(5, 8),
                ),
            ),
            SemanticBlock(8, (Return(8, (Name("cached"),)),)),
        ),
    )

    propagated = propagate_straight_line_facts(program)

    assert propagated.block_for_state(8).instructions == (Return(8, (Name("cached"),)),)


def test_emitter_renames_names_inside_tables_and_binary_expressions():
    program = SemanticProgram(
        1,
        (
            SemanticBlock(
                1,
                (
                    Assign(1, Name("x"), Literal(1)),
                    Call(
                        1,
                        CallExpr(
                            Name("consume"),
                            (TableExpr((Name("x"), BinaryExpr(Name("x"), "+", Literal(2)))),),
                        ),
                    ),
                    Return(1, (Name("x"),)),
                ),
            ),
        ),
    )

    source, complete = emit_structured(program, structure_program(program))

    assert complete is True
    assert source == (
        "local v1\n"
        "v1 = 1\n"
        "consume({v1, (v1 + 2)})\n"
        "return v1\n"
    )
