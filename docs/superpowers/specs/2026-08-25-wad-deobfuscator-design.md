# WAD Deobfuscator Design

## Goal

Build a static deobfuscator for WeAreDevs WAD Lua/Luau output that recovers readable, semantically equivalent Luau without executing the obfuscated payload.

The first regression fixture is the provided WAD v1.0.0 pair: one original source file and one obfuscated output file.

## Scope

The initial version targets the WAD v1.0.0 structure observed in the supplied sample:

- encoded and shuffled string table
- per-sample custom 64-character alphabet
- arithmetic constant noise
- generated aliases around Lua/Luau built-ins
- VM/control-flow flattening driven by numeric states
- wrapper/proxy functions used to invoke VM handlers

The implementation must derive structure from the input. It must not hardcode recovered strings, state IDs, symbol names, or offsets from the supplied fixture.

## Recovery Contract

Exact byte-for-byte source recovery is only possible for information preserved by the obfuscator. The tool will therefore use two recovery levels:

1. **Exact recovery** for preserved literals and structural information when it can be proven from the payload.
2. **Canonical semantic recovery** when the original spelling, comments, formatting, or local names were discarded.

Comments and original local identifiers are not guessed. Generated names should be stable and readable.

## Architecture

### 1. WAD detector

Identify supported WAD wrappers before deeper parsing. Detection should be structural, with the version marker used as supporting evidence rather than the only signal.

Unsupported input should fail with a concise diagnostic instead of attempting execution.

### 2. Safe expression evaluator

Parse and evaluate only the constant expression subset emitted by WAD, initially:

- integers
- unary minus
- addition
- subtraction
- multiplication
- division/modulo when needed by a recognized transform
- parentheses

No arbitrary Lua evaluation is allowed.

### 3. String table recovery

Extract the encoded string table, reconstruct WAD's table permutation, derive the custom alphabet from the decoder mapping, and decode strings.

This stage should expose a normalized index-to-string table for later passes.

### 4. Normalization pass

Fold arithmetic noise and resolve aliases/index calculations where values are statically known. The result should make VM structure easier to analyze without changing runtime semantics.

### 5. VM model

Represent the flattened program with a small intermediate representation:

- states/basic blocks
- register/local reads and writes
- constant loads
- table/index operations
- calls
- branches
- returns

The first implementation should model only operations demonstrated by verified WAD patterns and reject unknown patterns cleanly.

### 6. Lifter

Translate recognized WAD state transitions into the intermediate representation. Prefer pattern families over exact numeric-state matches so independently obfuscated inputs can be handled.

The lifter must remain static. It must not run the payload, invoke `loadstring`, or depend on Roblox/executor APIs.

### 7. Luau emitter

Emit readable Luau from the recovered IR. Use stable generated names when originals are unavailable, preserve recoverable strings/constants exactly, and reduce obvious temporary noise.

Formatting should be deterministic so fixture diffs remain useful.

### 8. CLI

Provide a small command-line interface:

```text
wad-deobf input.lua [-o output.lua]
```

Default behavior writes recovered source to stdout. Errors go to stderr and use non-zero exit codes.

## Suggested Project Layout

```text
src/wad_deobf/
  __init__.py
  cli.py
  detector.py
  expressions.py
  strings.py
  normalize.py
  ir.py
  lift.py
  emit.py

tests/
  fixtures/
  test_detector.py
  test_expressions.py
  test_strings.py
  test_lift.py
  test_regression.py
```

Python is used for the first implementation because the available workspace already has Python 3.13 and it allows a small dependency-free static-analysis tool.

## Testing Strategy

Development follows TDD.

### Unit tests

Cover each reversible layer independently:

- WAD detection
- arithmetic folding
- table permutation
- alphabet extraction
- string decoding
- representative VM pattern lifting
- deterministic emitting

### Regression fixture

The supplied original/obfuscated pair is the main end-to-end oracle.

The test should distinguish between:

- exact text that the payload demonstrably preserves
- semantic structure that can be reconstructed
- unrecoverable presentation information such as comments or discarded local names

The regression should not pass by embedding the original file in the implementation.

### Safety tests

Assert that malformed or unsupported inputs are rejected without executing embedded Lua.

## Error Handling

Use explicit errors for:

- unsupported WAD layout/version
- malformed numeric expressions
- invalid custom alphabet
- truncated string data
- unknown VM handler/pattern

Diagnostics should identify the failing stage and enough local context to debug new WAD variants.

## Repository and Integration

Implementation will be developed on a feature branch, with small human-style commits and minimal source comments. Public-facing code and documentation stay in English.

Before merge:

- unit and regression tests must pass
- the fixture must prove the decoder is not hardcoded to known output
- the branch diff must be reviewed
- a pull request will be opened and merged into `main`

## Non-goals for v1

- recovering comments that no longer exist in the payload
- guessing original local variable names
- executing obfuscated code to observe behavior
- supporting unrelated Lua obfuscators
- claiming universal support for future WAD versions without fixtures

## Success Criteria

The first release is successful when it can take the supplied WAD v1.0.0 sample, statically recover its preserved strings/constants and program behavior into readable Luau, and do so through generic transforms that are covered by tests rather than fixture-specific replacements.
