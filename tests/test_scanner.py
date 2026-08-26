import pytest

from wad_deobf import scanner


def test_find_balanced_ignores_delimiters_inside_strings():
    source = 'x={"}", {"{nested}"}, "\\\"}"} tail'
    start = source.index("{")
    begin, end = scanner.find_balanced(source, start, "{", "}")
    assert source[begin:end] == '{"}", {"{nested}"}, "\\\"}"}'


def test_find_balanced_ignores_lua_comments():
    source = "x={1, -- } ignored\n2, --[[ { } ]] 3} tail"
    start = source.index("{")
    _, end = scanner.find_balanced(source, start, "{", "}")
    assert source[end:].strip() == "tail"


def test_find_balanced_rejects_unclosed_fragment():
    with pytest.raises(ValueError):
        scanner.find_balanced("x={1,2", 2, "{", "}")


def test_split_top_level_handles_nested_tables_and_calls():
    body = '"a", {1, 2}; fn(3, 4), "b,c"'
    assert scanner.split_top_level(body, ",;") == [
        '"a"',
        "{1, 2}",
        "fn(3, 4)",
        '"b,c"',
    ]
