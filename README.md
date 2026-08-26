# Lua Obfuscator Deobfuscation Toolkit

## Prometheus Deobfuscator

Static Lua/Luau deobfuscation tooling for output produced by [Prometheus](https://github.com/wcrddn/Prometheus).

The tool never executes the input script. It peels transformations only when the generated structure can be recognized safely, and leaves unknown code intact instead of guessing.

## Supported recovery

| Prometheus layer | Status |
| --- | --- |
| `WrapInFunction` | Recovered |
| `NumbersToExpressions` | Recovered for constant arithmetic |
| `ConstantArray` | Custom Base64, runtime rotation, direct indexing and primary wrapper offsets |
| `EncryptStrings` | PRNG parameter extraction and static decryption when the service is exposed |
| `AntiTamper` | Conservative removal of the generated scaffold |
| `Vmify` | Dispatcher detection and linear-state lifting; runtime-dependent control flow is preserved and reported |

Prometheus can discard comments, formatting and original local names. Those cannot be reconstructed uniquely, so generated names are not presented as originals.

## Install

```bash
python -m pip install .
```

Python 3.11+ is required and the runtime has no third-party dependencies.

## Usage

```bash
prometheus-deobf input.lua -o output.lua --report report.json
```

Or directly from the source tree:

```bash
PYTHONPATH=src python -m prometheus_deobf.cli input.lua -o output.lua
```

The JSON report records every successful pass and whether a Prometheus VM dispatcher is still present.

## Samples

`samples/original.lua` is obfuscated with the pinned `wcrddn/Prometheus` fork using `samples/prometheus-config.lua`. CI regenerates the deterministic Medium-style fixture and verifies the deobfuscator against it.

## Development

```bash
python -m pytest -q
```

The test suite covers numeric folding, Lua literals, constant arrays, string encryption, generated scaffold cleanup, VM dispatcher lifting, the fixed-point pipeline and CLI behavior.

## Scope

This is a static reverse-engineering tool, not a Lua sandbox. Unknown VM patterns are intentionally preserved. Support is expanded from reproducible fixtures rather than by hardcoding one obfuscated file.

## Attribution

Prometheus is by Elias Oelschner and contributors. This project is an independent deobfuscator and does not bundle Prometheus source code.

## Legacy WAD engine

The existing `wad_deobf` package and `wad-deobf` CLI remain available for WeAreDevs WAD output. Prometheus support is implemented independently under `prometheus_deobf`.
