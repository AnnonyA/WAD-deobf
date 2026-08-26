import importlib
import importlib.util

from wad_deobf.semantic_ir import Opaque


def _patterns():
    assert importlib.util.find_spec("wad_deobf.patterns") is not None
    return importlib.import_module("wad_deobf.patterns")


def test_registry_uses_first_full_match():
    patterns = _patterns()
    first = patterns.StatementPattern(
        "first",
        r"move\((?P<value>\w+)\)",
        lambda context, match: (Opaque(context.state, f"first:{match.group('value')}"),),
    )
    second = patterns.StatementPattern(
        "second",
        r"move\((?P<value>\w+)\)",
        lambda context, match: (Opaque(context.state, "second"),),
    )
    context = patterns.PatternContext(17, "cursor", "move(slot)")

    assert patterns.lift_statement(context, (first, second)) == (Opaque(17, "first:slot"),)


def test_statement_pattern_requires_a_full_match():
    patterns = _patterns()
    pattern = patterns.StatementPattern(
        "exact",
        r"move\((?P<value>\w+)\)",
        lambda context, match: (Opaque(context.state, "matched"),),
    )
    context = patterns.PatternContext(23, "pc", "prefix move(slot)")

    assert patterns.lift_statement(context, (pattern,)) is None


def test_registry_rejects_unknown_statement_without_side_effects():
    patterns = _patterns()
    pattern = patterns.StatementPattern(
        "known",
        r"known",
        lambda context, match: (Opaque(context.state, "known"),),
    )
    context = patterns.PatternContext(31, "state", "unknown")

    assert patterns.lift_statement(context, (pattern,)) is None
