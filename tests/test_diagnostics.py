from wad_deobf.diagnostics import analyze_semantic_program, render_diagnostics, render_semantic_ir
from wad_deobf.emit import emit_luau
from wad_deobf.normalize import NormalizedWad
from wad_deobf.recover import recover_luau
from wad_deobf.semantic_ir import (
    CallExpr,
    Jump,
    MultiAssign,
    Name,
    Opaque,
    Return,
    SemanticBlock,
    SemanticProgram,
)
from wad_deobf.structure import structure_program


def normalized(source: str) -> NormalizedWad:
    return NormalizedWad(
        version="1.0.0",
        decoded_strings=(),
        lookup_name="n",
        lookup_offset=0,
        source=source,
    )


def test_recovery_prefers_structured_semantic_output_when_proven():
    source = "local function run(s) while s do if s<10 then print(1);s=20 else return end end end return run(5)"
    result = recover_luau(normalized(source))

    assert result.mode == "structured"
    assert result.source == "print(1)\nreturn\n"
    assert emit_luau(result).startswith("-- WAD deobfuscation: structured static recovery\n")


def test_recovery_marks_opaque_semantic_output_partial():
    source = "local function run(s) while s do if s<10 then mystery + 1;s=20 else return end end end return run(5)"
    result = recover_luau(normalized(source))

    assert result.mode == "structured-partial"
    assert "local state = 5" in result.source
    assert "mystery + 1" in result.source
    assert "partial semantic recovery" in emit_luau(result)


def test_diagnostics_explains_opaque_and_unresolved_states():
    program = SemanticProgram(
        1,
        (
            SemanticBlock(1, (Opaque(1, "mystery()"), Jump(1, 2))),
            SemanticBlock(2, (Return(2, ()),)),
        ),
        (99,),
    )
    report = analyze_semantic_program(program, structure_program(program))
    text = render_diagnostics(report)

    assert report.state_count == 2
    assert report.opaque_states == (1,)
    assert report.unresolved_targets == (99,)
    assert report.structured is False
    assert "opaque states: 1" in text
    assert "unresolved targets: 99" in text


def test_semantic_ir_renders_multiple_assignment_without_losing_results():
    program = SemanticProgram(
        17,
        (
            SemanticBlock(
                17,
                (
                    MultiAssign(
                        17,
                        (Name("left"), Name("right")),
                        (CallExpr(Name("pair"), ()),),
                    ),
                    Return(17, (Name("left"), Name("right"))),
                ),
            ),
        ),
    )

    text = render_semantic_ir(program)

    assert "multi-assign left, right = pair()" in text
    assert "return left, right" in text
