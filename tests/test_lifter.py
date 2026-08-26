from wad_deobf.ir import VmBlock, VmProgram
from wad_deobf.lifter import lift_program
from wad_deobf.semantic_ir import (
    Assign,
    Attribute,
    Branch,
    Call,
    CallExpr,
    Index,
    Jump,
    Literal,
    Name,
    Opaque,
    Return,
)


def test_lifter_recovers_straight_line_effects_and_return():
    program = VmProgram(
        state_var="s",
        blocks=(
            VmBlock(None, 10, "x=1; y=x; z=math.random(1, 100); print(z); s=20", (20,)),
            VmBlock(10, None, "return z", (), terminal=True),
        ),
    )

    lifted = lift_program(program, entry_state=5)

    assert lifted.entry_state == 5
    assert lifted.block_for_state(5).instructions == (
        Assign(5, Name("x"), Literal(1)),
        Assign(5, Name("y"), Name("x")),
        Assign(
            5,
            Name("z"),
            CallExpr(Attribute(Name("math"), "random"), (Literal(1), Literal(100))),
        ),
        Call(5, CallExpr(Name("print"), (Name("z"),))),
        Jump(5, 20),
    )
    assert lifted.block_for_state(20).instructions == (Return(20, (Name("z"),)),)


def test_lifter_recovers_index_access_and_preserves_unknown_statement():
    program = VmProgram(
        state_var="s",
        blocks=(
            VmBlock(None, 10, "a=regs[key]; regs[key]=a; strange + 1; s=20", (20,)),
            VmBlock(10, None, "return a", (), terminal=True),
        ),
    )

    lifted = lift_program(program, entry_state=5)
    block = lifted.block_for_state(5)

    assert block.instructions[:2] == (
        Assign(5, Name("a"), Index(Name("regs"), Name("key"))),
        Assign(5, Index(Name("regs"), Name("key")), Name("a")),
    )
    assert block.instructions[2] == Opaque(5, "strange + 1")
    assert block.instructions[-1] == Jump(5, 20)


def test_lifter_recovers_lua_ternary_state_branch():
    program = VmProgram(
        state_var="s",
        blocks=(
            VmBlock(None, 10, "s=ok and 20 or 30", (20, 30)),
            VmBlock(10, 25, "return 1", (), terminal=True),
            VmBlock(25, None, "return 2", (), terminal=True),
        ),
    )

    lifted = lift_program(program, entry_state=5)

    assert lifted.block_for_state(5).instructions == (Branch(5, Name("ok"), 20, 30),)
    assert lifted.unresolved_targets == ()
