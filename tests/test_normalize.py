import base64

from wad_deobf import normalize


ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def _literal(value: str) -> str:
    return '"' + "".join(f"\\{ord(char):03d}" for char in value) + '"'


def _alphabet() -> str:
    entries = []
    for index, char in enumerate(ALPHABET):
        key = char if char.isalpha() else f'["\\{ord(char):03d}"]'
        entries.append(f"{key}={index + 500}-500")
    return ",".join(entries)


def _source(raw: list[bytes], body: str = "", offset: str = "7") -> str:
    encoded = [base64.b64encode(value).decode("ascii") for value in raw]
    table = ";".join(_literal(value) for value in encoded)
    return (
        "--[[ v1.0.0 https://wearedevs.net/obfuscator ]] "
        f"return(function(...)local e={{{table}}}"
        f"for n,Y in ipairs({{{{1,{len(raw)}}}}})do while Y[1]<Y[2]do "
        "e[Y[1]],e[Y[2]],Y[1],Y[2]=e[Y[2]],e[Y[1]],Y[1]+1,Y[2]-1 end end "
        f"local function n(n)return e[n+({offset})]end "
        f"do local n={{{_alphabet()}}}local Y=string.sub local K=string.char end "
        f"{body} return(function()end)()end)(...)"
    )


def test_normalize_resolves_constant_lookup_with_offset():
    source = _source([b"second", b"first"], 'local value=n(-6)')
    result = normalize.normalize_wad(source)
    assert result.lookup_name == "n"
    assert result.lookup_offset == 7
    assert result.decoded_strings == (b"first", b"second")
    assert 'local value="first"' in result.source


def test_normalize_folds_code_but_preserves_strings_and_comments():
    source = _source([b"x"], 'local x=100-99 local text="100-99" -- 100-99\n')
    result = normalize.normalize_wad(source)
    assert "local x=1" in result.source
    assert '"100-99"' in result.source
    assert "-- 100-99" in result.source


def test_normalize_quotes_binary_decoded_strings_losslessly():
    source = _source([b"\x00\xff"], 'local value=n(-6)')
    result = normalize.normalize_wad(source)
    assert 'local value="\\000\\255"' in result.source
