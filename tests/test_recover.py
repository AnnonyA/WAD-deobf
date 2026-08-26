from wad_deobf import emit
from wad_deobf.normalize import NormalizedWad
from wad_deobf import recover


def normalized(source: str) -> NormalizedWad:
    return NormalizedWad(
        version="1.0.0",
        decoded_strings=(b"print",),
        lookup_name="n",
        lookup_offset=10,
        source=source,
    )


def test_recover_luau_extracts_static_loadstring_payload():
    result = recover.recover_luau(normalized('local f=loadstring("print(\\\"ok\\\")")'))
    assert result.mode == "source"
    assert result.source == 'print("ok")'
    assert result.reason is None


def test_recover_luau_extracts_static_load_payload():
    result = recover.recover_luau(normalized("return load('return 42')()"))
    assert result.mode == "source"
    assert result.source == "return 42"


def test_recover_luau_falls_back_without_fabricating_vm_source():
    source = "return(function() local state=123 end)()"
    result = recover.recover_luau(normalized(source))
    assert result.mode == "normalized"
    assert result.source == source
    assert "VM" in result.reason


def test_emit_luau_marks_partial_output_but_not_recovered_source():
    exact = recover.recover_luau(normalized("return load('print(1)')()"))
    partial = recover.recover_luau(normalized("return(function()end)()"))
    assert emit.emit_luau(exact) == "print(1)\n"
    rendered = emit.emit_luau(partial)
    assert rendered.startswith("-- WAD deobfuscation: partial static recovery\n")
    assert "return(function()end)()" in rendered
