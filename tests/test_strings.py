import base64

import pytest

from wad_deobf import strings


ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def lua_decimal(value: str) -> str:
    return '"' + "".join(f"\\{ord(char):03d}" for char in value) + '"'


def alphabet_table() -> str:
    entries = []
    for index, char in enumerate(ALPHABET):
        key = char if (char.isalpha() or char == "_") else f'["\\{ord(char):03d}"]'
        entries.append(f"{key}={index + 1000}-1000")
    return ";".join(entries)


def wad_source(encoded_values: list[str], ranges: str = "{{1,1}}") -> str:
    table = ",".join(lua_decimal(value) for value in encoded_values)
    return (
        "--[[ v1.0.0 https://wearedevs.net/obfuscator ]] "
        f"return(function(...)local e={{{table}}}"
        f"for n,Y in ipairs({ranges})do while Y[1]<Y[2]do "
        "e[Y[1]],e[Y[2]],Y[1],Y[2]=e[Y[2]],e[Y[1]],Y[1]+1,Y[2]-1 end end "
        "local function n(n)return e[n+0]end "
        f"do local n={{{alphabet_table()}}}local Y=string.sub local K=string.char end "
        "return(function()end)()end)(...)"
    )


def test_extract_string_table_decodes_lua_decimal_escapes():
    source = wad_source(["QUJD", "RA=="])
    assert strings.extract_string_table(source) == ["QUJD", "RA=="]


def test_recover_permutation_replays_wad_reverse_ranges():
    source = wad_source(["A", "B", "C", "D"], "{{1+0, 8-4};{1+1, 5-2}}")
    assert strings.recover_permutation(source, 4) == [3, 1, 2, 0]


def test_extract_alphabet_derives_all_64_values():
    source = wad_source(["QQ=="])
    alphabet = strings.extract_alphabet(source)
    assert len(alphabet) == 64
    assert alphabet["A"] == 0
    assert alphabet["/"] == 63


def test_decode_string_supports_padding_and_binary_bytes():
    alphabet = {char: index for index, char in enumerate(ALPHABET)}
    raw = b"A\x00\xffB"
    encoded = base64.b64encode(raw).decode("ascii")
    assert strings.decode_string(encoded, alphabet) == raw


def test_decode_string_rejects_invalid_alphabet():
    with pytest.raises(ValueError, match="alphabet"):
        strings.decode_string("QQ==", {"A": 0})


def test_recover_strings_applies_permutation_before_decoding():
    raw = [b"first", b"second", b"third"]
    encoded = [base64.b64encode(value).decode("ascii") for value in raw]
    source = wad_source(encoded, "{{1,3}}")
    assert strings.recover_strings(source) == [raw[2], raw[1], raw[0]]
