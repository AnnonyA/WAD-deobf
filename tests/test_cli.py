import base64
import subprocess
import sys
from pathlib import Path

from wad_deobf.cli import build_parser


ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def _literal(value: str) -> str:
    return '"' + "".join(f"\\{ord(char):03d}" for char in value) + '"'


def _alphabet() -> str:
    entries = []
    for index, char in enumerate(ALPHABET):
        key = char if char.isalpha() else f'["\\{ord(char):03d}"]'
        entries.append(f"{key}={index}")
    return ";".join(entries)


def _wad(payload: bytes = b"print(1)") -> str:
    encoded = base64.b64encode(payload).decode("ascii")
    return (
        "--[[ v1.0.0 https://wearedevs.net/obfuscator ]] "
        f"return(function(...)local e={{{_literal(encoded)}}}"
        "for n,Y in ipairs({{1,1}})do while Y[1]<Y[2]do "
        "e[Y[1]],e[Y[2]],Y[1],Y[2]=e[Y[2]],e[Y[1]],Y[1]+1,Y[2]-1 end end "
        "local function n(n)return e[n+(0)]end "
        f"do local n={{{_alphabet()}}}local Y=string.sub local K=string.char end "
        "local payload=n(1) return loadstring(payload)() end)(...)"
    )


def _wad_vm() -> str:
    encoded = base64.b64encode(b"unused").decode("ascii")
    return (
        "--[[ v1.0.0 https://wearedevs.net/obfuscator ]] "
        f"return(function(...)local e={{{_literal(encoded)}}}"
        "for n,Y in ipairs({{1,1}})do while Y[1]<Y[2]do "
        "e[Y[1]],e[Y[2]],Y[1],Y[2]=e[Y[2]],e[Y[1]],Y[1]+1,Y[2]-1 end end "
        "local function n(n)return e[n+(0)]end "
        f"do local n={{{_alphabet()}}}local Y=string.sub local K=string.char end "
        "local function run(s) while s do if s<10 then print(\"tick\");s=20 else return end end end "
        "return run(5) end)(...)"
    )


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "wad_deobf.cli", *args],
        text=True,
        capture_output=True,
        env={"PYTHONPATH": "src"},
        check=False,
    )


def test_cli_recovers_static_payload_to_stdout(tmp_path: Path):
    input_path = tmp_path / "input.lua"
    input_path.write_text(_wad(), encoding="utf-8")
    result = _run(str(input_path))
    assert result.returncode == 0
    assert result.stdout == "print(1)\n"
    assert result.stderr == ""


def test_cli_writes_recovered_output_file(tmp_path: Path):
    input_path = tmp_path / "input.lua"
    output_path = tmp_path / "out.lua"
    input_path.write_text(_wad(), encoding="utf-8")
    result = _run(str(input_path), "-o", str(output_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert output_path.read_text(encoding="utf-8") == "print(1)\n"


def test_cli_strings_mode_lists_decoded_bytes(tmp_path: Path):
    input_path = tmp_path / "input.lua"
    input_path.write_text(_wad(b"hello"), encoding="utf-8")
    result = _run(str(input_path), "--strings")
    assert result.returncode == 0
    assert "[1] hello" in result.stdout


def test_cli_accepts_vm_ir_semantic_ir_diagnostics_and_entry_flags():
    args = build_parser().parse_args(["input.lua", "--ir", "--entry", "123"])
    assert args.ir is True
    assert args.entry == 123
    args = build_parser().parse_args(["input.lua", "--diagnostics"])
    assert args.diagnostics is True


def test_cli_emits_semantic_ir(tmp_path: Path):
    input_path = tmp_path / "vm.lua"
    input_path.write_text(_wad_vm(), encoding="utf-8")
    result = _run(str(input_path), "--ir")
    assert result.returncode == 0
    assert "entry: 5" in result.stdout
    assert "state 5:" in result.stdout
    assert 'call print("tick")' in result.stdout
    assert "jump 20" in result.stdout


def test_cli_emits_semantic_diagnostics(tmp_path: Path):
    input_path = tmp_path / "vm.lua"
    input_path.write_text(_wad_vm(), encoding="utf-8")
    result = _run(str(input_path), "--diagnostics")
    assert result.returncode == 0
    assert "states: 2" in result.stdout
    assert "structured: yes" in result.stdout
    assert "opaque states: none" in result.stdout


def test_cli_rejects_non_wad_input(tmp_path: Path):
    input_path = tmp_path / "plain.lua"
    input_path.write_text("print('hello')", encoding="utf-8")
    result = _run(str(input_path))
    assert result.returncode == 2
    assert result.stdout == ""
    assert "WAD" in result.stderr
