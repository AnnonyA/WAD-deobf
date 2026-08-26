from wad_deobf.semantic_ir import (
    Branch,
    Call,
    CallExpr,
    Jump,
    Name,
    Opaque,
    Return,
    SemanticBlock,
    SemanticProgram,
)
from wad_deobf.structure import (
    BlockRegion,
    IfRegion,
    ReturnRegion,
    SequenceRegion,
    StateMachineRegion,
    WhileRegion,
    structure_program,
)


def test_structure_recovers_straight_line_sequence():
    program = SemanticProgram(
        1,
        (
            SemanticBlock(1, (Call(1, CallExpr(Name("a"), ())), Jump(1, 2))),
            SemanticBlock(2, (Call(2, CallExpr(Name("b"), ())), Jump(2, 3))),
            SemanticBlock(3, (Return(3, ()),)),
        ),
    )

    assert structure_program(program) == SequenceRegion(
        (BlockRegion(1), BlockRegion(2), ReturnRegion(3))
    )


def test_structure_recovers_simple_if_else_diamond():
    program = SemanticProgram(
        1,
        (
            SemanticBlock(1, (Branch(1, Name("ok"), 2, 3),)),
            SemanticBlock(2, (Call(2, CallExpr(Name("yes"), ())), Jump(2, 4))),
            SemanticBlock(3, (Call(3, CallExpr(Name("no"), ())), Jump(3, 4))),
            SemanticBlock(4, (Return(4, ()),)),
        ),
    )

    assert structure_program(program) == SequenceRegion(
        (
            IfRegion(1, Name("ok"), BlockRegion(2), BlockRegion(3), 4),
            ReturnRegion(4),
        )
    )


def test_structure_recovers_simple_while_back_edge():
    program = SemanticProgram(
        1,
        (
            SemanticBlock(1, (Branch(1, Name("running"), 2, 3),)),
            SemanticBlock(2, (Call(2, CallExpr(Name("tick"), ())), Jump(2, 1))),
            SemanticBlock(3, (Return(3, ()),)),
        ),
    )

    assert structure_program(program) == SequenceRegion(
        (
            WhileRegion(1, Name("running"), BlockRegion(2), 3),
            ReturnRegion(3),
        )
    )


def test_structure_refuses_loop_when_head_has_effects_before_branch():
    program = SemanticProgram(
        1,
        (
            SemanticBlock(
                1,
                (Call(1, CallExpr(Name("probe"), ())), Branch(1, Name("running"), 2, 3)),
            ),
            SemanticBlock(2, (Call(2, CallExpr(Name("tick"), ())), Jump(2, 1))),
            SemanticBlock(3, (Return(3, ()),)),
        ),
    )

    assert structure_program(program) == StateMachineRegion((1, 2, 3))


def test_structure_refuses_loop_when_branch_targets_same_body():
    program = SemanticProgram(
        1,
        (
            SemanticBlock(1, (Branch(1, Name("running"), 2, 2),)),
            SemanticBlock(2, (Call(2, CallExpr(Name("tick"), ())), Jump(2, 1))),
        ),
    )

    assert structure_program(program) == StateMachineRegion((1, 2))


def test_structure_falls_back_for_opaque_or_unresolved_control_flow():
    opaque = SemanticProgram(
        1,
        (
            SemanticBlock(1, (Opaque(1, "mystery()"), Jump(1, 2))),
            SemanticBlock(2, (Return(2, ()),)),
        ),
    )
    unresolved = SemanticProgram(1, (SemanticBlock(1, (Jump(1, 99),)),), (99,))

    assert structure_program(opaque) == StateMachineRegion((1, 2))
    assert structure_program(unresolved) == StateMachineRegion((1,))


def test_structure_without_entry_falls_back():
    program = SemanticProgram(None, (SemanticBlock(1, (Return(1, ()),)),))
    assert structure_program(program) == StateMachineRegion((1,))
