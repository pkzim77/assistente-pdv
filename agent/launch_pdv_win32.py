"""Abre o PDV-Fiscal se ainda não houver processo; não autentica nem vende."""
import ctypes
import json
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path
from pdv_config import PDV_EXE, PDV_PROCESS_NAME, is_sale_window, is_closing_title


def pdv_processes():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ULONG_PTR = ctypes.c_size_t

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ULONG_PTR),
            ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    if snapshot == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    found = []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        more = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            if entry.szExeFile.casefold() == PDV_PROCESS_NAME.casefold():
                found.append({"pid": int(entry.th32ProcessID), "name": entry.szExeFile})
            more = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return found


def launch():
    if sys.platform != "win32":
        raise RuntimeError("A inicialização do PDV só funciona no Windows.")
    active = pdv_processes()
    if active:
        from inspect_pdv_win32 import inspect
        from restore_pdv_win32 import restore

        snapshot = inspect()
        sales = [window for window in snapshot["windows"] if is_sale_window(window)]
        closings = [window for window in snapshot["windows"]
                    if is_closing_title(window["title"])]
        restored = False
        restore_message = None
        if len(sales) == 1 and not closings and \
           (sales[0].get("visible") is False or sales[0].get("minimized") is True):
            try:
                restore_result = restore()
                restored = bool(restore_result.get("visible"))
            except Exception as error:
                restore_message = str(error)
            snapshot = inspect()
            sales = [window for window in snapshot["windows"] if is_sale_window(window)]
            closings = [window for window in snapshot["windows"]
                        if is_closing_title(window["title"])]

        required = ("quantity", "product_search", "sale_price", "line_total")
        from pdv_geometry import layout_diagnostics
        layout = layout_diagnostics(sales[0]) if len(sales) == 1 else None
        roles_ok = len(sales) == 1 and all(
            sum(1 for control in sales[0]["controls"] if control["role"] == role) == 1 and
            next(control for control in sales[0]["controls"] if control["role"] == role)["enabled"] and
            next(control for control in sales[0]["controls"] if control["role"] == role).get("within_window") is True
            for role in required)
        roles_ok = roles_ok and bool(layout and layout["layoutFits"])
        usable = (len(sales) == 1 and sales[0].get("visible") is True and
                  sales[0].get("minimized") is False and not closings and roles_ok)
        if usable:
            message = ("O PDV já estava aberto; a janela foi reexibida e os quatro campos foram validados."
                       if restored else "O PDV já está aberto e a janela e os quatro campos foram validados.")
        elif closings:
            message = "O PDV está em fechamento de venda; retorne ao PDV Livre. Nenhuma segunda instância foi aberta."
        elif len(sales) == 1 and (sales[0].get("visible") is False or sales[0].get("minimized") is True):
            detail = f" Detalhe: {restore_message}." if restore_message else ""
            message = "O processo PDV existe, mas a janela continua oculta após tentar reexibi-la. Nenhuma segunda instância foi aberta." + detail
        elif len(sales) != 1:
            message = "O processo PDV existe, mas não há exatamente uma janela de venda acessível. Nenhuma segunda instância foi aberta."
        else:
            if layout and layout["clippedFields"]:
                message = ("O layout interno do PDV passa dos limites da janela atual ("
                           + str(layout["windowSize"]["width"]) + "×"
                           + str(layout["windowSize"]["height"]) + "). Campos/painéis fora da janela: "
                           + ", ".join(layout["clippedFields"])
                           + ". Feche e reabra o PDV neste monitor para ele recalcular o layout. Nenhuma entrada foi enviada.")
            else:
                message = "A janela existe, mas os campos não foram mapeados de forma única e habilitada. Nenhuma entrada foi enviada."
        return {"ok": True, "launched": False, "alreadyRunning": True,
                "windowUsable": usable, "windowRestored": restored,
                "layout": layout,
                "windowCount": len(sales), "mappedFields": [role for role in required
                    if len(sales) == 1 and sum(1 for control in sales[0]["controls"]
                                               if control["role"] == role) == 1],
                "processes": active, "message": message}

    executable = Path(PDV_EXE)
    if not executable.is_file():
        raise RuntimeError("PDV_EXE não aponta para um executável existente: " + str(executable))
    # A API chama este auxiliar com windowsHide=True. Repassamos explicitamente
    # SW_SHOWNORMAL para que o aplicativo gráfico não herde o estado oculto.
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 1  # SW_SHOWNORMAL
    process = subprocess.Popen([str(executable)], cwd=str(executable.parent),
                               close_fds=True, startupinfo=startupinfo)
    time.sleep(1.0)
    return {"ok": True, "launched": True, "alreadyRunning": False,
            "pid": process.pid,
            "message": "PDV iniciado em janela normal. Se aparecer a tela de login, entre no próprio PDV."}


if __name__ == "__main__":
    try:
        print(json.dumps(launch(), ensure_ascii=False))
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        sys.exit(1)
