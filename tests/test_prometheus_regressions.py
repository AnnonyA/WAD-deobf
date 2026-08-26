import base64

from prometheus_deobf.constant_array import recover_constant_arrays
from prometheus_deobf.unwrap import unwrap_generated_iife
from prometheus_deobf.vm import analyze_vm, lift_linear_dispatcher


def test_unwrap_handles_nested_prometheus_body():
    source = 'return(function(...)for i=1,2 do if i then print(i) end end return 1 end)(...)'
    output, changes = unwrap_generated_iife(source)
    assert changes == 1
    assert output == 'for i=1,2 do if i then print(i) end end return 1'


def test_constant_array_matches_prometheus_unparser_shape():
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
    shuffled = alphabet[::-1]
    encoded = base64.b64encode(b'prometheus').decode().translate(str.maketrans(alphabet, shuffled))
    entries = []
    for index, char in enumerate(shuffled):
        key = char if char.isalpha() else f'["\\{ord(char):03d}"]'
        value = f'{index + 100}-100' if index % 2 == 0 else str(index)
        entries.append(f'{key}={value}')
    source = (
        f'local A={{"{encoded}","{encoded}"}} '
        f'local k={{{";".join(entries)}}} '
        'local function W(x)return A[x+1]end '
        'print(W(-100-(-100)))'
    )
    result = recover_constant_arrays(source)
    assert 'print("prometheus")' in result.source


def test_vm_detector_prefers_state_dispatcher_over_helper_loop():
    source = '''local helper={1}; local h=1
while h do h=helper[h] end
local pc=100
while pc do
 if pc < 200 then print("a"); pc=300 else print("b"); pc=nil end
end'''
    report = analyze_vm(source)
    assert report.detected is True
    assert report.position == 'pc'
    lifted = lift_linear_dispatcher(source)
    assert lifted.changes == 1
    assert 'print("a")' in lifted.source


def test_vm_lifter_never_steals_outer_scope_state():
    source = '''local pc=10
local f=function(pc)
while pc do
 if pc < 20 then print("inner"); pc=nil else print("other"); pc=nil end
end
end'''
    result = lift_linear_dispatcher(source)
    assert result.changes == 0
    assert result.details['reason'] == 'initial-state-not-found'
