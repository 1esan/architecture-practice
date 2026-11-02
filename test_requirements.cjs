const assert=require('node:assert/strict');
const R=require('./requirements.js');
const fs=require('node:fs');
const d={answer:'',revealed:[],clarifications:[{question:'Сколько?',answer:'Пять',source:'prepared',factIds:['f1']}],twist:false};
const card={brief:'Клиент <делает> заказ\nВторая строка'};
R.ensure(d);
assert.equal(R.validate(d.requirements),true);
const req=R.add(d,{type:'fact',text:'Заказ обрабатывается за < 2 секунды',status:'confirmed',source:{kind:'brief',index:0}});
assert.match(req.id,/^[\w-]+$/);
const clarification=R.add(d,{type:'quality',text:'Доступность 99.9%',status:'open',source:{kind:'clarification',index:0}});
assert.equal(clarification.source.index,0);
assert.throws(()=>R.add(d,{type:'assumption',text:'Временная гипотеза',status:'confirmed',source:{kind:'brief',index:0}}),/нельзя пометить подтверждённым/);
R.add(d,{type:'assumption',text:'Пиковая нагрузка пока неизвестна',status:'open',source:{kind:'brief',index:0}});
assert.match(R.html(card,d),/>Условие<\/a>/);
assert.match(R.html(card,d),/Зафиксировать вывод/);
assert.match(R.html(card,d),/&lt;делает&gt;/);
assert.doesNotMatch(R.html(card,d),/<делает>/);
R.updateEntry(d,req.id,{type:'functional',text:'Система сохраняет заказ',status:'confirmed'});
assert.equal(d.requirements.entries[0].history.length,1);
assert.equal(d.requirements.entries[0].history[0].text,'Заказ обрабатывается за < 2 секунды');
assert.match(R.text(d),/Система сохраняет заказ/);
assert.match(R.text(d),/Доступность 99.9%/);
assert.match(R.text(d),/Пиковая нагрузка пока неизвестна/);
const question=R.add(d,{type:'question',text:'Можно ли отменить заказ?',status:'open',source:{kind:'clarification',index:0}});
assert.match(R.text(d),/открытое предложение/);
assert.match(R.text(d),/Можно ли отменить заказ/);
assert.ok(R.signature(d).length<100,'review signature must fit compact transport limits');
const saved=JSON.parse(JSON.stringify(d.requirements));
assert.equal(R.validate(saved),true);
assert.throws(()=>R.validate({...saved,entries:[{...saved.entries[0],text:'   '}]}),/Некорректная/);
assert.throws(()=>R.validate({...saved,entries:[...saved.entries,{...saved.entries[0]}]}),/Некорректная/);
assert.throws(()=>R.validate({...saved,entries:[{...saved.entries[0],source:{kind:'brief',index:1}}]}),/Некорректная/);
const before=R.signature(d);
d.clarifications[0].answer='Шесть';
assert.notEqual(R.signature(d),before,'answer change must invalidate review snapshot');
const reviewed=R.setReview(d,{summary:'Проверены пробелы',model:'model-x',findings:[{kind:'missing',severity:'minor',entryIds:[req.id],message:'Нет сценария отказа',suggestion:'Уточнить поведение'}]},R.signature(d));
assert.equal(reviewed.findings.length,1);
assert.doesNotThrow(()=>R.setReview(d,{summary:'Замечаний нет',findings:[]},R.signature(d)));
const afterReview=R.signature(d);
R.updateEntry(d,req.id,{type:'functional',text:'Система сохраняет заказ после сбоя',status:'confirmed'});
assert.notEqual(d.requirements.review,null,'keep prior feedback visible for comparison');
assert.notEqual(R.signature(d),afterReview,'entry edit must invalidate review');
assert.match(R.html(card,d),/Предыдущий разбор · требует обновления/);
assert.match(R.html(card,d),/#req-source-clarification-0/);
const rendered=R.html(card,d);
assert.match(rendered,/data-req-edit=/,'entries expose a single edit action');
assert.doesNotMatch(rendered,/<textarea data-req-text=/,'entries do not show permanent editors');
assert.doesNotMatch(rendered,/<select data-req-type=/,'entries do not show permanent category selectors');
assert.doesNotMatch(rendered,/<form class="req-composer"/,'composer stays closed until requested');
assert.match(rendered,/id="question"/);assert.match(rendered,/id="ask"/);
assert.match(rendered,/class="req-workspace"/,'conversation and notes share a two-column desktop layout');
assert.match(rendered,/data-req-tab="dialog"/,'mobile exposes a conversation tab');
const uiCSS=fs.readFileSync(require('node:path').join(__dirname,'requirements.css'),'utf8');
assert.match(uiCSS,/\.req-workspace\{display:grid;grid-template-columns:/,'desktop columns divide dialogue and notebook');
assert.doesNotMatch(uiCSS,/\.req-entry-list\{[^}]*repeat\(2/,'entries remain a single compact list');
assert.doesNotMatch(uiCSS,/position:\s*sticky|max-height:\s*calc\(|overflow-y:\s*(auto|scroll)/,'the page has no nested scrolling notebook');
assert.match(rendered,/Ответ 1/,'clarification sources are concise');
const vague={clarifications:[],revealed:[],twist:false};R.ensure(vague);R.add(vague,{type:'quality',text:'Высокая доступность и быстрая обработка запросов',status:'open',source:{kind:'brief',index:0}});assert.ok(R.warnings(vague).some(x=>x.message.includes('измеримого')));

// Exercise the rendered editor through bind(), including an unrelated app rerender.
class Control {
  constructor(value=''){this.value=value;this.listeners={};this.dataset={};this.focused=false;}
  addEventListener(name,fn){(this.listeners[name]??=[]).push(fn);}
  fire(name,event={}){for(const fn of this.listeners[name]||[])fn({preventDefault(){},target:this,...event});}
  focus(){this.focused=true;}
  scrollIntoView(){this.scrolled=true;}
}
const uiDraft={answer:'',revealed:[],clarifications:[],twist:false};R.ensure(uiDraft);
const uiCard={brief:'Вводное условие'};
let uiHTML='',saves=0,doc,latestUI;
const decode=s=>s.replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&amp;/g,'&');
function selectedValue(markup,selector){const m=markup.match(new RegExp(String.raw`<select[^>]* ${selector}[^>]*>([\s\S]*?)</select>`));return m?.[1].match(/<option value=\"([^\"]+)\"[^>]*selected/)?.[1]||'';}
function renderUI(){uiHTML=R.html(uiCard,uiDraft);const controls={};const newButton=new Control();controls.new=newButton;
  const editButtons=[...uiHTML.matchAll(/data-req-edit="([^"]+)"/g)].map(m=>{const b=new Control();b.dataset.reqEdit=m[1];return b;});
  const fixButtons=[...uiHTML.matchAll(/data-req-fix="([^"]+)"/g)].map(m=>{const b=new Control();b.dataset.reqFix=m[1];return b;});
  const tabButtons=[...uiHTML.matchAll(/data-req-tab="([^"]+)"/g)].map(m=>{const b=new Control();b.dataset.reqTab=m[1];return b;});
  let form=null;if(uiHTML.includes('data-req-composer')){const text=decode(uiHTML.match(/<textarea[^>]*data-compose-text[^>]*>([\s\S]*?)<\/textarea>/)?.[1]||'');const type=selectedValue(uiHTML,'data-compose-type'),status=selectedValue(uiHTML,'data-compose-status'),source=selectedValue(uiHTML,'data-compose-source');const fields={'[data-compose-text]':new Control(text),'[data-compose-type]':new Control(type),'[data-compose-status]':new Control(status),'[data-compose-source]':source?new Control(source):null,'[data-compose-error]':new Control()};form=new Control();form.querySelector=s=>fields[s]||null;form.querySelectorAll=()=>[];controls.form=form;controls.fields=fields;controls.close=new Control();}
  const rootNode=new Control();rootNode.querySelectorAll=s=>s==='[data-req-new]'?[newButton]:s==='[data-req-edit]'?editButtons:s==='[data-req-fix]'?fixButtons:s==='[data-req-tab]'?tabButtons:[];rootNode.querySelector=s=>s==='[data-req-composer]'?form:s==='[data-req-close]'?controls.close:null;
  const question=new Control(uiDraft.requirements.questionDraft);doc={querySelector:s=>s==='.req-board'?rootNode:s==='#question'?question:s==='#ask'?new Control():s==='[data-compose-text]'?fieldsText():null,getElementById:()=>null};
  function fieldsText(){return controls.fields?.['[data-compose-text]']||null;}
  global.document=doc;R.bind(uiCard,uiDraft,{save(){saves++;},render:renderUI});latestUI={newButton,editButtons,fixButtons,tabButtons,form,fields:controls.fields,close:controls.close};return latestUI;
}
let ui=renderUI();
assert.doesNotMatch(uiHTML,/<textarea data-compose-text/,'composer is absent before an action');
assert.equal(ui.fields,undefined);
ui.newButton.fire('click');ui=latestUI;
assert.match(uiHTML,/<form class="req-composer"/,'Add opens the shared composer');
assert.ok(ui.fields['[data-compose-text]'].focused,'opening the composer restores focus to its text field');
assert.ok(ui.fields['[data-compose-text]'].scrolled,'opening the composer scrolls it into view');
ui.fields['[data-compose-text]'].value='Unsaved sentence survives';ui.form.fire('input');
uiDraft.clarifications.push({question:'New answer arrived',answer:'Relevant context',source:'prepared',factIds:[]});
ui=renderUI();
assert.match(uiHTML,/Unsaved sentence survives/,'an unrelated rerender preserves editor text');
ui.form.fire('submit');
assert.equal(uiDraft.requirements.entries.length,1,'submitting adds exactly one user-confirmed entry');
assert.equal(uiDraft.requirements.entries[0].text,'Unsaved sentence survives');
assert.equal(saves,1,'successful add saves the draft');
const savedSource=uiDraft.requirements.entries[0].source,sourceSnapshot={...savedSource};
ui=renderUI();ui.editButtons[0].fire('click');ui=latestUI;
assert.match(uiHTML,/Изменить запись/);
assert.doesNotMatch(uiHTML,/data-compose-source/,'source is not editable after an entry is created');
assert.ok(ui.fields['[data-compose-text]'].focused);
ui.fields['[data-compose-text]'].value='Unsaved edit survives';ui.form.fire('input');
ui.fields['[data-compose-type]'].value='quality';ui.form.fire('change',{target:ui.fields['[data-compose-type]']});ui=latestUI;
assert.match(uiHTML,/<option value="quality" selected>/,'edited category persists through its own rerender');
uiDraft.clarifications.push({question:'Edit rerender answer',answer:'Another response',source:'prepared',factIds:[]});ui=renderUI();
assert.match(uiHTML,/Unsaved edit survives/,'editing text also survives an asynchronous rerender');
ui.form.fire('submit');
assert.equal(uiDraft.requirements.entries[0].text,'Unsaved edit survives');
assert.equal(uiDraft.requirements.entries[0].type,'quality');
assert.deepEqual(uiDraft.requirements.entries[0].source,sourceSnapshot,'editing leaves source provenance unchanged');
assert.equal(uiDraft.requirements.entries[0].history.length,1,'editing appends prior text to history');
assert.equal(saves,2);
ui=renderUI();
assert.doesNotMatch(uiHTML,/<textarea data-compose-text|<select data-compose-type/,'read view has no visible editor controls');
ui=renderUI();ui.fixButtons[0].fire('click');ui=latestUI;
assert.match(uiHTML,/Разобрать ответ/);
assert.match(uiHTML,/<option value="open" selected>/,'a proposed extraction stays open until explicitly confirmed');
assert.match(uiHTML,/data-req-tab="records" class="is-active"/,'opening the fix editor switches the mobile view to records');
ui.newButton.fire('click');ui=latestUI;ui.close.fire('click');ui=latestUI;
assert.equal(uiDraft.requirements.entries.length,1,'closing the composer cancels without adding a record');
assert.doesNotMatch(uiHTML,/<form class="req-composer"/,'cancel returns to the compact read view');
assert.match(uiHTML,/>Условие<\/a>/,'brief source label is concise');
delete global.document;

console.log('requirements module tests passed');
