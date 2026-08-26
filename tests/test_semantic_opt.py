from wad_deobf.semantic_ir import (
    Assign,
    Attribute,
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
from wad_deobf.semantic_opt import optimize_program, stable_names


def test_optimizer_propagates_constants_and_removes_dead_pure_temporaries():
    program = SemanticProgram(
        5,
        (
            SemanticBlock(
                5,
                (
                    Assign(5, Name("x"), Literal(1)),
                    Assign(5, Name("y"), Name("x")),
                    Call(5, CallExpr(Name("print"), (Name("y"),))),
                    Jump(5, 20),
                ),
            ),
            SemanticBlock(20, (Return(20, ()),)),
        ),
    )

    optimized = optimize_program(program)

    assert optimized.block_for_state(5).instructions == (
        Call(5, CallExpr(Name("print"), (Literal(1),))),
        Jump(5, 20),
    )


def test_optimizer_reduces_constant_branch_to_jump():
    program = SemanticProgram(5, (SemanticBlock(5, (Branch(5, Literal(False), 10, 20),)),))
    optimized = optimize_program(program)
    assert optimized.block_for_state(5).instructions == (Jump(5, 20),)


def test_optimizer_preserves_effectful_and_opaque_operations():
    random_call = CallExpr(Attribute(Name("math"), "random"), ())
    program = SemanticProgram(
        5,
        (
            SemanticBlock(
                5,
                (
                    Assign(5, Name("x"), random_call),
                    Opaque(5, "unknown_side_effect()"),
                    Return(5, (Name("x"),)),
                ),
            ),
        ),
    )

    optimized = optimize_program(program)
    assert optimized.block_for_state(5).instructions[0] == Assign(5, Name("x"), random_call)
    assert any(isinstance(item, Opaque) for item in optimized.block_for_state(5).instructions)


def test_optimizer_never_substitutes_a_name_assignment_target():
    program = SemanticProgram(
        1,
        (
            SemanticBlock(
                1,
                (
                    Assign(1, Name("x"), Literal(1)),
                    Assign(1, Name("x"), Literal(2)),
                    Return(1, (Name("x"),)),
                ),
            ),
        ),
    )

    optimized = optimize_program(program)

    assert optimized.block_for_state(1).instructions == (Return(1, (Literal(2),)),)


def test_optimizer_invalidates_copies_when_the_source_is_reassigned():
    program = SemanticProgram(
        1,
        (
            SemanticBlock(
                1,
                (
                    Assign(1, Name("saved"), Name("source")),
                    Assign(1, Name("source"), Literal(2)),
                    Return(1, (Name("saved"),)),
                ),
            ),
        ),
    )

    optimized = optimize_program(program)

    assert optimized.block_for_state(1).instructions == (
        Assign(1, Name("saved"), Name("source")),
        Assign(1, Name("source"), Literal(2)),
        Return(1, (Name("saved"),)),
    )


def test_optimizer_invalidates_attribute_aliases_after_index_write():
    program = SemanticProgram(
        1,
        (
            SemanticBlock(
                1,
                (
                    Assign(1, Name("saved"), Attribute(Name("obj"), "field")),
                    Assign(1, Index(Name("obj"), Literal("field")), Literal(2)),
                    Return(1, (Name("saved"),)),
                ),
            ),
        ),
    )

    optimized = optimize_program(program)

    assert optimized.block_for_state(1).instructions == (
        Assign(1, Name("saved"), Attribute(Name("obj"), "field")),
        Assign(1, Index(Name("obj"), Literal("field")), Literal(2)),
        Return(1, (Name("saved"),)),
    )


def test_optimizer_invalidates_facts_across_multiple_assignment():
    program = SemanticProgram(
        1,
        (
            SemanticBlock(
                1,
                (
                    Assign(1, Name("left"), Literal(1)),
                    MultiAssign(
                        1,
                        (Name("left"), Name("right")),
                        (CallExpr(Name("pair"), ()),),
                    ),
                    Return(1, (Name("left"), Name("right"))),
                ),
            ),
        ),
    )

    optimized = optimize_program(program)
    instructions = optimized.block_for_state(1).instructions

    assert any(isinstance(item, MultiAssign) for item in instructions)
    assert instructions[-1] == Return(1, (Name("left"), Name("right")))


def test_stable_names_include_multiple_assignment_targets():
    program = SemanticProgram(
        1,
        (
            SemanticBlock(
                1,
                (
                    MultiAssign(1, (Name("alpha"), Name("beta")), (CallExpr(Name("pair"), ()),)),
                    Return(1, (Name("alpha"), Name("beta"))),
                ),
            ),
        ),
    )

    assert stable_names(program) == {"alpha": "v1", "beta": "v2"}


def test_stable_names_are_deterministic_and_ignore_globals():
    program = SemanticProgram(
        1,
        (
            SemanticBlock(
                1,
                (
                    Assign(1, Name("alpha"), Literal(1)),
                    Assign(1, Name("beta"), Name("alpha")),
                    Call(1, CallExpr(Name("print"), (Name("beta"),))),
                ),
            ),
        ),
    )
    assert stable_names(program) == {"alpha": "v1", "beta": "v2"}
    assert stable_names(program) == stable_names(program)
