"""Mostra a visibilidade e a árvore de controles sem ler valores digitados."""
import ctypes
import json
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [EnumProc, wintypes.LPARAM]
user32.EnumChildWindows.argtypes = [wintypes.HWND, EnumProc, wintypes.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.c_void_p]


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


def info(hwnd):
    title = ctypes.create_unicode_buffer(512)
    kind = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, title, len(title))
    user32.GetClassNameW(hwnd, kind, len(kind))
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return {"hwnd": int(hwnd), "title": title.value, "class": kind.value,
            "visible": bool(user32.IsWindowVisible(hwnd)),
            "rect": [rect.left, rect.top, rect.right, rect.bottom]}


target = 0
windows = []


@EnumProc
def children(hwnd, _):
    if len(windows[-1]["children"]) < 80:
        windows[-1]["children"].append(info(hwnd))
    return True


@EnumProc
def top_level(hwnd, _):
    global target
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    title = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, title, len(title))
    kind = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, kind, len(kind))
    if pid.value == target and kind.value in {"TFVendas", "TFSplashScreen", "TParentForm", "TFecha_Venda"}:
        row = info(hwnd)
        row["children"] = []
        windows.append(row)
        user32.EnumChildWindows(hwnd, children, 0)
    return True


if __name__ == "__main__":
    import sys
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    user32.EnumWindows(top_level, 0)
    print(json.dumps({"pid": target, "windows": windows}, ensure_ascii=False))
