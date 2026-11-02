"""Confirma o código direto no campo Produto com até dois Enter, sem pagamento."""
import ctypes
import json
import sys
import time
from ctypes import wintypes
from decimal import Decimal

from inspect_pdv_win32 import inspect
from pdv_geometry import require_safe_layout
from pdv_config import is_sale_window


EXPECTED_DESCRIPTION = "VESTIDO FEMININO INFANTIL (GR 4/8) - 251687"
FACTORY_REFERENCE = "12501687"
PRODUCT_CODE = "7306"
SELECTED_PRODUCT_VALUES = {PRODUCT_CODE, FACTORY_REFERENCE, EXPECTED_DESCRIPTION}
DEFAULT_ITEM = {"id": 7306, "reference": FACTORY_REFERENCE,
                "description": EXPECTED_DESCRIPTION, "quantity": 2,
                "price": 50, "subtotal": 10000}


def read_sale():
    snapshot = inspect()
    sales = [w for w in snapshot["windows"] if is_sale_window(w)]
    if len(sales) != 1:
        raise RuntimeError("A janela de venda do PDV deixou de estar única; sequência interrompida.")
    sale = sales[0]
    require_safe_layout(sale)
    if sale.get("visible") is False or sale.get("minimized") is True:
        raise RuntimeError("A janela do PDV está oculta ou minimizada; nenhum Enter enviado.")
    fields = {c["role"]: (c.get("value") or "") for c in sale["controls"]
              if c["role"] in {"quantity", "product_search", "sale_price", "line_total"}}
    for role in ("quantity", "product_search", "sale_price", "line_total"):
        matching = [control for control in sale["controls"] if control["role"] == role]
        if len(matching) != 1 or not matching[0]["enabled"] or not matching[0]["hwnd"]:
            raise RuntimeError(f"Campo {role} não está único e habilitado; nenhum Enter enviado.")
    grid_count = sum(1 for c in sale["controls"]
                     if c["class"] == "TArpaAdvDBGrid" and c["enabled"])
    return sale, fields, grid_count


def press_two(quantity_visually_confirmed=False, item=None):
    if sys.platform != "win32":
        raise RuntimeError("Esta ação só funciona no Windows.")
    if not quantity_visually_confirmed:
        raise RuntimeError("A operação não foi autorizada; nenhum Enter enviado.")
    item = item or DEFAULT_ITEM
    try:
        product_code = str(int(item["id"]))
        quantity_target = int(item["quantity"])
        expected_price = f"{Decimal(str(item['price'])):.3f}".replace(".", ",")
        expected_total = f"{Decimal(int(item['subtotal'])) / Decimal(100):.2f}".replace(".", ",")
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise RuntimeError("Dados do item inválidos; nenhum Enter enviado.") from error
    sale, fields, grid_count = read_sale()
    field_text = fields.get("product_search", "").strip()
    if field_text != product_code:
        raise RuntimeError("O campo Produto não contém o código interno esperado; nenhum Enter enviado.")
    if fields.get("quantity", "").strip() not in (
            str(quantity_target), f"{quantity_target},000", f"{quantity_target}.000"):
        raise RuntimeError("A quantidade não confere com a proposta; nenhum Enter enviado.")
    if fields.get("sale_price", "").strip() not in ("0", "0,000", "0.000") or \
       fields.get("line_total", "").strip() not in ("0", "0,00", "0.00"):
        raise RuntimeError("Preço ou total já está preenchido; nenhum Enter enviado.")
    if grid_count:
        raise RuntimeError("Há uma lista aberta no PDV; nenhum Enter enviado para evitar selecionar outra linha.")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    HWND = wintypes.HWND
    product_control = next(c for c in sale["controls"] if c["role"] == "product_search")
    product_hwnd = HWND(product_control["hwnd"])
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = HWND
    foreground = user32.GetForegroundWindow()
    if int(getattr(foreground, "value", foreground) or 0) != sale["hwnd"] or \
       sale.get("focused_hwnd") != product_control["hwnd"]:
        raise RuntimeError("O foco não está no campo Produto do PDV; nenhum Enter enviado.")

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

    def send_enter():
        events = (INPUT * 2)(
            INPUT(type=1, ki=KEYBDINPUT(0x0D, 0, 0, 0, 0)),
            INPUT(type=1, ki=KEYBDINPUT(0x0D, 0, 0x0002, 0, 0)))
        if user32.SendInput(2, events, ctypes.sizeof(INPUT)) != 2:
            raise ctypes.WinError(ctypes.get_last_error())

    def line_reset(observed, grids):
        value = lambda role: str(observed.get(role) or "").strip()
        return (value("product_search") == "" and
                value("quantity") in ("1", "1,000", "1.000") and
                value("sale_price") in ("0", "0,000", "0.000") and
                value("line_total") in ("0", "0,00", "0.00") and
                grids == 0)

    def selected_state(observed):
        value = lambda role: str(observed.get(role) or "").strip()
        text = value("product_search").upper()
        identity = (product_code, str(item.get("reference") or "").strip(),
                    str(item.get("description") or "").strip())
        return (any(value and value.upper() in text for value in identity) and
                value("quantity") in (
                    str(quantity_target), f"{quantity_target},000", f"{quantity_target}.000") and
                value("sale_price") in
                    (expected_price, expected_price.replace(",", ".")) and
                value("line_total") in
                    (expected_total, expected_total.replace(",", ".")))

    sent = 0
    after = fields
    grids_after = grid_count
    item_added = False
    for index in range(2):
        send_enter()
        sent += 1
        time.sleep(0.3)
        sale_after, after, grids_after = read_sale()
        if line_reset(after, grids_after):
            item_added = True
            break
        value = lambda role: str(after.get(role) or "").strip()
        if grids_after or (not selected_state(after) and not (
                index == 0 and value("product_search") == product_code and
                value("quantity") in (
                    str(quantity_target), f"{quantity_target},000", f"{quantity_target}.000") and
                value("sale_price") in ("0", "0,000", "0.000") and
                value("line_total") in ("0", "0,00", "0.00"))):
            raise RuntimeError("O PDV não confirmou seleção ou inclusão após Enter; sequência interrompida.")
        if index == 0:
            # Só envia o segundo Enter se o primeiro manteve exatamente o código
            # e a linha inicial, ou confirmou preço/subtotal do item esperado.
            foreground = user32.GetForegroundWindow()
            if int(getattr(foreground, "value", foreground) or 0) != sale["hwnd"] or \
               sale_after.get("focused_hwnd") != product_control["hwnd"]:
                raise RuntimeError("Após o primeiro Enter o foco mudou; segundo Enter cancelado.")
            continue
    if not item_added:
        raise RuntimeError("Dois Enter foram enviados, mas o PDV não confirmou a inclusão da linha.")

    return {"ok": True, "enterSent": sent, "paymentSent": False,
            "fields": after, "resultGridCount": grids_after,
            "itemAdded": item_added,
            "message": "Sequência interrompida antes de qualquer tecla de pagamento."}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--quantity-visually-confirmed", action="store_true")
    parser.add_argument("--item-json")
    args = parser.parse_args()
    try:
        item = json.loads(args.item_json) if args.item_json else DEFAULT_ITEM
        print(json.dumps(press_two(args.quantity_visually_confirmed, item), ensure_ascii=False))
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        sys.exit(1)
