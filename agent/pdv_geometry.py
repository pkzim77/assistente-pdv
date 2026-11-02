"""Geometry checks shared by read-only inspection and guarded PDV actions."""

SALE_FIELDS = ("quantity", "product_search", "sale_price", "line_total")
LAYOUT_ANCHORS = ("pdv_status_display", "sale_items_area")


def rectangle_inside(rectangle, bounds):
    return bool(
        isinstance(rectangle, list) and len(rectangle) == 4
        and isinstance(bounds, list) and len(bounds) == 4
        and rectangle[0] >= bounds[0] and rectangle[1] >= bounds[1]
        and rectangle[2] <= bounds[2] and rectangle[3] <= bounds[3]
        and rectangle[2] > rectangle[0] and rectangle[3] > rectangle[1]
    )


def layout_diagnostics(sale):
    bounds = sale.get("rectangle")
    controls = sale.get("controls", [])
    counts = {role: sum(control.get("role") == role for control in controls)
              for role in SALE_FIELDS}
    missing = [role for role, count in counts.items() if count != 1]
    disabled = [role for role in SALE_FIELDS if counts[role] == 1 and not next(
        control for control in controls if control.get("role") == role
    ).get("enabled")]
    clipped = [role for role in SALE_FIELDS if counts[role] == 1 and not rectangle_inside(
        next(control for control in controls if control.get("role") == role).get("rectangle"), bounds
    )]
    # Esses elementos ajudam a detectar uma janela que foi reduzida ou movida
    # entre monitores sem que o próprio PDV refaça o layout dos painéis.
    for role in LAYOUT_ANCHORS:
        matches = [control for control in controls if control.get("role") == role]
        if len(matches) == 1 and not rectangle_inside(matches[0].get("rectangle"), bounds):
            clipped.append(role)
    width = bounds[2] - bounds[0] if bounds and len(bounds) == 4 else 0
    height = bounds[3] - bounds[1] if bounds and len(bounds) == 4 else 0
    return {
        "windowSize": {"width": width, "height": height},
        "roleCounts": counts,
        "missingFields": missing,
        "disabledFields": disabled,
        "clippedFields": clipped,
        "layoutFits": not (missing or disabled or clipped),
    }


def require_safe_layout(sale):
    diagnostic = layout_diagnostics(sale)
    if diagnostic["missingFields"]:
        raise RuntimeError("Mapa incompleto ou ambíguo: "
                           + ", ".join(diagnostic["missingFields"]) + ". Nenhuma entrada enviada.")
    if diagnostic["disabledFields"]:
        raise RuntimeError("Campos desabilitados: "
                           + ", ".join(diagnostic["disabledFields"]) + ". Nenhuma entrada enviada.")
    if diagnostic["clippedFields"]:
        raise RuntimeError("Layout do PDV excede a janela atual ("
                           + str(diagnostic["windowSize"]["width"]) + "×"
                           + str(diagnostic["windowSize"]["height"]) + "); controles fora da tela: "
                           + ", ".join(diagnostic["clippedFields"])
                           + ". Feche e reabra o PDV neste monitor para refazer o layout. Nenhuma entrada enviada.")
    return diagnostic
