"""Lança itens da proposta no PDV e para antes do fechamento/pagamento."""
import json
import sys
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from inspect_pdv_win32 import inspect, search_product
from pdv_geometry import require_safe_layout
from press_two_enter_win32 import press_two
from type_quantity_win32 import type_quantity, valid_quantity_text


def sale_window(snapshot):
    sales = [window for window in snapshot.get("windows", [])
             if window.get("title") == "PDV-FISCAL" and window.get("class") == "TFVendas"]
    if len(sales) != 1:
        raise RuntimeError("Não há uma única janela de venda acessível; nenhuma tecla enviada.")
    sale = sales[0]
    require_safe_layout(sale)
    if not sale.get("visible") or sale.get("minimized"):
        raise RuntimeError("A tela de venda está oculta ou minimizada; nenhuma tecla enviada.")
    if any("FECHAMENTO DE VENDA" in window.get("title", "").upper()
           for window in snapshot.get("windows", [])):
        raise RuntimeError("O fechamento está aberto; retorne à venda antes de iniciar.")
    return sale


def normalize_item(item):
    if not isinstance(item, dict):
        raise RuntimeError("A proposta contém um item inválido.")
    try:
        product_id = int(item["id"])
        quantity = int(item["quantity"])
        price = Decimal(str(item["price"]))
        subtotal = int(item["subtotal"])
    except (KeyError, TypeError, ValueError, OverflowError, InvalidOperation) as error:
        raise RuntimeError("Código, quantidade, preço ou subtotal inválido na proposta.") from error
    if product_id <= 0 or not 1 <= quantity <= 999999 or not price.is_finite() or price <= 0 or subtotal <= 0:
        raise RuntimeError("Há valor fora do intervalo aceito; nenhum item foi lançado.")
    expected_subtotal = int((price * quantity * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if subtotal != expected_subtotal:
        raise RuntimeError("O subtotal calculado não confere com preço e quantidade; nenhum item foi lançado.")
    description = str(item.get("description", "")).strip()
    if not description:
        raise RuntimeError("Descrição vazia na proposta; nenhum item foi lançado.")
    return {"id": product_id, "reference": str(item.get("reference") or ""),
            "description": description, "quantity": quantity,
            "price": float(price), "subtotal": subtotal}


def wait_for_empty_line(timeout=2.5):
    """Confirma estado vazio estável antes de iniciar o próximo item."""
    deadline = time.monotonic() + timeout
    stable_reads = 0
    observed = {}
    while time.monotonic() < deadline:
        sale = sale_window(inspect())
        observed = {control.get("role"): str(control.get("value") or "").strip()
                    for control in sale["controls"]}
        grids = sum(1 for control in sale["controls"]
                    if control.get("class") == "TArpaAdvDBGrid" and control.get("enabled"))
        empty = (observed.get("product_search", "") == "" and
                 observed.get("quantity") in ("1", "1,000", "1.000") and
                 observed.get("sale_price") in ("0", "0,000", "0.000") and
                 observed.get("line_total") in ("0", "0,00", "0.00") and grids == 0)
        stable_reads = stable_reads + 1 if empty else 0
        if stable_reads >= 2:
            return sale, observed
        time.sleep(0.2)
    raise RuntimeError("A linha do PDV não estabilizou após a inclusão; "
                       "nenhum item seguinte foi digitado. Estado observado: "
                       + json.dumps(observed, ensure_ascii=False))


def build_sale(items):
    if sys.platform != "win32":
        raise RuntimeError("Esta ação só funciona no Windows.")
    if not isinstance(items, list) or not items:
        raise RuntimeError("A proposta não contém itens.")
    items = [normalize_item(item) for item in items]
    if len({item["id"] for item in items}) != len(items):
        raise RuntimeError("A proposta contém códigos duplicados; nenhum item foi lançado.")

    before = inspect()
    sale = sale_window(before)
    fields = {control.get("role"): str(control.get("value") or "").strip()
              for control in sale["controls"]}
    if not valid_quantity_text(fields.get("quantity")) or \
       fields.get("sale_price") not in ("0", "0,000", "0.000") or \
       fields.get("line_total") not in ("0", "0,00", "0.00"):
        raise RuntimeError("A linha do PDV não está limpa; nada foi digitado.")
    if any(control.get("class") == "TArpaAdvDBGrid" and control.get("enabled")
           for control in sale["controls"]):
        raise RuntimeError("Há resultados de busca abertos; nada foi digitado.")

    added = []
    attempted_item = None
    stage = "before_quantity"
    try:
        for item in items:
            attempted_item = item
            # Depois de cada inclusão, espera duas leituras vazias consecutivas.
            # Isso evita tratar o redesenho assíncrono da linha como divergência.
            if added:
                current, current_fields = wait_for_empty_line()
            else:
                current = sale_window(inspect())
                current_fields = {control.get("role"): str(control.get("value") or "").strip()
                                  for control in current["controls"]}
                if not valid_quantity_text(current_fields.get("quantity")) or \
                   current_fields.get("sale_price") not in ("0", "0,000", "0.000") or \
                   current_fields.get("line_total") not in ("0", "0,00", "0.00"):
                    raise RuntimeError("A linha do PDV mudou antes do primeiro item; nada foi digitado.")

            stage = "quantity"
            quantity_result = type_quantity(item["quantity"])
            if not quantity_result.get("typed") or quantity_result.get("targetQuantity") != f"{item['quantity']},000":
                raise RuntimeError("O PDV não confirmou a quantidade; busca não iniciada.")

            stage = "product_search"
            search_result = search_product(str(item["id"]))
            if search_result.get("searchedQuery") != str(item["id"]) or \
               search_result.get("selected") or search_result.get("itemAdded"):
                raise RuntimeError("O código interno não foi confirmado no campo Produto.")

            stage = "add_item"
            added_result = press_two(True, item)
            if not added_result.get("itemAdded") or added_result.get("paymentSent"):
                raise RuntimeError("O PDV não confirmou a inclusão deste item; sequência interrompida.")
            added.append({"id": item["id"], "description": item["description"],
                          "quantity": item["quantity"], "price": item["price"],
                          "subtotal": item["subtotal"], "enterSent": added_result.get("enterSent")})
            attempted_item = None
            stage = "before_quantity"
            time.sleep(0.15)

        final_sale = sale_window(inspect())
        final_fields = {control.get("role"): str(control.get("value") or "").strip()
                        for control in final_sale["controls"]}
        if final_fields.get("product_search") or \
           final_fields.get("quantity") not in ("1", "1,000", "1.000") or \
           final_fields.get("sale_price") not in ("0", "0,000", "0.000") or \
           final_fields.get("line_total") not in ("0", "0,00", "0.00"):
            raise RuntimeError("Os itens foram adicionados, mas a linha do PDV não voltou ao estado vazio.")
        return {"ok": True, "addedItems": added,
                "expectedSubtotal": sum(item["subtotal"] for item in items),
                "finalFields": final_fields, "f6Sent": False,
                "paymentSent": False, "nfcIssued": False, "stage": "complete"}
    except Exception as error:
        return {"ok": False, "addedItems": added,
                "expectedSubtotalAdded": sum(item["subtotal"] for item in added),
                "stage": stage,
                "quantityMayHaveChanged": stage == "quantity",
                "itemMayHaveBeenAdded": stage == "add_item",
                "uncertainItem": attempted_item if stage == "add_item" else None,
                "error": str(error), "f6Sent": False,
                "paymentSent": False, "nfcIssued": False,
                "mustInspectBeforeRetry": True}


if __name__ == "__main__":
    try:
        payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else json.loads(sys.stdin.read())
        result = build_sale(payload.get("items"))
        print(json.dumps(result, ensure_ascii=False))
        if not result.get("ok"):
            sys.exit(2)
    except Exception as error:
        print(json.dumps({"ok": False, "addedItems": [], "error": str(error),
                          "f6Sent": False, "paymentSent": False,
                          "nfcIssued": False, "mustInspectBeforeRetry": True},
                         ensure_ascii=False))
        sys.exit(1)
