"""Prepara 2 unidades e envia um único Enter; nunca envia tecla de pagamento."""
import ctypes
import json
import sys
import time
from ctypes import wintypes

from inspect_pdv_win32 import inspect

EXPECTED = "VESTIDO FEMININO INFANTIL (GR 4/8) - 251687"
ALLOWED = {"7306", "12501687", EXPECTED}


def read_sale():
    snapshot = inspect()
    sales = [w for w in snapshot["windows"]
             if w["title"] == "PDV-FISCAL" and w["class"] == "TFVendas"]
    if len(sales) != 1:
        raise RuntimeError("A janela PDV-FISCAL não está única; nenhum Enter enviado.")
    sale = sales[0]
    fields = {c["role"]: c.get("value", "") for c in sale["controls"]
              if c["role"] in {"quantity", "product_search", "sale_price", "line_total"}}
    grids = [c for c in sale["controls"]
             if c["class"] == "TArpaAdvDBGrid" and c["enabled"]]
    return sale, fields, grids


def one_enter():
    if sys.platform != "win32":
        raise RuntimeError("Esta ação só funciona no Windows.")
    sale, fields, grids = read_sale()
    if fields.get("product_search", "").strip() not in ALLOWED:
        raise RuntimeError("O código 7306 não está confirmado no campo Produto; nenhum Enter enviado.")
    if fields.get("quantity", "").strip() not in {"1", "1,000", "2", "2,000", "2.000"}:
        raise RuntimeError("Quantidade inesperada; nenhum Enter enviado.")
    if fields.get("sale_price", "").strip() not in {"0", "0,000", "0.000"} or \
       fields.get("line_total", "").strip() not in {"0", "0,00", "0.00"}:
        raise RuntimeError("Preço/total não zerados; nenhum Enter enviado.")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    HWND = wintypes.HWND
    user32.SetWindowTextW.argtypes = [HWND, wintypes.LPCWSTR]
    user32.SetWindowTextW.restype = wintypes.BOOL
    user32.PostMessageW.argtypes = [HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
    user32.PostMessageW.restype = wintypes.BOOL
    controls = {c["role"]: c for c in sale["controls"]}
    if fields["quantity"].strip() not in {"2", "2,000", "2.000"}:
        quantity = HWND(controls["quantity"]["hwnd"])
        if not user32.SetWindowTextW(quantity, "2,000"):
            raise ctypes.WinError(ctypes.get_last_error())
        time.sleep(0.15)
        sale, fields, grids = read_sale()
        if fields.get("quantity") != "2,000":
            raise RuntimeError("Quantidade 2 não foi confirmada; nenhum Enter enviado.")

    product = HWND(controls["product_search"]["hwnd"])
    down = 1 | (0x1C << 16)
    up = down | (1 << 30) | (1 << 31)
    if not user32.PostMessageW(product, 0x0100, 0x0D, down):
        raise ctypes.WinError(ctypes.get_last_error())
    if not user32.PostMessageW(product, 0x0101, 0x0D, up):
        raise ctypes.WinError(ctypes.get_last_error())
    time.sleep(0.5)
    _, after, grids_after = read_sale()
    return {"ok": True, "enterSent": 1, "paymentSent": False,
            "fields": after, "resultGridCount": len(grids_after),
            "message": "Um Enter foi enviado; nenhuma segunda tecla ou pagamento foi enviado."}


if __name__ == "__main__":
    try:
        print(json.dumps(one_enter(), ensure_ascii=False))
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        sys.exit(1)
