from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .emit import emit_luau
from .normalize import normalize_wad
from .recover import recover_luau
from .vm import extract_dispatcher, infer_entry_state
from .vm_emit import emit_state_machine


def _render_bytes(value: bytes) -> str:
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError:
        return "".join(chr(byte) if 32 <= byte <= 126 else f"\\x{byte:02x}" for byte in value)
    if all(char.isprintable() or char in "\t\r\n" for char in text):
        return text
    return "".join(chr(byte) if 32 <= byte <= 126 else f"\\x{byte:02x}" for byte in value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wad-deobf", description="Static WeAreDevs WAD Lua/Luau deobfuscator")
    parser.add_argument("input", type=Path, help="WAD-obfuscated Lua/Luau file")
    parser.add_argument("-o", "--output", type=Path, help="write output to a file")
    parser.add_argument("--strings", action="store_true", help="print the decoded WAD string table")
    parser.add_argument("--normalized", action="store_true", help="emit normalized WAD source without payload recovery")
    parser.add_argument("--vm-ir", action="store_true", help="emit the de-flattened WAD VM state machine")
    parser.add_argument("--entry", type=int, help="override the WAD VM entry state")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        source = args.input.read_text(encoding="utf-8")
        normalized = normalize_wad(source)
        if args.strings:
            output = "".join(f"[{index}] {_render_bytes(value)}\n" for index, value in enumerate(normalized.decoded_strings, 1))
        elif args.normalized:
            output = normalized.source.rstrip() + "\n"
        elif args.vm_ir:
            program = extract_dispatcher(normalized.source)
            entry = args.entry if args.entry is not None else infer_entry_state(normalized.source, program)
            output = emit_state_machine(program, entry_state=entry)
        else:
            output = emit_luau(recover_luau(normalized, entry_state=args.entry))
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"wad-deobf: {exc}", file=sys.stderr)
        return 2

    if args.output:
        try:
            args.output.write_text(output, encoding="utf-8")
        except OSError as exc:
            print(f"wad-deobf: {exc}", file=sys.stderr)
            return 2
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
