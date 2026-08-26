from wad_deobf.cfg import build_state_graph
from wad_deobf.cleanup import resolve_global_aliases
from wad_deobf.emit import emit_luau
from wad_deobf.normalize import NormalizedWad
from wad_deobf.recover import RecoveryResult, recover_luau
from wad_deobf.vm import extract_dispatcher, infer_entry_state
from wad_deobf.vm_emit import emit_state_machine


def normalized(source: str) -> NormalizedWad:
    return NormalizedWad(
        version="1.0.0",
        decoded_strings=(),
        lookup_name="n",
        lookup_offset=0,
        source=source,
    )


def test_dispatcher_partitions_flattened_state_tree():
    source = """while state do
      if state < 100 then
        if state < 50 then state=75 else state=flag and 10 or 125 end
      else state=nil end
    end"""
    program = extract_dispatcher(source)
    assert [(block.lower, block.upper) for block in program.blocks] == [(None, 50), (50, 100), (100, None)]
    assert program.blocks[0].targets == (75,)
    assert program.blocks[1].targets == (10, 125)
    assert program.blocks[2].terminal is True


def test_dispatcher_ignores_nested_function_end_tokens():
    source = "while s do if s<10 then local f=function(x)return x end s=20 else s=nil end end"
    program = extract_dispatcher(source)
    assert len(program.blocks) == 2
    assert program.blocks[0].targets == (20,)


def test_dispatcher_tracks_split_lua_ternary():
    source = "while s do if s<10 then a=100 s=cond and a b=200 s=s or b else s=nil end end"
    program = extract_dispatcher(source)
    assert program.blocks[0].targets == (100, 200)


def test_dispatcher_propagates_known_boolean_transition():
    source = "while s do if s<10 then ok=true s=ok and 20 or 30 else s=nil end end"
    program = extract_dispatcher(source)
    assert program.blocks[0].targets == (20,)


def test_entry_state_is_inferred_from_named_dispatcher_call():
    source = "local function run(s) while s do if s<10 then s=20 else s=nil end end end return run(100-95)"
    program = extract_dispatcher(source)
    assert infer_entry_state(source, program) == 5


def test_cfg_prunes_unreachable_states():
    source = "while s do if s<10 then s=20 else if s<30 then s=40 else s=nil end end end"
    graph = build_state_graph(extract_dispatcher(source), 5)
    assert graph.states == (5, 20, 40)
    assert graph.unresolved_targets == ()


def test_state_machine_removes_binary_partition_tree():
    program = extract_dispatcher("while q do if q<10 then x=1 q=20 else x=2 q=nil end end")
    output = emit_state_machine(program, entry_state=5)
    assert "local state = 5" in output
    assert "if state == 5 then" in output
    assert "elseif state == 20 then" in output
    assert "if q<10" not in output


def test_safe_global_alias_calls_are_resolved():
    source = 'local f=math.floor local s="f(1)" local x=f(1)'
    output = resolve_global_aliases(source)
    assert '"f(1)"' in output
    assert "math.floor(1)" in output


def test_recover_resolves_loadstring_variable_and_concat():
    result = recover_luau(normalized('local a="print(" local b="3)" local payload=a..b return loadstring(payload)()'))
    assert result.mode == "source"
    assert result.source == "print(3)"


def test_recover_refuses_reassigned_payload_variable():
    result = recover_luau(normalized('local payload="print(1)" payload=other return loadstring(payload)()'))
    assert result.mode == "normalized"


def test_recover_de_flattens_vm_and_honors_entry_override():
    source = "local function run(s) while s do if s<10 then s=20 else s=nil end end end run(5)"
    result = recover_luau(normalized(source), entry_state=7)
    assert result.mode == "vm"
    assert "local state = 7" in result.source
    assert "if s<10" not in result.source


def test_vm_output_has_distinct_banner():
    rendered = emit_luau(RecoveryResult("vm", "while state do end", "entry state unknown"))
    assert rendered.startswith("-- WAD deobfuscation: de-flattened VM\n")
