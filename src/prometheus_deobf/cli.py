from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .pipeline import deobfuscate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='prometheus-deobf', description='Static deobfuscator for Prometheus Lua/Luau output')
    parser.add_argument('input', type=Path)
    parser.add_argument('-o', '--output', type=Path)
    parser.add_argument('--report', type=Path, help='write a JSON transformation report')
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        source = args.input.read_text(encoding='utf-8')
    except OSError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    result = deobfuscate(source)
    if args.output:
        args.output.write_text(result.source, encoding='utf-8')
    else:
        sys.stdout.write(result.source)
    if args.report:
        args.report.write_text(json.dumps({
            'total_changes': result.total_changes,
            'vm': result.vm,
            'passes': result.report,
        }, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
