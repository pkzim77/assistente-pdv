"""Limpa ou digita a quantidade no campo Quantidade, sem selecionar produto."""
import argparse
import ctypes
import json
import re
import sys
import time
from ctypes import wintypes

from inspect_pdv_win32 import inspect
from pdv_geometry import require_safe_layout
from restore_pdv_win32 import restore


SALE_TITLE = "PDV-FISCAL"
SALE_CLASS = "TFVendas"
def valid_quantity_text(value):
    value = str(value or "").strip()
    if value in {"", "0", "0,000", "0.000"}:
        return True
    match = re.fullmatch(r"([0-9]{1,6})(?:([,.])000)?", value)
    return bool(match and 1 <= int(match.group(1)) <= 999999)


def sale_window(snapshot):
    sales = [window for window in snapshot["windows"]
             if window["title"] == SALE_TITLE and window["class"] == SALE_CLASS]
    if len(sales) != 1:
        raise RuntimeError("Não há uma única tela de venda; quantidade não alterada.")
    if sales[0].get("visible") is False or sales[0].get("minimized") is True:
        raise RuntimeError("A janela do PDV está oculta ou minimizada; quantidade não alterada.")
    if any("FECHAMENTO DE VENDA" in window["title"].upper()
           for window in snapshot["windows"]):
        raise RuntimeError("O fechamento da venda está aberto; quantidade não alterada.")
    return sales[0]


def controls_for(sale):
    require_safe_layout(sale)
    controls = {control["role"]: control for control in sale["controls"]
                if control["role"] != "unknown"}
    required = ("quantity", "product_search", "sale_price", "line_total")
    if any(role not in controls for role in required):
        raise RuntimeError("Os campos da venda não estão mapeados; quantidade não alterada.")
    if not controls["quantity"]["enabled"]:
        raise RuntimeError("Campo Quantidade indisponível.")
    if any(control["class"] == "TArpaAdvDBGrid" and control["enabled"]
           for control in sale["controls"]):
        raise RuntimeError("Feche a lista de produtos antes de alterar a quantidade.")
    if controls["sale_price"].get("value", "").strip() not in {"0", "0,000", "0.000"} or \
       controls["line_total"].get("value", "").strip() not in {"0", "0,00", "0.00"}:
        raise RuntimeError("Preço ou total já preenchido; quantidade não alterada.")
    value = controls["quantity"].get("value", "").strip()
    if not valid_quantity_text(value):
        raise RuntimeError("A quantidade atual é inesperada; nada foi digitado.")
    return controls


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


def press_key(user32, vk, down):
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    event = INPUT(type=1, ki=KEYBDINPUT(vk, 0, 0 if down else 0x0002, 0, 0))
    array = (INPUT * 1)(event)
    if user32.SendInput(1, array, ctypes.sizeof(INPUT)) != 1:
        raise ctypes.WinError(ctypes.get_last_error())


def focus_quantity():
    snapshot = inspect()
    sale = sale_window(snapshot)
    controls = controls_for(sale)
    restored = restore()
    if not restored.get("activated"):
        raise RuntimeError("Não consegui trazer o PDV à frente; quantidade não alterada.")

    sale = sale_window(inspect())
    controls = controls_for(sale)
    quantity = controls["quantity"]
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    HWND = wintypes.HWND
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = HWND
    foreground = user32.GetForegroundWindow()
    if int(getattr(foreground, "value", foreground) or 0) != sale["hwnd"]:
        raise RuntimeError("A tela de venda não está em primeiro plano; quantidade não alterada.")

    left, top, right, bottom = quantity["rectangle"]
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = wintypes.BOOL
    user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.DWORD, ctypes.c_size_t]
    user32.mouse_event.restype = None
    if not user32.SetCursorPos((left + right) // 2, (top + bottom) // 2):
        raise ctypes.WinError(ctypes.get_last_error())
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.15)

    focused_sale = sale_window(inspect())
    focused_quantity = next((control for control in focused_sale["controls"]
                             if control["role"] == "quantity"), None)
    if focused_sale["hwnd"] != sale["hwnd"] or not focused_quantity or \
       focused_sale.get("focused_hwnd") != focused_quantity["hwnd"]:
        raise RuntimeError("O clique não confirmou foco em Quantidade; nenhuma tecla enviada.")
    return user32, focused_sale, focused_quantity


def clear_field(user32):
    # O PDV pode reter parte do valor mascarado após a primeira limpeza.
    # Repita cinco passagens completas de seleção + Backspace/Delete antes
    # de digitar a nova quantidade. Essas teclas atuam somente no campo focado.
    home_select_clear = (
        (0x24, True), (0x10, True), (0x23, True), (0x23, False),
        (0x10, False), (0x08, True), (0x08, False),
        (0x2E, True), (0x2E, False),
    )
    ctrl_a_clear = (
        (0x11, True), (0x41, True), (0x41, False), (0x11, False),
        (0x08, True), (0x08, False), (0x2E, True), (0x2E, False),
    )
    for _ in range(5):
        for vk, down in home_select_clear + ctrl_a_clear:
            press_key(user32, vk, down)
            time.sleep(0.025)
        time.sleep(0.1)
    time.sleep(0.15)
    return 5


def type_digits(user32, quantity=2):
    # TEditArpa aplica a máscara decimal e mostra as três casas no formato
    # 2,000. Digitar a vírgula como tecla física varia conforme o layout do
    # teclado; envie somente os dígitos inteiros e valide a formatação do PDV.
    for character in str(quantity):
        vk = 0x30 + int(character)
        press_key(user32, vk, True)
        press_key(user32, vk, False)
        time.sleep(0.03)


def finish_result(action, before_hwnd):
    after = inspect()
    sale = sale_window(after)
    if sale["hwnd"] != before_hwnd:
        raise RuntimeError("A tela de venda mudou durante a operação; pare para conferir.")
    fields = {control["role"]: control.get("value", "") for control in sale["controls"]
              if control["role"] in {"quantity", "product_search", "sale_price", "line_total"}}
    return {"ok": True, "action": action, "fields": fields,
            "enterSent": 0, "itemAdded": False, "paymentSent": False,
            "visualCheckRequired": True}


def clear_quantity():
    if sys.platform != "win32":
        raise RuntimeError("Esta ação só funciona no Windows.")
    user32, sale, quantity = focus_quantity()
    result_passes = clear_field(user32)
    result = finish_result("clear_quantity_only", sale["hwnd"])
    # A leitura Win32 do controle pode ficar diferente do texto renderizado.
    # O painel pede confirmação visual antes de permitir a digitação.
    result["cleared"] = True
    result["clearPasses"] = result_passes
    return result


def type_quantity(target_quantity=2):
    if sys.platform != "win32":
        raise RuntimeError("Esta ação só funciona no Windows.")
    if not isinstance(target_quantity, int) or target_quantity < 1 or target_quantity > 999999:
        raise RuntimeError("Quantidade inteira inválida; nada foi digitado.")
    user32, sale, _quantity_control = focus_quantity()
    # Apaga novamente no campo antes de digitar, mesmo após a conferência visual,
    # para impedir que 2,000 seja acrescentado ao conteúdo anterior.
    clear_passes = clear_field(user32)
    type_digits(user32, target_quantity)
    time.sleep(0.2)
    result = finish_result("clear_then_type_quantity", sale["hwnd"])
    if result["fields"].get("quantity", "").strip() not in (
            str(target_quantity), f"{target_quantity},000", f"{target_quantity}.000"):
        actual = result["fields"].get("quantity", "")
        raise RuntimeError(
            f"O campo Quantidade não confirmou {target_quantity},000 "
            f"(leitura do PDV: {actual!r}); pare para conferir.")
    result["typed"] = True
    result["targetQuantity"] = f"{target_quantity},000"
    result["clearPasses"] = clear_passes
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--clear-only", action="store_true")
    mode.add_argument("--type-only", action="store_true")
    args = parser.parse_args()
    try:
        output = clear_quantity() if args.clear_only else type_quantity()
        print(json.dumps(output, ensure_ascii=False))
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        sys.exit(1)
