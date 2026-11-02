'use strict';
const assert=require('node:assert/strict');
const L=require('./learning.js');
const card=(id,title,skill='reliability',scoreId=skill)=>({id,title,rubric:[{id:scoreId,label:'generic rubric',expectation:'generic expectation',skillIds:[skill]}]});
const attempt=(id,created,overrides={})=>({id:`a-${id}-${created}`,cardId:id,cardSnapshot:card(id,`Снимок ${id}`),day:created.slice(0,10),created,source:'ai',score:50,answer:'Повтор безопасен через идемпотентный ключ K-42.',referenceSeen:false,review:{evaluationVersion:3,criteria:[{id:'reliability',score:1,evidence:'идемпотентный ключ',feedback:'слово ошибка не должно менять навык'}]},...overrides});
const cards=[card('api-001','Текущий кейс'),card('api-002','Новый кейс надёжности'),card('api-003','Новый кейс ёмкости','capacity','capacity'),card('api-004','Новый кейс требований','requirements','requirements'),card('api-005','Контрактный кейс','contracts','contract')];
const state={attempts:[
 attempt('api-001','2026-10-20T10:00:00Z',{review:{evaluationVersion:3,criteria:[{id:'reliability',score:0,evidence:'идемпотентный ключ',feedback:'старое слабое свидетельство'}]}}),
 attempt('api-001','2026-10-31T10:00:00Z',{id:'a-latest',review:{evaluationVersion:3,criteria:[{id:'reliability',score:2,evidence:'идемпотентный ключ',feedback:'слово ошибка не должно менять навык'}]}}),
 attempt('api-003','2026-10-30T10:00:00Z',{source:'self'}),
 attempt('api-004','2026-10-30T10:00:00Z',{referenceSeen:true}),
 attempt('api-005','2026-10-30T10:00:00Z',{review:{evaluationVersion:3,criteria:[{id:'contract',score:1,evidence:'цитаты нет в ответе',feedback:'x'}]}})
]};
for(const a of state.attempts)if(a.review)a.review.evaluationVersion=3;
const map=L.evidence(state,cards);
assert.equal(map.length,8);
assert.equal(map.find(x=>x.id==='reliability').count,1,'revisions of one case are one independent case');
assert.equal(map.find(x=>x.id==='reliability').cases[0].score,2,'use the latest eligible attempt, not the weakest historical score');
assert.equal(map.find(x=>x.id==='reliability').cases[0].attemptId,'a-latest');
assert.equal(map.find(x=>x.id==='contracts').count,0,'attempt after opening reference is excluded, even if it has a weak score');
assert.equal(map.find(x=>x.id==='contracts').count,0,'unsubstantiated quote is excluded');
assert.equal(map.find(x=>x.id==='security').count,0,'self-evaluation is excluded');
assert.equal(map.find(x=>x.id==='communication').count,0,'ordinary feedback words do not assign skill tags');
assert.ok(map.every(x=>!String(x.status).includes('осво')),'no single score becomes a mastery claim');
const beforeV3=structuredClone(state);for(const a of beforeV3.attempts)if(a.review)delete a.review.evaluationVersion;assert.equal(L.evidence(beforeV3,cards).reduce((n,x)=>n+x.count,0),0,'old grades do not certify new skills');
const rec=L.recommend(state,cards);
assert.equal(rec.skill.id,'reliability','a weak measured skill ranks ahead of skills with no evidence');
assert.equal(rec.card.id,'api-002','recommend a different unattempted case tagged for the weak skill');
assert.match(L.render(state,cards),/явные навыки критериев из банка/);
assert.match(L.render(state,cards),/Независимых кейсов: 1/);
assert.match(L.render(state,cards),/Пример для разбора: Текущий кейс/);
assert.match(L.render(state,cards),/Открыть кейс/);
assert.match(L.render(state,cards),/data-lab-control="queue-capacity"/);
assert.match(L.render(state,cards),/data-lab-option="enforceAuthorization"/);
assert.match(L.render(state,cards),/data-lab-option="shedding"/);
assert.match(L.render({attempts:[attempt('api-001','2026-10-31T10:00:00Z',{review:{evaluationVersion:3,criteria:[{id:'reliability',score:4,evidence:'идемпотентный ключ',feedback:''}]}})]},cards),/Пример свидетельства: Текущий кейс/);
assert.equal(L.LABS.length,8);
assert.equal(L.simulate('idempotent-retry').checks[0],'Повтор с тем же ключом не создал дубль');
assert.match(L.simulate('idempotent-retry',{retryKey:'K2'}).checks[0],/Новый ключ/);
assert.match(L.simulate('idempotent-retry',{dropResponse:false}).lines[1],/доставлен/);
assert.match(L.simulate('queue-capacity').lines[2],/\+4 событий/);
assert.equal(L.simulate('queue-capacity',{workers:2}).checks[0],'Текущей ёмкости достаточно');
assert.throws(()=>L.simulate('queue-capacity',{workers:1.5}),/целым числом/);
assert.throws(()=>L.simulate('queue-capacity',{workers:-1}),/целым числом/);
assert.throws(()=>L.simulate('queue-capacity',{workers:Infinity}),/целым числом/);
assert.throws(()=>L.simulate('stale-cache',{ttl:''}),/целым числом/);
assert.match(L.simulate('booking-race',{atomic:false}).checks[0],/двойную бронь/);
assert.match(L.simulate('booking-race').checks[0],/ровно одна/);
assert.match(L.simulate('stale-cache').checks[0],/устаревшее/);
assert.match(L.simulate('stale-cache',{invalidated:true}).checks[0],/актуальная/);
assert.match(L.simulate('api-compatibility',{required:true}).checks[0],/ломается/);
assert.match(L.simulate('api-compatibility').checks[0],/продолжает работать/);
assert.match(L.simulate('rollback-observability').checks[0],/отката достигнуто/);
assert.match(L.simulate('access-boundary',{authenticated:true,owner:true,tenant:true}).checks[0],/разрешён/);
assert.match(L.simulate('access-boundary',{authenticated:true,owner:false,tenant:true}).checks[0],/запрещён/);
assert.match(L.simulate('access-boundary',{authenticated:true,owner:false,tenant:false,enforceAuthorization:false}).checks[0],/УЯЗВИМОСТЬ.*чужую запись/);
assert.match(L.simulate('access-boundary',{authenticated:true,owner:false,tenant:false,enforceAuthorization:true}).checks[0],/Доступ запрещён/);
assert.match(L.simulate('load-shed').checks[0],/удерживает нагрузку/);
assert.match(L.simulate('load-shed',{shedding:false}).lines[2],/очередь растёт на 40/);
assert.match(L.simulate('load-shed',{shedding:false}).checks[0],/очередь растёт каждую секунду/);
assert.throws(()=>L.simulate('unknown'),/Неизвестная/);
assert.ok(L.render({attempts:[]},[]).includes('Пока нет независимых свидетельств'));
// A pre-tagged card snapshot remains a safe fallback when that card is no longer in the current bank.
const legacy=attempt('old-01','2026-10-30T09:00:00Z',{cardSnapshot:card('old-01','Старый снимок','data','invariants'),review:{evaluationVersion:3,criteria:[{id:'invariants',score:2,evidence:'идемпотентный ключ',feedback:''}]}});
legacy.review.evaluationVersion=3;
assert.equal(L.evidence({attempts:[legacy]},[]).find(x=>x.id==='data').count,1);
// Bind reads the rendered controls and passes their chosen values into the same deterministic simulator.
let click;const output={innerHTML:''};const input={dataset:{labOption:'workers'},type:'number',value:'2'};const button={dataset:{learnLab:'queue-capacity'},addEventListener:(name,fn)=>{click=fn;}};
const fake={querySelectorAll(selector){if(selector==='[data-learn-case]')return [];if(selector==='[data-learn-lab]')return [button];if(selector==='[data-lab-control="queue-capacity"] [data-lab-option]')return [input];return [];},querySelector(selector){return selector==='[data-learn-output="queue-capacity"]'?output:null;}};
L.bind(fake,{state,cards});click();assert.match(output.innerHTML,/Текущей ёмкости достаточно/,'UI selected values reach the simulation');
input.value='1.5';click();assert.match(output.innerHTML,/должен быть целым числом/,'invalid UI values show a helpful message');
let loadClick;const loadOutput={innerHTML:''},loadButton={dataset:{learnLab:'load-shed'},addEventListener:(name,fn)=>{loadClick=fn;}};const loadInputs=[{dataset:{labOption:'incoming'},type:'number',value:'120'},{dataset:{labOption:'capacity'},type:'number',value:'80'},{dataset:{labOption:'shedding'},type:'select-one',value:'false'}];
const loadFake={querySelectorAll(selector){if(selector==='[data-learn-case]')return [];if(selector==='[data-learn-lab]')return [loadButton];if(selector==='[data-lab-control="load-shed"] [data-lab-option]')return loadInputs;return [];},querySelector(selector){return selector==='[data-learn-output="load-shed"]'?loadOutput:null;}};
L.bind(loadFake,{state,cards});loadClick();assert.match(loadOutput.innerHTML,/очередь растёт на 40/,'the rendered mode switch reaches the unbounded queue model');
console.log('learning module: all checks passed');
