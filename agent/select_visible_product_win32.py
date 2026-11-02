"""Clica na variante conferida na lista Arpa; não envia Enter."""
import ctypes
import json
import sys
import time
from decimal import Decimal
from ctypes import wintypes

from inspect_pdv_win32 import inspect
from pdv_geometry import require_safe_layout
from pdv_config import is_sale_window


DEFAULT_ITEM = {"id": 7306, "reference": "12501687",
                "description": "VESTIDO FEMININO INFANTIL (GR 4/8) - 251687",
                "quantity": 2, "price": 50, "subtotal": 10000}


def select_target(item=None):
    if sys.platform != "win32":
        raise RuntimeError("Esta ação só funciona no Windows.")
    item = item or DEFAULT_ITEM
    try:
        product_code = str(int(item["id"]))
        quantity_target = int(item["quantity"])
        expected_price = f"{Decimal(str(item['price'])):.3f}".replace(".", ",")
        expected_total = f"{Decimal(int(item['subtotal'])) / Decimal(100):.2f}".replace(".", ",")
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise RuntimeError("Dados do produto inválidos; nenhum resultado foi clicado.") from error
    if quantity_target < 1 or not item.get("description"):
        raise RuntimeError("Quantidade ou descrição do produto inválida; nada foi clicado.")
    references = {product_code, str(item.get("reference") or "").strip(),
                  str(item["description"]).strip()}
    snapshot = inspect()
    sales = [w for w in snapshot["windows"] if is_sale_window(w)]
    if len(sales) != 1:
        raise RuntimeError("É necessário exatamente uma janela PDV-FISCAL visível.")
    sale = sales[0]
    require_safe_layout(sale)
    controls = sale["controls"]
    by_role = {c["role"]: c for c in controls if c["role"] != "unknown"}
    search = by_role.get("product_search", {})
    quantity = by_role.get("quantity", {})
    price = by_role.get("sale_price", {})
    total = by_role.get("line_total", {})

    if search.get("value", "").strip().casefold() != str(item["description"]).strip().casefold():
        raise RuntimeError("A descrição pesquisada não corresponde ao produto da proposta.")
    if quantity.get("value", "").strip() not in (
            str(quantity_target), f"{quantity_target},000", f"{quantity_target}.000"):
        raise RuntimeError("A quantidade no PDV não corresponde à proposta.")
    if price.get("value", "").strip() not in ("0", "0,000", "0.000"):
        raise RuntimeError("O preço já está preenchido; seleção cancelada.")
    if total.get("value", "").strip() not in ("0", "0,00", "0.00"):
        raise RuntimeError("O total já está preenchido; seleção cancelada.")

    grids = [c for c in controls
             if c["class"] == "TArpaAdvDBGrid" and c["enabled"]]
    if len(grids) != 1:
        raise RuntimeError("Deixe aberta a lista filtrada por 251687; nada foi clicado.")
    grid = grids[0]
    left, top, right, bottom = grid["rectangle"]
    sale_left, sale_top, sale_right, sale_bottom = sale["rectangle"]
    if (right - left < 300 or bottom - top < 80 or left < sale_left or top < sale_top or
            right > sale_right or bottom > sale_bottom):
        raise RuntimeError("A geometria da grade mudou; nada foi clicado.")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    HWND = wintypes.HWND
    user32.GetForegroundWindow.restype = HWND
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = wintypes.BOOL
    user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.DWORD, ctypes.c_size_t]
    user32.mouse_event.restype = None
    if int(user32.GetForegroundWindow() or 0) != sale["hwnd"]:
        raise RuntimeError("Traga o PDV para primeiro plano; nada foi clicado.")

    # A busca pelo código interno é única; clicar na primeira linha usa a grade
    # atual e não pixels absolutos. O clique só seleciona, não inclui o item.
    click_x = left + int((right - left) * 0.24)
    click_y = top + int((bottom - top) * 0.12)
    if not user32.SetCursorPos(click_x, click_y):
        raise ctypes.WinError(ctypes.get_last_error())
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.3)

    after = inspect()
    sales_after = [w for w in after["windows"] if is_sale_window(w)]
    fields = {c["role"]: c.get("value", "") for w in sales_after
              for c in w["controls"]
              if c["role"] in {"quantity", "product_search", "sale_price", "line_total"}}
    product_after = fields.get("product_search", "").strip().upper()
    if not any(reference and reference.upper() in product_after for reference in references):
        raise RuntimeError("O produto selecionado não confirmou o código/referência esperado; pare para conferir.")
    if fields.get("quantity", "").strip() not in (
            str(quantity_target), f"{quantity_target},000", f"{quantity_target}.000"):
        raise RuntimeError("A quantidade mudou após o clique; pare para revisar o PDV.")
    if fields.get("sale_price", "").strip() not in (expected_price, expected_price.replace(",", ".")):
        raise RuntimeError("O preço unitário não confirmou a proposta; nenhum Enter enviado.")
    if fields.get("line_total", "").strip() not in (expected_total, expected_total.replace(",", ".")):
        raise RuntimeError("O subtotal da linha não confirmou a proposta; nenhum Enter enviado.")
    return {"ok": True, "action": "click_result_row_only",
            "expectedProduct": item["description"], "productId": int(item["id"]),
            "fields": fields,
            "enterSent": 0, "itemAdded": False, "paymentSent": False}


if __name__ == "__main__":
    try:
        payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ITEM
        print(json.dumps(select_target(payload), ensure_ascii=False))
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        sys.exit(1)
