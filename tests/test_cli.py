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


def test_cli_accepts_vm_ir_and_entry_flags():
    args = build_parser().parse_args(["input.lua", "--vm-ir", "--entry", "123"])
    assert args.vm_ir is True
    assert args.entry == 123


def test_cli_rejects_non_wad_input(tmp_path: Path):
    input_path = tmp_path / "plain.lua"
    input_path.write_text("print('hello')", encoding="utf-8")
    result = _run(str(input_path))
    assert result.returncode == 2
    assert result.stdout == ""
    assert "WAD" in result.stderr
