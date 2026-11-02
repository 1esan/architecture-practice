import json,pathlib
from scenarios import public_card
ROOT=pathlib.Path(__file__).resolve().parent
bank=[]
for name in ('api','integration','design','micro'):
    p=ROOT/'data'/f'{name}.json'
    if p.exists(): bank.extend(public_card(c) for c in json.loads(p.read_text(encoding='utf-8')))
assert len(bank)==216, f'Банк ещё не готов: {len(bank)}/216'
assert len({x['id'] for x in bank})==216
html=(ROOT/'index.template.html').read_text(encoding='utf-8')
for marker,content in {'STYLE':(ROOT/'style.css').read_text(encoding='utf-8')+'\n'+(ROOT/'workbench.css').read_text(encoding='utf-8')+'\n'+(ROOT/'design-tools.css').read_text(encoding='utf-8')+'\n'+(ROOT/'learning.css').read_text(encoding='utf-8')+'\n'+(ROOT/'requirements.css').read_text(encoding='utf-8')+'\n'+(ROOT/'focused-practice.css').read_text(encoding='utf-8'),'DATA':'const BANK='+json.dumps(bank,ensure_ascii=False).replace('<','\\u003c')+';','CORE':(ROOT/'view-state.js').read_text(encoding='utf-8')+'\n'+(ROOT/'core.js').read_text(encoding='utf-8')+'\n'+(ROOT/'workbench.js').read_text(encoding='utf-8')+'\n'+(ROOT/'design-tools.js').read_text(encoding='utf-8')+'\n'+(ROOT/'learning.js').read_text(encoding='utf-8')+'\n'+(ROOT/'requirements.js').read_text(encoding='utf-8')+'\n'+(ROOT/'focused-practice.js').read_text(encoding='utf-8')+'\n'+(ROOT/'focused-state.js').read_text(encoding='utf-8'),'APP':(ROOT/'app.js').read_text(encoding='utf-8')}.items():
    html=html.replace('/*'+marker+'*/',content)
(ROOT/'index.html').write_text(html,encoding='utf-8')
print(f'Собрано {len(bank)} карточек, {len(html.encode()):,} байт')
