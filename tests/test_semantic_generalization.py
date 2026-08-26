from wad_deobf.ir import VmBlock, VmProgram
from wad_deobf.lifter import lift_program
from wad_deobf.semantic_opt import optimize_program
from wad_deobf.structure import structure_program
from wad_deobf.structured_emit import emit_structured


def _emit(program: VmProgram, entry: int) -> tuple[str, bool]:
    semantic = optimize_program(lift_program(program, entry))
    return emit_structured(semantic, structure_program(semantic))


def test_semantic_lifter_generalizes_across_state_names_and_values():
    program = VmProgram(
        "pc",
        (
            VmBlock(None, 200, "value=41\npc=257", (257,)),
            VmBlock(200, 300, "print(value)\npc=411", (411,)),
            VmBlock(300, None, "return value", ()),
        ),
    )

    source, complete = _emit(program, 137)

    assert complete is True
    assert source == "local v1\nv1 = 41\nprint(v1)\nreturn v1\n"
    assert "pc" not in source
    assert "137" not in source
    assert "257" not in source
    assert "411" not in source


def test_semantic_lifter_generalizes_diamond_with_different_partition_values():
    program = VmProgram(
        "cursor",
        (
            VmBlock(None, 500, "cursor=flag and 701 or 809", (701, 809)),
            VmBlock(500, 750, "result='left'\ncursor=997", (997,)),
            VmBlock(750, 900, "result='right'\ncursor=997", (997,)),
            VmBlock(900, None, "return result", ()),
        ),
    )

    source, complete = _emit(program, 123)

    assert complete is True
    assert source == (
        "local v1\n"
        "if flag then\n"
        "    v1 = \"left\"\n"
        "else\n"
        "    v1 = \"right\"\n"
        "end\n"
        "return v1\n"
    )
    assert "cursor" not in source
    assert "701" not in source
    assert "809" not in source
    assert "997" not in source
