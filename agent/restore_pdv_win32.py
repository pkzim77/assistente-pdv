"""Restaura a janela principal do PDV sem enviar teclas ou editar a venda."""
import ctypes
import json
import sys
import time
from ctypes import wintypes

from inspect_pdv_win32 import inspect
from pdv_config import is_sale_window


def restore():
    if sys.platform != "win32":
        raise RuntimeError("Esta ação só funciona no Windows.")
    windows = [window for window in inspect()["windows"] if is_sale_window(window)]
    if len(windows) != 1:
        raise RuntimeError("Não encontrei uma única janela principal do PDV; nada foi ativado.")
    hwnd_value = windows[0]["hwnd"]
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    HWND = wintypes.HWND
    user32.ShowWindow.argtypes = [HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = [HWND]
    user32.BringWindowToTop.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.GetForegroundWindow.restype = HWND
    user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user32.AttachThreadInput.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [HWND, HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SetWindowPos.restype = wintypes.BOOL
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    hwnd = HWND(hwnd_value)
    # HWND_TOP is NULL. HWND(-1) is HWND_TOPMOST and leaves the PDV above
    # every other window, preventing the operator from returning to the panel.
    top = HWND(0)
    flags = 0x0001 | 0x0002 | 0x0040  # SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW
    user32.SetWindowPos(hwnd, top, 0, 0, 0, 0, flags)
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE, inclusive se a janela estava minimizada
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.15)
    foreground = user32.GetForegroundWindow()
    foreground_value = int(getattr(foreground, "value", foreground) or 0)
    if foreground_value != hwnd_value:
        current_foreground = user32.GetForegroundWindow()
        foreground_thread = user32.GetWindowThreadProcessId(current_foreground, None)
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)
        attached = bool(user32.AttachThreadInput(foreground_thread, target_thread, True))
        try:
            if attached:
                user32.ShowWindow(hwnd, 9)
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(foreground_thread, target_thread, False)
        time.sleep(0.15)
    foreground = user32.GetForegroundWindow()
    foreground_value = int(getattr(foreground, "value", foreground) or 0)
    return {"ok": True, "activated": foreground_value == hwnd_value,
            "visible": bool(user32.IsWindowVisible(hwnd)),
            "paymentSent": False, "confirmationSent": False, "window": windows[0]}


if __name__ == "__main__":
    try:
        print(json.dumps(restore(), ensure_ascii=False))
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        sys.exit(1)
