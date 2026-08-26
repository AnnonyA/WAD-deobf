# WAD-deobf

Static deobfuscator for Lua/Luau produced by the WeAreDevs WAD obfuscator.

The current release targets the WAD v1.0.0 layout observed in public and local samples. It never executes the obfuscated payload.

## What it does

- detects WAD wrappers structurally
- folds WAD integer arithmetic noise safely
- rebuilds the shuffled string table
- derives the per-file 64-character decoder alphabet
- decodes text and binary string entries
- resolves constant WAD string-table lookups
- extracts literal `load` / `loadstring` payloads when they are statically present
- emits normalized Lua/Luau when deeper VM recovery cannot be proven

WAD can discard comments, formatting, and original local variable names. Those cannot be recovered exactly if they are no longer present in the obfuscated data.

## Install

```bash
python -m pip install .
```

Python 3.11 or newer is required. Runtime dependencies: none.

## Usage

```bash
wad-deobf input.lua
wad-deobf input.lua -o output.lua
wad-deobf input.lua --strings
wad-deobf input.lua --normalized
```

Default output attempts static payload recovery first. If the VM cannot be reconstructed safely, the output is marked as partial and contains the normalized WAD source instead of fabricated code.

## Safety model

The tool parses text only. It does not call Lua, `load`, `loadstring`, Roblox APIs, executor APIs, or the obfuscated program.

## Development

```bash
python -m pytest -q
```

## License

MIT
