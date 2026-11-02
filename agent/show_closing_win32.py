"""Traz a janela de fechamento do PDV à frente, sem enviar teclas ou editar campos."""
import ctypes
import json
import sys
import time
from ctypes import wintypes

from inspect_pdv_win32 import inspect
from pdv_config import PDV_CLOSING_CLASS, is_closing_title


def show_closing():
    if sys.platform != "win32":
        raise RuntimeError("Esta ação só funciona no Windows.")
    snapshot = inspect()
    dialogs = [window for window in snapshot["windows"]
               if window["class"] == PDV_CLOSING_CLASS and
               is_closing_title(window["title"])]
    if len(dialogs) != 1:
        raise RuntimeError("Não encontrei uma única janela de fechamento; nada foi ativado.")

    hwnd_value = dialogs[0]["hwnd"]
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    HWND = wintypes.HWND
    user32.GetForegroundWindow.restype = HWND
    user32.ShowWindow.argtypes = [HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = [HWND]
    user32.BringWindowToTop.restype = wintypes.BOOL
    user32.SetActiveWindow.argtypes = [HWND]
    user32.SetActiveWindow.restype = HWND
    user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user32.AttachThreadInput.restype = wintypes.BOOL
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    hwnd = HWND(hwnd_value)
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)

    def foreground():
        value = user32.GetForegroundWindow()
        return int(getattr(value, "value", value) or 0)

    deadline = time.monotonic() + 0.7
    while time.monotonic() < deadline and foreground() != hwnd_value:
        time.sleep(0.05)

    if foreground() != hwnd_value:
        current_thread = kernel32.GetCurrentThreadId()
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)
        attached = bool(user32.AttachThreadInput(current_thread, target_thread, True))
        try:
            if attached:
                user32.SetActiveWindow(hwnd)
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(current_thread, target_thread, False)
        deadline = time.monotonic() + 0.7
        while time.monotonic() < deadline and foreground() != hwnd_value:
            time.sleep(0.05)

    return {"ok": True, "activated": foreground() == hwnd_value,
            "paymentSent": False, "confirmationSent": False,
            "closingWindow": dialogs[0]}


if __name__ == "__main__":
    try:
        print(json.dumps(show_closing(), ensure_ascii=False))
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        sys.exit(1)
