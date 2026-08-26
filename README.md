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
- emits a simpler state machine instead of the original binary-search control-flow tree

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
wad-deobf input.lua --vm-ir --entry 123456
```

Default output tries static source recovery first. If that cannot be proven, it tries to de-flatten the VM dispatcher. If neither step is safe, it falls back to normalized WAD source instead of fabricating code.

`--entry` is useful when the VM entry state is known but cannot be inferred automatically. When an entry is available, unreachable states are omitted from the emitted state machine.

## Current limit

v0.2.0 removes a large part of WAD's wrapper and control-flow noise, but it is not yet a complete bytecode decompiler for every WAD program. Deep VM instruction lifting still depends on recognizing more serializer/opcode patterns across additional samples.

## Safety model

The tool does not call Lua, `load`, `loadstring`, Roblox APIs, executor APIs, or the obfuscated program. All recovery is static.

## Development

```bash
python -m pytest -q
```

## License

MIT
