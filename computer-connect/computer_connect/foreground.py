"""Own-process foreground checks. No window titles or other-app data collected."""
import ctypes
import os
import sys


def active(root):
    try:
        if os.name=='nt':
            user=ctypes.WinDLL('user32')
            user.GetForegroundWindow.restype=ctypes.c_void_p
            user.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint32)]
            pid=ctypes.c_uint32()
            user.GetWindowThreadProcessId(user.GetForegroundWindow(),ctypes.byref(pid))
            return pid.value==os.getpid()
        if sys.platform=='darwin':
            objc=ctypes.CDLL('/usr/lib/libobjc.A.dylib')
            objc.objc_getClass.argtypes=[ctypes.c_char_p];objc.objc_getClass.restype=ctypes.c_void_p
            objc.sel_registerName.argtypes=[ctypes.c_char_p];objc.sel_registerName.restype=ctypes.c_void_p
            send=ctypes.CFUNCTYPE(ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p)(('objc_msgSend',objc))
            boolean=ctypes.CFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)(('objc_msgSend',objc))
            app=send(objc.objc_getClass(b'NSApplication'),objc.sel_registerName(b'sharedApplication'))
            return bool(app and boolean(app,objc.sel_registerName(b'isActive')))
        return root.focus_displayof() is not None
    except Exception:
        return False  # unknown focus cannot retain remote input authority
