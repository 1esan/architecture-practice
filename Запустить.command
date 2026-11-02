#!/bin/zsh
cd "${0:A:h}"
if ! command -v python3 >/dev/null; then
  print 'Для запуска нужен Python 3.'
  read -k 1
  exit 1
fi
python3 -B - "$@" <<'PY'
import urllib.request,webbrowser,subprocess,pathlib,os,time,sys
root=pathlib.Path.cwd();url='http://127.0.0.1:8784'
def ready():
    try:
        with urllib.request.urlopen(url+'/api/health',timeout=2) as r:
            import json
            d=json.load(r)
        return d.get('app')=='architecture-practice'
    except Exception:return False
if not ready():
    # Never stop another application occupying the port.
    import socket
    s=socket.socket()
    try:s.bind(('127.0.0.1',8784))
    except OSError:
        print('Порт 8784 занят другой программой. Ничего не остановлено.');sys.exit(1)
    finally:s.close()
    (root/'.state').mkdir(exist_ok=True)
    log=open(root/'.state/server.log','ab')
    subprocess.Popen([sys.executable,'-B',str(root/'server.py')],cwd=root,stdout=log,stderr=log,start_new_session=True)
    for _ in range(60):
        if ready():break
        time.sleep(.2)
    else:print('Не удалось запустить. Журнал: .state/server.log');sys.exit(1)
if '--no-open' not in sys.argv:webbrowser.open(url)
print('Практика открыта: '+url)
PY
