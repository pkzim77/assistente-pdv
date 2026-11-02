"""Abre o fechamento do PDV em segundo plano com F6; não informa pagamento."""
import ctypes
import json
import sys
import time
from ctypes import wintypes

from inspect_pdv_win32 import inspect
from pdv_geometry import require_safe_layout


def open_closing():
    if sys.platform != "win32":
        raise RuntimeError("Esta ação só funciona no Windows.")

    before = inspect()
    sales = [window for window in before["windows"]
             if window["title"] == "PDV-FISCAL" and window["class"] == "TFVendas"]
    if len(sales) != 1:
        raise RuntimeError("É necessário exatamente uma janela PDV-FISCAL; F6 não enviado.")
    require_safe_layout(sales[0])

    from restore_pdv_win32 import restore as restore_pdv_window
    activation = restore_pdv_window()
    if not activation.get("visible") or not activation.get("activated"):
        raise RuntimeError("A janela do PDV não ficou ativa; F6 não enviado.")
    before = inspect()
    sales = [window for window in before["windows"]
             if window["title"] == "PDV-FISCAL" and window["class"] == "TFVendas"]
    if len(sales) != 1:
        raise RuntimeError("A janela do PDV mudou durante a ativação; F6 não enviado.")
    require_safe_layout(sales[0])

    hwnd_value = sales[0]["hwnd"]
    focus_value = sales[0]["focused_hwnd"]
    child_handles = {control["hwnd"] for control in sales[0]["controls"]}
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
    user32.SetFocus.argtypes = [HWND]
    user32.SetFocus.restype = HWND
    user32.IsChild.argtypes = [HWND, HWND]
    user32.IsChild.restype = wintypes.BOOL
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = wintypes.BOOL
    user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.DWORD, ctypes.c_size_t]
    user32.mouse_event.restype = None

    def current_foreground():
        foreground = user32.GetForegroundWindow()
        return int(getattr(foreground, "value", foreground) or 0)

    if current_foreground() != hwnd_value:
        main_hwnd = HWND(hwnd_value)
        focus_hwnd = HWND(focus_value) if focus_value else main_hwnd
        user32.ShowWindow(main_hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(main_hwnd)
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and current_foreground() != hwnd_value:
            time.sleep(0.05)

        if current_foreground() != hwnd_value:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetCurrentThreadId.restype = wintypes.DWORD
            user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(wintypes.DWORD)]
            user32.GetWindowThreadProcessId.restype = wintypes.DWORD
            user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
            user32.AttachThreadInput.restype = wintypes.BOOL
            current_thread = kernel32.GetCurrentThreadId()
            target_thread = user32.GetWindowThreadProcessId(main_hwnd, None)
            attached = bool(user32.AttachThreadInput(current_thread, target_thread, True))
            try:
                if attached:
                    user32.BringWindowToTop(main_hwnd)
                    user32.SetActiveWindow(main_hwnd)
                    user32.SetFocus(focus_hwnd)
                    user32.SetForegroundWindow(main_hwnd)
            finally:
                if attached:
                    user32.AttachThreadInput(current_thread, target_thread, False)
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline and current_foreground() != hwnd_value:
                time.sleep(0.05)

    if current_foreground() == hwnd_value and (not focus_value or
            (focus_value not in child_handles and
             not user32.IsChild(HWND(hwnd_value), HWND(focus_value)))):
        product = next((control for control in sales[0]["controls"]
                        if control["role"] == "product_search" and control["enabled"]), None)
        if not product:
            raise RuntimeError("Campo Produto não encontrado; F6 não enviado.")
        left, top, right, bottom = product["rectangle"]
        if not user32.SetCursorPos((left + right) // 2, (top + bottom) // 2):
            raise ctypes.WinError(ctypes.get_last_error())
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
        time.sleep(0.15)
        refreshed = inspect()
        refreshed_sales = [window for window in refreshed["windows"]
                           if window["title"] == "PDV-FISCAL" and window["class"] == "TFVendas"]
        if len(refreshed_sales) != 1:
            raise RuntimeError("A janela do PDV mudou ao focar Produto; F6 não enviado.")
        sales = refreshed_sales
        focus_value = sales[0]["focused_hwnd"]
        child_handles = {control["hwnd"] for control in sales[0]["controls"]}

    if not focus_value or (focus_value not in child_handles and
                           not user32.IsChild(HWND(hwnd_value), HWND(focus_value))):
        raise RuntimeError("O foco não está em um controle do PDV; F6 não enviado.")

    if current_foreground() == hwnd_value:
        ULONG_PTR = ctypes.c_size_t

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ULONG_PTR)]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                        ("wParamH", wintypes.WORD)]

        class INPUT_UNION(ctypes.Union):
            # INPUT's union must use its full Windows size even for keyboard
            # events; a keyboard-only union makes SendInput reject cbSize.
            _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT),
                        ("hi", HARDWAREINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("union",)
            _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]

        user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        user32.SendInput.restype = wintypes.UINT
        events = (INPUT * 2)()
        events[0].type = 1  # INPUT_KEYBOARD
        events[0].ki = KEYBDINPUT(0x75, 0x40, 0, 0, 0)  # VK_F6 down
        events[1].type = 1
        events[1].ki = KEYBDINPUT(0x75, 0x40, 0x0002, 0, 0)  # VK_F6 up
        sent = user32.SendInput(2, events, ctypes.sizeof(INPUT))
        if sent != 2:
            raise ctypes.WinError(ctypes.get_last_error())
        delivery = "SendInput após confirmar foco do PDV"
    else:
        # Fallback de segundo plano, limitado ao controle que o Windows informa
        # como focado dentro do PDV. Não usa o teclado global.
        if not focus_value or (focus_value not in child_handles and
                               not user32.IsChild(HWND(hwnd_value), HWND(focus_value))):
            raise RuntimeError("Sem foco confiável no PDV; F6 não enviado.")
        user32.PostMessageW.argtypes = [HWND, wintypes.UINT,
                                        ctypes.c_size_t, ctypes.c_ssize_t]
        user32.PostMessageW.restype = wintypes.BOOL
        keydown_lparam = 1 | (0x40 << 16)
        keyup_lparam = keydown_lparam | (1 << 30) | (1 << 31)
        if not user32.PostMessageW(HWND(focus_value), 0x0100, 0x75, keydown_lparam):
            raise ctypes.WinError(ctypes.get_last_error())
        if not user32.PostMessageW(HWND(focus_value), 0x0101, 0x75, keyup_lparam):
            raise ctypes.WinError(ctypes.get_last_error())
        delivery = "PostMessage F6 ao controle focado do PDV"

    time.sleep(0.8)
    from pathlib import Path
    Path(__file__).with_name("capture-pdv.request").write_text(
        "FECHAMENTO DE VENDA", encoding="utf-8")
    after = inspect()
    closing = [window for window in after["windows"]
               if "FECHAMENTO DE VENDA" in window["title"].upper()]
    if len(closing) != 1:
        raise RuntimeError(
            "F6 foi enviado ao PDV, mas a janela única de fechamento não foi detectada. "
            "Nenhuma tecla de pagamento ou confirmação foi enviada."
        )
    return {
        "ok": True,
        "f6Sent": True,
        "paymentSent": False,
        "confirmationSent": False,
        "delivery": delivery,
        "closingWindow": closing[0],
        "windows": after["windows"],
    }


if __name__ == "__main__":
    try:
        print(json.dumps(open_closing(), ensure_ascii=False))
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        sys.exit(1)
