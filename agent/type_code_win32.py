"""Limpa e digita somente o código 7306 no campo Produto visível."""
import ctypes
import json
import sys
import time
from ctypes import wintypes

from inspect_pdv_win32 import inspect
from pdv_geometry import require_safe_layout
from restore_pdv_win32 import restore


def type_code():
    if sys.platform != "win32":
        raise RuntimeError("Esta ação só funciona no Windows.")
    snapshot = inspect()
    sales = [w for w in snapshot["windows"]
             if w["title"] == "PDV-FISCAL" and w["class"] == "TFVendas"]
    if len(sales) != 1:
        raise RuntimeError("Não há uma única tela PDV-FISCAL; código não digitado.")
    sale = sales[0]
    require_safe_layout(sale)
    roles = {c["role"]: c for c in sale["controls"] if c["role"] != "unknown"}
    field = roles.get("product_search")
    if not field or not field["enabled"]:
        raise RuntimeError("Campo Produto indisponível; código não digitado.")
    if roles.get("sale_price", {}).get("value") not in {"0,000", "0.000", "0"} or \
       roles.get("line_total", {}).get("value") not in {"0,00", "0.00", "0"}:
        raise RuntimeError("Preço ou total não zerados; código não digitado.")
    if any(c["class"] == "TArpaAdvDBGrid" and c["enabled"] for c in sale["controls"]):
        raise RuntimeError("A lista de resultados já está aberta; código não alterado.")

    activation = restore()
    if not activation.get("visible"):
        raise RuntimeError("A janela do PDV não ficou visível; código não digitado.")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    HWND = wintypes.HWND
    user32.GetForegroundWindow.restype = HWND
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = wintypes.BOOL
    user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.DWORD, ctypes.c_size_t]
    user32.mouse_event.restype = None
    user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

    left, top, right, bottom = field["rectangle"]
    if not user32.SetCursorPos((left + right) // 2, (top + bottom) // 2):
        raise ctypes.WinError(ctypes.get_last_error())
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.15)
    foreground = user32.GetForegroundWindow()
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(foreground, ctypes.byref(pid))
    if int(pid.value) != sale["process_id"]:
        raise RuntimeError("O clique não ativou o PDV; nenhuma tecla enviada.")

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.c_size_t)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                    ("wParamH", wintypes.WORD)]

    class INPUTUNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("data",)
        _fields_ = [("type", wintypes.DWORD), ("data", INPUTUNION)]

    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT

    def key(vk, down):
        event = INPUT(type=1, ki=KEYBDINPUT(vk, 0, 0 if down else 0x0002, 0, 0))
        array = (INPUT * 1)(event)
        if user32.SendInput(1, array, ctypes.sizeof(INPUT)) != 1:
            raise ctypes.WinError(ctypes.get_last_error())

    # Seleciona o texto anterior e o substitui com teclas virtuais reais.
    key(0x11, True)   # Ctrl
    key(0x41, True)   # A
    key(0x41, False)
    key(0x11, False)
    key(0x08, True)   # Backspace
    key(0x08, False)
    time.sleep(0.1)
    for digit in (0x37, 0x33, 0x30, 0x36):
        key(digit, True)
        key(digit, False)
        time.sleep(0.03)
    time.sleep(0.3)
    after = inspect()
    result = [w for w in after["windows"]
              if w["title"] == "PDV-FISCAL" and w["class"] == "TFVendas"]
    fields_after = {c["role"]: c.get("value", "") for w in result for c in w["controls"]
                    if c["role"] in {"product_search", "quantity", "sale_price", "line_total"}}
    return {"ok": True, "typed": fields_after.get("product_search") == "7306",
            "fields": fields_after, "paymentSent": False, "enterSent": 0}


if __name__ == "__main__":
    try:
        print(json.dumps(type_code(), ensure_ascii=False))
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        sys.exit(1)
