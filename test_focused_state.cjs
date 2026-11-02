'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const W=require('./workbench.js'),F=require('./focused-practice.js'),S=require('./focused-state.js'),C=require('./core.js');
const card={id:'int-001',pool:'integration',title:'Test'};
const fresh=()=>{const d={answer:'',revealed:[],clarifications:[],mode:'quick',twist:false};W.ensure(d,card);return d;};
let d=fresh();d.answer='Старый свободный ответ';d.training.sections.data='Старые данные';d.training.editor='stages';S.ensure(card,d);
assert.equal(d.focusedVersion,1);assert.match(d.answer,/Старые данные/);assert.match(d.answer,/Старый свободный ответ/);assert.equal(d.training.sections.data,'');
const once=JSON.stringify(d);S.ensure(card,d);assert.equal(JSON.stringify(d),once);
d.training.sections.boundaries='rest,webhook';d.training.sections.flow='Запрос запускает работу, callback возвращает результат';d.training.diagram.nodes=[{id:'n1',label:'Внешняя система',type:'external',x:10,y:20}];
const answer=S.solution(card,d,F,W);for(const term of ['REST','Webhook','callback','Внешняя система','Старые данные'])assert.ok(answer.includes(term),term);
assert.equal(answer.match(/Старый свободный ответ/g).length,1);
const huge=fresh();huge.answer='x'.repeat(59000);huge.training.sections.data='y'.repeat(8000);const hugeBefore=JSON.stringify(huge);assert.equal(S.ensure(card,huge),false);assert.equal(JSON.stringify(huge),hugeBefore);
const state=C.initial();state.drafts[card.id]=d;C.validate(JSON.parse(JSON.stringify(state)),[card]);
assert.equal(S.solution(card,JSON.parse(JSON.stringify(d)),F,W),answer);
assert.throws(()=>C.validate({...state,drafts:{[card.id]:{...d,focusedVersion:2}}},[card]));
const design={...card,pool:'design'};const old=fresh();old.training.editor='stages';old.training.sections.requirements='Не трогать';const copy=JSON.stringify(old);S.ensure(design,old);assert.equal(JSON.stringify(old),copy);assert.equal(S.solution(design,old,F,W),W.effectiveAnswer(old,design));
// Exercise actual application snapshot and restore, not a parallel implementation.
const ctx={TrainerCore:C,TrainerWorkbench:W,FocusedPractice:F,FocusedState:S,BANK:[card],location:{protocol:'file:',hash:'#history'},document:{getElementById:()=>({textContent:'',style:{}})},structuredClone,crypto:require('node:crypto').webcrypto,Date,JSON,console,setTimeout:()=>0,clearTimeout(){},localStorage:{setItem(){}},confirm:()=>true};ctx.globalThis=ctx;
const src=fs.readFileSync('app.js','utf8').replace(/boot\(\);\s*$/,'');
vm.runInNewContext(src+`;globalThis.test={draft,answerFor,solutionAnswer,record,editorHTML,phaseHTML,beginRevision,get state(){return state},set state(x){state=x},set render(x){render=x},set persist(x){persist=x}}`,ctx);
const h=ctx.test;h.persist=()=>true;h.render=()=>{};h.state=state;
const draft=h.draft(card);const html=h.editorHTML(card,draft);assert.match(html,/focused-practice/);assert.match(html,/tw-workbench/);assert.match(html,/необязательно/);assert.doesNotMatch(html,/data-editor="stages"/);
const snapshot=structuredClone(draft);snapshot.rawAnswer=draft.answer;snapshot.answer=h.answerFor(draft,card);
const attempt=h.record(card,snapshot,null,'self',75);assert.equal(attempt.focusedVersion,1);assert.ok(attempt.answer.includes('callback'));assert.equal(attempt.rawAnswer,draft.answer);
// beginRevision may initiate a route change, but must preserve structured fields and format marker.
h.beginRevision(attempt.id);assert.equal(h.state.drafts[card.id].focusedVersion,1);assert.equal(h.state.drafts[card.id].training.sections.flow,draft.training.sections.flow);
assert.ok(h.phaseHTML(card,draft).includes('Выбор взаимодействия'));
console.log('focused state migration, snapshot, restore and rendering passed');
