from wad_deobf.semantic_ir import (
    Assign,
    Branch,
    Call,
    CallExpr,
    Jump,
    Literal,
    Name,
    Opaque,
    Return,
    SemanticBlock,
    SemanticProgram,
)
from wad_deobf.structure import structure_program
from wad_deobf.structured_emit import emit_structured


def test_emitter_outputs_readable_straight_line_luau():
    program = SemanticProgram(
        1,
        (
            SemanticBlock(1, (Assign(1, Name("tmp"), Literal(7)), Call(1, CallExpr(Name("print"), (Name("tmp"),))), Jump(1, 2))),
            SemanticBlock(2, (Return(2, (Name("tmp"),)),)),
        ),
    )

    source, complete = emit_structured(program, structure_program(program))

    assert complete is True
    assert source == 'local v1 = 7\nprint(v1)\nreturn v1\n'
    assert "state" not in source


def test_emitter_outputs_if_else_and_while_regions():
    diamond = SemanticProgram(
        1,
        (
            SemanticBlock(1, (Branch(1, Name("ok"), 2, 3),)),
            SemanticBlock(2, (Call(2, CallExpr(Name("yes"), ())), Jump(2, 4))),
            SemanticBlock(3, (Call(3, CallExpr(Name("no"), ())), Jump(3, 4))),
            SemanticBlock(4, (Return(4, ()),)),
        ),
    )
    loop = SemanticProgram(
        1,
        (
            SemanticBlock(1, (Branch(1, Name("running"), 2, 3),)),
            SemanticBlock(2, (Call(2, CallExpr(Name("tick"), ())), Jump(2, 1))),
            SemanticBlock(3, (Return(3, ()),)),
        ),
    )

    diamond_source, diamond_complete = emit_structured(diamond, structure_program(diamond))
    loop_source, loop_complete = emit_structured(loop, structure_program(loop))

    assert diamond_complete is True
    assert diamond_source == 'if ok then\n    yes()\nelse\n    no()\nend\nreturn\n'
    assert loop_complete is True
    assert loop_source == 'while running do\n    tick()\nend\nreturn\n'


def test_emitter_marks_state_machine_fallback_partial():
    program = SemanticProgram(
        1,
        (
            SemanticBlock(1, (Opaque(1, "mystery()"), Jump(1, 2))),
            SemanticBlock(2, (Return(2, ()),)),
        ),
    )

    source, complete = emit_structured(program, structure_program(program))

    assert complete is False
    assert "local state = 1" in source
    assert "mystery()" in source
    assert "state = 2" in source
