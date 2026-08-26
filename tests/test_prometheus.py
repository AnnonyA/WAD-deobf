import base64

from prometheus_deobf.cleanup import remove_antitamper
from prometheus_deobf.constant_array import recover_constant_arrays
from prometheus_deobf.encrypt_strings import decrypt_string, recover_encrypted_strings
from prometheus_deobf.literals import decode_lua_string, encode_lua_string
from prometheus_deobf.numbers import eval_numeric, fold_numeric_expressions
from prometheus_deobf.pipeline import deobfuscate
from prometheus_deobf.unwrap import unwrap_generated_iife
from prometheus_deobf.vm import analyze_vm, lift_linear_dispatcher


def test_numeric_folding_is_safe():
    assert eval_numeric('(10 + 2) * 3 - 4 ^ 2') == 20
    src = 'local x=(40+2)\nlocal s="(40+2)"\n-- (4+5)'
    out, count = fold_numeric_expressions(src)
    assert 'local x=42' in out and '"(40+2)"' in out and '-- (4+5)' in out
    assert count == 1


def test_lua_literals_and_generated_wrapper():
    token = '"\\072\\101\\108\\108\\111\\010"'
    value = decode_lua_string(token)
    assert value == 'Hello\n'
    assert decode_lua_string(encode_lua_string(value)) == value
    src = 'return(function(...)local x=1;print(x)return x end)(...)'
    out, count = unwrap_generated_iife(src)
    assert count == 1 and out == 'local x=1;print(x)return x'


def test_constant_array_rotation_and_custom_base64():
    std = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
    custom = std[::-1]
    trans = str.maketrans(std, custom)
    enc = lambda text: base64.b64encode(text.encode()).decode().translate(trans)
    lookup = ','.join(f'["{ch}"]={i}' for i, ch in enumerate(custom))
    src = f'''local A={{"{enc('world')}","{enc('hello')}"}}
local lookup={{{lookup}}}
for i,v in ipairs({{{{1,2}},{{1,1}},{{2,2}}}}) do while v[1]<v[2] do A[v[1]],A[v[2]],v[1],v[2]=A[v[2]],A[v[1]],v[1]+1,v[2]-1 end end
local function W(x)return A[x+5]end
print(W(-4), W(-3))'''
    result = recover_constant_arrays(src)
    assert 'print("hello", "world")' in result.source
    assert result.details['decoded_entries'] == 2


def _encrypt(plain, seed, mul45, add45, mul8, key8):
    state45 = seed % 35184372088832
    state8 = seed % 255 + 2
    prev_values = []
    prev = key8
    out = bytearray()
    for byte in plain.encode():
        if not prev_values:
            state45 = (state45 * mul45 + add45) % 35184372088832
            while True:
                state8 = state8 * mul8 % 257
                if state8 != 1:
                    break
            r = state8 % 32
            n = (state45 // (2 ** (13 - (state8 - r) // 32))) % (2 ** 32) / (2 ** r)
            rnd = int((n % 1) * 2 ** 32) + int(n)
            low = rnd % 65536
            high = (rnd - low) // 65536
            prev_values = [low % 256, low // 256, high % 256, high // 256]
        rand = prev_values.pop()
        out.append((byte - (rand + prev)) % 256)
        prev = byte
    return bytes(out).decode('latin1')


def test_encrypt_strings_round_trip_and_rewrite():
    mul45, add45, mul8, key8 = 5, 123456789, 3, 77
    seed = 987654321
    cipher = _encrypt('hello prometheus', seed, mul45, add45, mul8, key8)
    assert decrypt_string(cipher, seed, mul45, add45, mul8, key8) == 'hello prometheus'
    token = encode_lua_string(cipher)
    src = f'''local state_45=0;local state_8=2
state_45=(state_45*{mul45}+{add45})%35184372088832
state_8=state_8*{mul8}%257
local prevVal={key8}
print(S[D({token},{seed})])'''
    assert 'print("hello prometheus")' in recover_encrypted_strings(src).source


def test_antitamper_requires_multiple_prometheus_markers():
    src = '''do local valid=true local pcallIntact=true
local err=function() error("Tamper Detected!") end
repeat until valid end
print("ok")'''
    assert 'Tamper Detected!' not in remove_antitamper(src).source
    near = 'do error("Tamper Detected!") end'
    assert remove_antitamper(near).source == near


def test_linear_vm_lifting_and_runtime_branch_fallback():
    src = '''local pc=104729
while pc do
 if pc < 200000 then
  if pc < 150000 then print("first");pc=390001 else print("wrong");pc=nil end
 else
  if pc < 500000 then print("second");pc=nil else print("wrong2");pc=nil end
 end
end'''
    assert analyze_vm(src).detected
    result = lift_linear_dispatcher(src)
    assert result.details['resolved_states'] == [104729, 390001]
    assert 'first' in result.source and 'second' in result.source and 'wrong' not in result.source

    dynamic = 'local pc=10\nwhile pc do if pc < 20 then if flag then pc=30 else pc=40 end else pc=nil end end'
    unresolved = lift_linear_dispatcher(dynamic)
    assert unresolved.changes == 0 and unresolved.details['unresolved'] is True


def test_pipeline_reaches_fixed_point():
    result = deobfuscate('return(function(...)local x=(20+22);print(x,"ok") end)(...)')
    assert 'local x=42' in result.source
    assert 'return(function' not in result.source
    assert result.total_changes >= 2
