"""Inspeciona o PDV e, opcionalmente, digita uma busca sem selecionar itens."""
import argparse
import ctypes
import json
import sys
import struct
import time
from ctypes import wintypes
from pathlib import Path
from pdv_config import (PDV_PROCESS_NAME, PDV_WINDOW_TITLE, PDV_WINDOW_CLASS,
                        relevant_window_titles, is_sale_window)


def capture_window_bmp(hwnd_value, output_path):
    """Captura uma janela em segundo plano via PrintWindow para diagnóstico local."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    HWND = wintypes.HWND
    HDC = wintypes.HDC
    HBITMAP = wintypes.HBITMAP

    class RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                    ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]

    class RGBQUAD(ctypes.Structure):
        _fields_ = [("rgbBlue", ctypes.c_ubyte), ("rgbGreen", ctypes.c_ubyte),
                    ("rgbRed", ctypes.c_ubyte), ("rgbReserved", ctypes.c_ubyte)]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", RGBQUAD * 1)]

    hwnd = HWND(hwnd_value)
    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise ctypes.WinError(ctypes.get_last_error())
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if width <= 0 or height <= 0 or width * height > 20_000_000:
        raise RuntimeError("Dimensões da janela inválidas para captura.")

    user32.GetDC.argtypes = [HWND]
    user32.GetDC.restype = HDC
    user32.ReleaseDC.argtypes = [HWND, HDC]
    user32.ReleaseDC.restype = ctypes.c_int
    user32.PrintWindow.argtypes = [HWND, HDC, wintypes.UINT]
    user32.PrintWindow.restype = wintypes.BOOL
    gdi32.CreateCompatibleDC.argtypes = [HDC]
    gdi32.CreateCompatibleDC.restype = HDC
    gdi32.CreateCompatibleBitmap.argtypes = [HDC, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = HBITMAP
    gdi32.SelectObject.argtypes = [HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.GetDIBits.argtypes = [HDC, HBITMAP, wintypes.UINT, wintypes.UINT,
                                ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT]
    gdi32.GetDIBits.restype = ctypes.c_int
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.DeleteDC.argtypes = [HDC]
    gdi32.DeleteDC.restype = wintypes.BOOL

    screen_dc = user32.GetDC(hwnd)
    memory_dc = gdi32.CreateCompatibleDC(screen_dc)
    bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    old_bitmap = gdi32.SelectObject(memory_dc, bitmap)
    try:
        if not user32.PrintWindow(hwnd, memory_dc, 2):
            raise RuntimeError("PrintWindow não conseguiu capturar a janela.")
        info = BITMAPINFO()
        info.bmiHeader = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), width, -height,
                                          1, 32, 0, width * height * 4, 0, 0, 0, 0)
        pixels = ctypes.create_string_buffer(width * height * 4)
        rows = gdi32.GetDIBits(memory_dc, bitmap, 0, height, pixels,
                               ctypes.byref(info), 0)
        if rows != height:
            raise RuntimeError("Não foi possível ler os pixels da janela.")
        header = struct.pack("<2sIHHI", b"BM", 54 + len(pixels), 0, 0, 54)
        dib = struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32, 0,
                          len(pixels), 0, 0, 0, 0)
        Path(output_path).write_bytes(header + dib + pixels.raw)
    finally:
        gdi32.SelectObject(memory_dc, old_bitmap)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, screen_dc)


def inspect():
    if sys.platform != "win32":
        raise RuntimeError("Este inspetor só funciona no Windows.")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    HWND = wintypes.HWND
    LPARAM = wintypes.LPARAM
    BOOL = wintypes.BOOL
    DWORD = wintypes.DWORD

    class RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                    ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    class GUITHREADINFO(ctypes.Structure):
        _fields_ = [("cbSize", DWORD), ("flags", DWORD), ("hwndActive", HWND),
                    ("hwndFocus", HWND), ("hwndCapture", HWND),
                    ("hwndMenuOwner", HWND), ("hwndMoveSize", HWND),
                    ("hwndCaret", HWND), ("rcCaret", RECT)]

    enum_proc = ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)
    user32.EnumWindows.argtypes = [enum_proc, LPARAM]
    user32.EnumWindows.restype = BOOL
    user32.EnumChildWindows.argtypes = [HWND, enum_proc, LPARAM]
    user32.EnumChildWindows.restype = BOOL
    user32.IsWindowVisible.argtypes = [HWND]
    user32.IsWindowVisible.restype = BOOL
    user32.IsIconic.argtypes = [HWND]
    user32.IsIconic.restype = BOOL
    user32.IsWindowEnabled.argtypes = [HWND]
    user32.IsWindowEnabled.restype = BOOL
    user32.GetWindowTextLengthW.argtypes = [HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    # GetWindowTextW pode devolver texto em cache para controles de outro
    # processo. O PDV roda em processo separado; WM_GETTEXT pede o conteúdo
    # atual ao próprio controle, com timeout para não travar a inspeção.
    user32.SendMessageTimeoutW.argtypes = [HWND, wintypes.UINT, ctypes.c_size_t,
                                           ctypes.c_ssize_t, wintypes.UINT,
                                           wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
    user32.SendMessageTimeoutW.restype = ctypes.c_ssize_t
    user32.GetClassNameW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindowRect.argtypes = [HWND, ctypes.POINTER(RECT)]
    user32.GetWindowRect.restype = BOOL
    user32.GetDlgCtrlID.argtypes = [HWND]
    user32.GetDlgCtrlID.restype = ctypes.c_int
    user32.SetForegroundWindow.argtypes = [HWND]
    user32.SetForegroundWindow.restype = BOOL
    user32.SetFocus.argtypes = [HWND]
    user32.SetFocus.restype = HWND
    user32.SetWindowTextW.argtypes = [HWND, wintypes.LPCWSTR]
    user32.SetWindowTextW.restype = BOOL
    user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(DWORD)]
    user32.GetWindowThreadProcessId.restype = DWORD
    user32.GetForegroundWindow.restype = HWND
    user32.GetGUIThreadInfo.argtypes = [DWORD, ctypes.POINTER(GUITHREADINFO)]
    user32.GetGUIThreadInfo.restype = BOOL

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [DWORD, BOOL, DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, DWORD,
                                                     wintypes.LPWSTR,
                                                     ctypes.POINTER(DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = BOOL

    def text(hwnd):
        length = min(user32.GetWindowTextLengthW(hwnd), 1024)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        return buffer.value

    def control_value(hwnd):
        result = ctypes.c_size_t()
        if not user32.SendMessageTimeoutW(hwnd, 0x000E, 0, 0, 0x0002, 500,
                                          ctypes.byref(result)):
            return None
        length = min(int(result.value), 1024)
        buffer = ctypes.create_unicode_buffer(length + 1)
        if not user32.SendMessageTimeoutW(hwnd, 0x000D, len(buffer),
                                          ctypes.cast(buffer, ctypes.c_void_p).value,
                                          0x0002, 500, ctypes.byref(result)):
            return None
        return buffer.value

    def class_name(hwnd):
        buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buffer, len(buffer))
        return buffer.value

    def rectangle(hwnd):
        rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        return [rect.left, rect.top, rect.right, rect.bottom]

    def contained(inner, outer):
        return bool(inner and outer and inner[0] >= outer[0] and inner[1] >= outer[1]
                    and inner[2] <= outer[2] and inner[3] <= outer[3])

    def is_pdv_process(process_id):
        process = kernel32.OpenProcess(0x1000, False, process_id)  # QUERY_LIMITED_INFORMATION
        if not process:
            return False
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = DWORD(len(buffer))
            if not kernel32.QueryFullProcessImageNameW(process, 0, buffer,
                                                        ctypes.byref(size)):
                return False
            return Path(buffer.value).name.casefold() == PDV_PROCESS_NAME.casefold()
        finally:
            kernel32.CloseHandle(process)

    def control_role(kind, rect, parent_rect):
        if not rect or not parent_rect:
            return "unknown"
        parent_width = parent_rect[2] - parent_rect[0]
        parent_height = parent_rect[3] - parent_rect[1]
        if parent_width <= 0 or parent_height <= 0:
            return "unknown"
        left, top, right, bottom = rect
        center_x = ((left + right) / 2 - parent_rect[0]) / parent_width
        center_y = ((top + bottom) / 2 - parent_rect[1]) / parent_height
        # O campo Produto é identificado pela classe nativa e pela coluna esquerda.
        # A posição vertical varia entre resoluções e não é usada como identidade.
        if kind == "TArpaEditConsultaDados" and center_x < 0.30:
            return "product_search"
        if kind == "TEditArpa" and center_x > 0.25 and center_y < 0.16:
            return "pdv_status_display"
        if kind == "TAdvSmoothPanel" and center_x > 0.25 and 0.16 < center_y < 0.90:
            return "sale_items_area"
        return "unknown"

    expected = tuple(title.upper() for title in relevant_window_titles())
    windows = []

    @enum_proc
    def enum_windows(hwnd, _):
        pid = DWORD()
        thread_id = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        title = text(hwnd)
        known_title = any(label in title.upper() for label in expected)
        if not known_title and (not pid.value or not is_pdv_process(pid.value)):
            return True

        children = []
        parent_rect = rectangle(hwnd)

        @enum_proc
        def enum_children(child, _):
            if user32.IsWindowVisible(child):
                kind = class_name(child)
                child_rect = rectangle(child)
                # Só lemos os quatro campos de venda da tela TFVendas; campos de
                # login, senha e qualquer outro Edit permanecem omitidos.
                is_edit = "EDIT" in kind.upper()
                role = control_role(kind, child_rect, parent_rect)
                control = {
                    "hwnd": int(child),
                    "class": kind,
                    "role": role,
                    "label": "" if is_edit else text(child),
                    "rectangle": child_rect,
                    "within_window": contained(child_rect, parent_rect),
                    "control_id": user32.GetDlgCtrlID(child),
                    "enabled": bool(user32.IsWindowEnabled(child)),
                }
                if role in {"quantity", "product_search", "sale_price", "line_total"}:
                    control["value"] = control_value(child)
                children.append(control)
            return True

        user32.EnumChildWindows(hwnd, enum_children, 0)
        # Os três TEditArpa habilitados na coluna esquerda são, em ordem
        # vertical, Quantidade, Preço de venda e Total. Ordenar os controles
        # visíveis evita depender de pixels ou da resolução usada na abertura.
        if class_name(hwnd) == PDV_WINDOW_CLASS and title == PDV_WINDOW_TITLE and parent_rect:
            parent_width = parent_rect[2] - parent_rect[0]
            left_edits = []
            if parent_width > 0:
                for control in children:
                    rect = control["rectangle"]
                    if control["class"] == "TEditArpa" and control["enabled"] and rect:
                        center_x = ((rect[0] + rect[2]) / 2 - parent_rect[0]) / parent_width
                        if center_x < 0.30:
                            left_edits.append(control)
            left_edits.sort(key=lambda control: control["rectangle"][1])
            if len(left_edits) == 3:
                for control, role in zip(left_edits,
                                         ("quantity", "sale_price", "line_total")):
                    control["role"] = role
                    control["value"] = control_value(HWND(control["hwnd"]))
        foreground = user32.GetForegroundWindow()
        gui_info = GUITHREADINFO()
        gui_info.cbSize = ctypes.sizeof(GUITHREADINFO)
        user32.GetGUIThreadInfo(thread_id, ctypes.byref(gui_info))
        focus_hwnd = int(gui_info.hwndFocus or 0)
        focus_role = next((c["role"] for c in children if c["hwnd"] == focus_hwnd), "unknown")
        windows.append({
            "hwnd": int(hwnd),
            "title": title,
            "class": class_name(hwnd),
            "process_id": pid.value,
            "visible": bool(user32.IsWindowVisible(hwnd)),
            "minimized": bool(user32.IsIconic(hwnd)),
            "is_foreground": foreground == hwnd,
            "focused_hwnd": focus_hwnd,
            "focused_role": focus_role,
            "rectangle": rectangle(hwnd),
            "controls": children,
        })
        return True

    user32.EnumWindows(enum_windows, 0)
    capture_request = Path(__file__).with_name("capture-pdv.request")
    if capture_request.exists() and windows:
        capture_path = Path(__file__).with_name("pdv-background-capture.bmp")
        try:
            requested_title = capture_request.read_text(encoding="utf-8").strip().upper()
            target = next((w for w in windows if requested_title in w["title"].upper()), windows[0])
            capture_window_bmp(target["hwnd"], capture_path)
        finally:
            capture_request.unlink(missing_ok=True)
    return {"method": "Win32 API (ctypes), somente leitura", "windows": windows}


def search_product(query):
    """Digita o código interno no campo Produto, sem Enter nem seleção."""
    if not isinstance(query, str) or not query.strip() or len(query) > 12 or \
       any(ord(c) < 32 for c in query):
        raise ValueError("Texto de busca inválido.")
    query = query.strip()
    if not query.isdigit():
        raise ValueError("Esta etapa aceita somente o código interno numérico.")
    search_text = query
    from restore_pdv_win32 import restore as restore_pdv_window
    restore_pdv_window()
    before = None
    sales = []
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        before = inspect()
        sales = [window for window in before["windows"] if is_sale_window(window)]
        fields_ready = (len(sales) == 1 and
                        sum(1 for c in sales[0]["controls"] if c["role"] == "product_search") == 1)
        if fields_ready:
            break
        time.sleep(0.2)
    if len(sales) != 1:
        raise RuntimeError("É necessário exatamente uma janela PDV-FISCAL visível.")
    from pdv_geometry import require_safe_layout
    require_safe_layout(sales[0])
    if sales[0].get("visible") is False or sales[0].get("minimized") is True:
        raise RuntimeError("A janela do PDV está oculta ou minimizada; busca não digitada.")
    controls = sales[0]["controls"]
    search = [control for control in controls if control["role"] == "product_search"]
    values = {control["role"]: control.get("value", "") for control in controls}
    for role in ("quantity", "product_search", "sale_price", "line_total"):
        matching = [control for control in controls if control["role"] == role]
        if len(matching) != 1 or not matching[0]["enabled"] or not matching[0]["hwnd"]:
            raise RuntimeError(f"Campo {role} não está único e habilitado; busca não digitada.")
    existing_grid_count = sum(1 for control in controls
                              if control["class"] == "TArpaAdvDBGrid" and control["enabled"])
    if existing_grid_count:
        raise RuntimeError("A lista de resultados já está aberta; busca não substituída.")
    quantity_text = values.get("quantity", "").strip()
    quantity_digits = quantity_text.replace(",000", "").replace(".000", "")
    if not quantity_digits.isdigit() or not 1 <= int(quantity_digits) <= 999999 or \
       quantity_text not in (quantity_digits, quantity_digits + ",000", quantity_digits + ".000"):
        raise RuntimeError("A quantidade do PDV foi alterada ou não é inteira; busca cancelada.")
    if values.get("sale_price", "").strip() not in ("0", "0,000", "0.000"):
        raise RuntimeError("O PDV já exibe um preço; busca cancelada para preservar o cupom.")
    if values.get("line_total", "").strip() not in ("0", "0,00", "0.00"):
        raise RuntimeError("O PDV já exibe um total; busca cancelada para preservar o cupom.")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    HWND = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetActiveWindow.argtypes = [HWND]
    user32.SetActiveWindow.restype = HWND
    user32.SetFocus.argtypes = [HWND]
    user32.SetFocus.restype = HWND
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = wintypes.BOOL
    user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.DWORD, ctypes.c_size_t]
    user32.mouse_event.restype = None
    user32.GetForegroundWindow.restype = HWND
    user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

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

    main_hwnd = HWND(sales[0]["hwnd"])
    field = HWND(search[0]["hwnd"])
    restore_pdv_window()
    user32.SetActiveWindow(main_hwnd)
    left, top, right, bottom = search[0]["rectangle"]
    if not user32.SetCursorPos((left + right) // 2, (top + bottom) // 2):
        raise ctypes.WinError(ctypes.get_last_error())
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.1)
    foreground = user32.GetForegroundWindow()
    foreground_pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(foreground, ctypes.byref(foreground_pid))
    if foreground_pid.value != sales[0]["process_id"]:
        raise RuntimeError("O clique não ativou o PDV; código não digitado.")
    key(0x11, True)   # Ctrl
    key(0x41, True)   # A
    key(0x41, False)
    key(0x11, False)
    key(0x08, True)   # Backspace
    key(0x08, False)
    for digit in search_text:
        key(ord(digit), True)
        key(ord(digit), False)
        time.sleep(0.03)
    time.sleep(0.2)
    after = inspect()
    final_sales = [window for window in after["windows"] if is_sale_window(window)]
    if len(final_sales) != 1:
        raise RuntimeError("A janela do PDV mudou durante a digitação; produto não confirmado.")
    final_controls = final_sales[0]["controls"]
    final_search = [control.get("value", "") for control in final_controls
                    if control["role"] == "product_search"]
    final_values = {control["role"]: control.get("value", "") for control in final_controls}
    grid_count = sum(1 for control in final_controls
                     if control["class"] == "TArpaAdvDBGrid" and control["enabled"])
    if not final_search or str(final_search[0]).strip() != search_text:
        raise RuntimeError("O código interno não ficou integral no campo Produto; busca interrompida.")
    if final_values.get("sale_price", "").strip() not in ("0", "0,000", "0.000") or \
       final_values.get("line_total", "").strip() not in ("0", "0,00", "0.00"):
        raise RuntimeError("O PDV alterou preço ou total; pare para conferir antes de selecionar.")
    return {
        "method": "Win32 API (ctypes)",
        "searchedQuery": query,
        "searchedText": search_text,
        "typingEventsSent": len(search_text),
        "fieldReadback": final_search[0] if final_search else None,
        "visibleGridCount": grid_count,
        "selected": False,
        "itemAdded": False,
        "paymentSent": False,
        "windows": after["windows"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdout", action="store_true",
                        help="emite o resultado JSON sem gravar arquivo")
    parser.add_argument("--search", help="pesquisa texto no campo Produto sem selecionar")
    args = parser.parse_args()
    output = Path(__file__).with_name("inspection-win32.json")
    try:
        result = search_product(args.search) if args.search else inspect()
        if args.stdout:
            print(json.dumps(result, ensure_ascii=False))
        else:
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"ok": bool(result["windows"]), "output": str(output.resolve()),
                              "windows": len(result["windows"])}))
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        sys.exit(1)
