import pytest

from wad_deobf import detector


WAD = '''--[[ v1.0.0 https://wearedevs.net/obfuscator ]] return(function(...)local e={"abc"}for n,Y in ipairs({{1,1}})do while Y[1]<Y[2]do e[Y[1]],e[Y[2]],Y[1],Y[2]=e[Y[2]],e[Y[1]],Y[1]+1,Y[2]-1 end end local function n(n)return e[n+23]end return(function()end)()end)(...)'''


def test_detect_wad_returns_version_and_string_table_span():
    info = detector.detect_wad(WAD)
    assert info.version == "1.0.0"
    assert WAD[info.table_start:info.table_end] == '{"abc"}'


def test_detect_wad_accepts_structure_without_marker():
    info = detector.detect_wad(WAD.split("]]", 1)[1])
    assert info.version is None


def test_detect_wad_rejects_marker_only_false_positive():
    with pytest.raises(ValueError, match="WAD"):
        detector.detect_wad("--[[ v1.0.0 https://wearedevs.net/obfuscator ]] print('hello')")
