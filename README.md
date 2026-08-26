# WAD-deobf

Static deobfuscator for Lua/Luau produced by the WeAreDevs WAD obfuscator.

The current release targets the WAD v1.0.0 layout observed in public samples. It parses text only and never executes the obfuscated payload.

## What it does

- detects WAD wrappers structurally
- folds integer arithmetic noise safely
- rebuilds shuffled string tables
- derives the per-file 64-character decoder alphabet
- decodes text and binary string entries
- resolves constant string-table lookups
- preserves readable UTF-8 while keeping binary bytes lossless
- resolves safe aliases such as `local f = math.floor`
- recovers `load` / `loadstring` payloads from literal variables and simple static concatenations
- detects the flattened WAD VM dispatcher
- partitions the numeric state decision tree into VM blocks
- propagates simple Lua boolean/numeric state values
- recovers split `and` / `or` state transitions
- builds a reachable-state CFG when an entry state is known
- infers entry states from named dispatcher calls when possible
- lifts recognized VM block statements into a semantic IR
- propagates constants and copies conservatively
- removes provably dead pure temporary assignments
- reconstructs simple straight-line, `if` / `else`, and `while` regions when control flow can be proven
- emits stable temporary names such as `v1`, `v2`, and `v3`
- falls back to a simpler explicit state machine when a CFG cannot be structured safely
- reports opaque states and unresolved targets through diagnostics

WAD may discard comments, formatting, and original local variable names. Those cannot be reconstructed exactly if they are no longer present in the obfuscated data.

## Install

```bash
python -m pip install .
```

Python 3.11 or newer is required. Runtime dependencies: none.

A standalone Windows executable is attached to releases starting with v0.2.0.

## Usage

```bash
wad-deobf input.lua
wad-deobf input.lua -o output.lua
wad-deobf input.lua --strings
wad-deobf input.lua --normalized
wad-deobf input.lua --vm-ir
wad-deobf input.lua --ir
wad-deobf input.lua --diagnostics
wad-deobf input.lua --entry 123456
```

Default output tries static source recovery first. If no literal source payload is available, v0.3 lifts recognized VM blocks into semantic IR, applies conservative simplification, and reconstructs structured Luau when the CFG can be proven. If that is not safe, it keeps an explicit state-machine fallback instead of fabricating structured code. If the VM itself cannot be proven statically, normalized WAD source is returned.

`--ir` prints the optimized semantic IR by state. `--diagnostics` reports semantic coverage, opaque states, unresolved targets, and whether the CFG was structurally recovered. `--vm-ir` keeps the lower-level de-flattened state-machine view from v0.2.

`--entry` is useful when the VM entry state is known but cannot be inferred automatically. When an entry is available, unreachable states are omitted from semantic recovery and VM output.

## Current limit

v0.3.0 reconstructs recognized VM statements and simple reducible control-flow regions, but it is not a complete bytecode decompiler for every WAD program. Unknown statements, unresolved state transitions, irreducible CFGs, and serializer/opcode forms that are not proven statically remain conservative fallbacks.

## Safety model

The tool does not call Lua, `load`, `loadstring`, Roblox APIs, executor APIs, or the obfuscated program. All recovery is static.

## Development

```bash
python -m pytest -q
```

## License

MIT
