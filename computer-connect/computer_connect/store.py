"""Windows user-scoped DPAPI; no plaintext credential persistence or fallback."""
import base64
import ctypes
import json
import os
from pathlib import Path
import tempfile

from .transport import ConnectError, Endpoint, valid_token


class Blob(ctypes.Structure):
    _fields_ = [('size', ctypes.c_uint32), ('data', ctypes.c_void_p)]


def dpapi(data, decrypt=False):
    if os.name != 'nt':
        raise ConnectError('Remembering a pairing is supported only with Windows user protection. Pairing stays in memory here.')
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    buf = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buf, ctypes.c_void_p))
    output = Blob()
    # Flags=CRYPTPROTECT_UI_FORBIDDEN, no machine-wide protection flag.
    if decrypt:
        fn = crypt.CryptUnprotectData
        fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(Blob)]
        args = (ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output))
    else:
        fn = crypt.CryptProtectData
        fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_wchar_p, ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(Blob)]
        args = (ctypes.byref(source), 'Couchside Computer Connect', None, None, None, 1, ctypes.byref(output))
    fn.restype = ctypes.c_int
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not fn(*args):
        raise ConnectError('Windows could not unlock this pairing. Forget it and pair again.')
    try:return ctypes.string_at(output.data, output.size)
    finally:kernel.LocalFree(output.data)


def default_path():
    parent = Path(os.environ.get('LOCALAPPDATA', Path.home()/'.config'))
    return parent/'Couchside Computer Connect'/'pairing.json'


class Store:
    def __init__(self, path=None):
        self.path = Path(path) if path else default_path()

    def save(self, endpoint, token):
        # Bind host + port + pin inside encrypted data, so editing public
        # metadata cannot redirect an existing token to a different peer.
        data = json.dumps({'host':endpoint.host, 'port':endpoint.port,
                           'fingerprint':endpoint.fingerprint, 'token':valid_token(token)}).encode()
        wrapped = dpapi(data)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix='.pairing-')
        try:
            with os.fdopen(fd,'w') as out:
                json.dump({'format':1, 'dpapi':base64.b64encode(wrapped).decode()},out)
            os.replace(tmp,self.path)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)

    def load(self):
        if not self.path.exists():return None
        try:
            if self.path.stat().st_size > 32768:raise ValueError()
            data = json.loads(self.path.read_text())
            if data.get('format') != 1:raise ValueError()
            plain = json.loads(dpapi(base64.b64decode(data['dpapi'],validate=True),decrypt=True))
            return Endpoint(plain['host'],plain['port'],plain['fingerprint']), valid_token(plain['token'])
        except Exception:
            raise ConnectError('Saved pairing cannot be unlocked. Forget it and pair again.') from None

    def forget(self):
        self.path.unlink(missing_ok=True)
