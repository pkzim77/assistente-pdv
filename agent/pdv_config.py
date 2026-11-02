"""Configuração local do PDV; os valores padrão atendem ao PDV-Fiscal atual."""
import os
from pathlib import Path


def setting(name, default):
    return os.environ.get(name, "").strip() or default


PDV_EXE = setting("PDV_EXE", r"C:\Program Files (x86)\arpa\control\pdv.exe")
PDV_PROCESS_NAME = setting("PDV_PROCESS_NAME", Path(PDV_EXE).name or "pdv.exe")
PDV_WINDOW_TITLE = setting("PDV_WINDOW_TITLE", "PDV-FISCAL")
PDV_WINDOW_CLASS = setting("PDV_WINDOW_CLASS", "TFVendas")
PDV_LOGIN_TITLE = setting("PDV_LOGIN_TITLE", "CUPOM FISCAL")
PDV_CLOSING_TITLE = setting("PDV_CLOSING_TITLE", "FECHAMENTO DE VENDA")
PDV_CLOSING_CLASS = setting("PDV_CLOSING_CLASS", "TFecha_Venda")
PDV_AUX_WINDOW_CLASSES = tuple(
    value.strip() for value in setting("PDV_AUX_WINDOW_CLASSES", "TFSplashScreen,TParentForm").split(",")
    if value.strip()
)
PDV_OTHER_WINDOW_TITLES = tuple(
    value.strip() for value in setting("PDV_OTHER_WINDOW_TITLES", "PDV - CONTROL").split(",")
    if value.strip()
)


def is_closing_title(title):
    return PDV_CLOSING_TITLE.upper() in str(title).upper()


def is_sale_window(window):
    return (window.get("title") == PDV_WINDOW_TITLE and
            window.get("class") == PDV_WINDOW_CLASS)


def relevant_window_titles():
    return tuple(dict.fromkeys((PDV_LOGIN_TITLE, PDV_WINDOW_TITLE,
                                *PDV_OTHER_WINDOW_TITLES, PDV_CLOSING_TITLE)))
