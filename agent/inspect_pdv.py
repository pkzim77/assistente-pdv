"""Inspeção somente leitura. Não abre caixa, digita, clica ou emite notas."""
import argparse
import json
import sys
from pathlib import Path

# Bibliotecas locais instaladas pelo bootstrap; também funciona em virtualenv.
local_lib = Path(__file__).resolve().parents[1] / '.tools' / 'python-libs'
if local_lib.exists():
    import site
    site.addsitedir(str(local_lib))
    for extra in ('win32', 'win32/lib', 'pywin32_system32'):
        sys.path.insert(0, str(local_lib / extra))
    if sys.platform == 'win32':
        import os
        dll_dir = os.add_dll_directory(str(local_lib / 'pywin32_system32'))

def inspect(backend):
    from pywinauto import Desktop
    # A tela de entrada usa o título "CUPOM FISCAL"; as telas seguintes usam
    # PDV-FISCAL/Fechamento de Venda. O nome dos controles Edit é omitido para
    # não copiar conteúdo de campos que possam conter dados sensíveis.
    windows = Desktop(backend=backend).windows(
        title_re=r'.*(PDV-FISCAL|CUPOM FISCAL|Fechamento de Venda).*'
    )
    if not windows:
        raise RuntimeError('Abra o PDV e entre manualmente antes da inspeção.')
    result=[]
    for window in windows:
        controls=[]
        for control in window.descendants():
            info=control.element_info
            kind=getattr(info, 'control_type', '')
            # Não registrar conteúdo de campos editáveis/senhas.
            title='' if kind in ('Edit','Document') or 'edit' in info.class_name.lower() else control.window_text()
            rect=control.rectangle()
            controls.append({'automation_id':getattr(info,'automation_id',''),
                'control_id':getattr(info,'control_id',None),'type':kind,
                'class_name':info.class_name,'label':title,
                'rectangle':[rect.left,rect.top,rect.right,rect.bottom]})
        result.append({'title':window.window_text(),'process_id':window.process_id(),'controls':controls})
    return {'backend':backend,'windows':result}

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--backend',choices=['uia','win32'],default='uia')
    parser.add_argument('--output',type=Path,default=Path(__file__).with_name('inspection.json'))
    args=parser.parse_args()
    try:
        result=inspect(args.backend)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'ok':True,'output':str(args.output.resolve()),'windows':len(result['windows'])}))
    except Exception as error:
        print(json.dumps({'ok':False,'error':str(error)},ensure_ascii=False))
        sys.exit(1)
