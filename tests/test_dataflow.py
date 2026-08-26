import importlib
import importlib.util

from wad_deobf.semantic_ir import (
    Assign,
    Branch,
    Call,
    CallExpr,
    Index,
    Jump,
    Literal,
    MultiAssign,
    Name,
    Opaque,
    Return,
    SemanticBlock,
    SemanticProgram,
)


def _propagate(program: SemanticProgram) -> SemanticProgram:
    assert importlib.util.find_spec("wad_deobf.dataflow") is not None
    module = importlib.import_module("wad_deobf.dataflow")
    return module.propagate_straight_line_facts(program)


def test_dataflow_propagates_literal_across_unique_jump():
    program = SemanticProgram(
        10,
        (
            SemanticBlock(10, (Assign(10, Name("value"), Literal(7)), Jump(10, 20))),
            SemanticBlock(20, (Return(20, (Name("value"),)),)),
        ),
    )

    propagated = _propagate(program)

    assert propagated.block_for_state(20).instructions == (Return(20, (Literal(7),)),)


def test_dataflow_propagates_copy_chain_across_multiple_states():
    program = SemanticProgram(
        11,
        (
            SemanticBlock(11, (Assign(11, Name("source"), Literal("ok")), Jump(11, 29))),
            SemanticBlock(29, (Assign(29, Name("copy"), Name("source")), Jump(29, 47))),
            SemanticBlock(47, (Return(47, (Name("copy"),)),)),
        ),
    )

    propagated = _propagate(program)

    assert propagated.block_for_state(47).instructions == (Return(47, (Literal("ok"),)),)


def test_dataflow_refuses_to_cross_merge_points():
    program = SemanticProgram(
        1,
        (
            SemanticBlock(1, (Branch(1, Name("ok"), 2, 3),)),
            SemanticBlock(2, (Assign(2, Name("result"), Literal(1)), Jump(2, 4))),
            SemanticBlock(3, (Assign(3, Name("result"), Literal(2)), Jump(3, 4))),
            SemanticBlock(4, (Return(4, (Name("result"),)),)),
        ),
    )

    propagated = _propagate(program)

    assert propagated.block_for_state(4).instructions == (Return(4, (Name("result"),)),)


def test_dataflow_call_is_a_fact_barrier():
    program = SemanticProgram(
        5,
        (
            SemanticBlock(
                5,
                (
                    Assign(5, Name("cached"), Literal(9)),
                    Call(5, CallExpr(Name("touch"), ())),
                    Jump(5, 8),
                ),
            ),
            SemanticBlock(8, (Return(8, (Name("cached"),)),)),
        ),
    )

    propagated = _propagate(program)

    assert propagated.block_for_state(8).instructions == (Return(8, (Name("cached"),)),)


def test_dataflow_multiple_assignment_is_a_fact_barrier():
    program = SemanticProgram(
        13,
        (
            SemanticBlock(
                13,
                (
                    Assign(13, Name("left"), Literal(1)),
                    MultiAssign(13, (Name("left"), Name("right")), (CallExpr(Name("pair"), ()),)),
                    Jump(13, 22),
                ),
            ),
            SemanticBlock(22, (Return(22, (Name("left"), Name("right"))),)),
        ),
    )

    propagated = _propagate(program)

    assert propagated.block_for_state(22).instructions == (
        Return(22, (Name("left"), Name("right"))),
    )


def test_dataflow_index_write_and_opaque_are_fact_barriers():
    index_write = SemanticProgram(
        3,
        (
            SemanticBlock(
                3,
                (
                    Assign(3, Name("saved"), Literal(4)),
                    Assign(3, Index(Name("slots"), Literal(1)), Literal(8)),
                    Jump(3, 6),
                ),
            ),
            SemanticBlock(6, (Return(6, (Name("saved"),)),)),
        ),
    )
    opaque = SemanticProgram(
        30,
        (
            SemanticBlock(
                30,
                (Assign(30, Name("saved"), Literal(4)), Opaque(30, "mystery()"), Jump(30, 60)),
            ),
            SemanticBlock(60, (Return(60, (Name("saved"),)),)),
        ),
    )

    propagated_index = _propagate(index_write)
    propagated_opaque = _propagate(opaque)

    assert propagated_index.block_for_state(6).instructions == (Return(6, (Name("saved"),)),)
    assert propagated_opaque.block_for_state(60).instructions == (Return(60, (Name("saved"),)),)
