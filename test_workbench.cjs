'use strict';
const assert=require('node:assert/strict');
const W=require('./workbench.js');
const card={id:'sys-101',pool:'design',title:'Сервис бронирования переговорной',brief:'Сотрудник резервирует комнату на интервал; два человека могут выбрать один слот одновременно.',deliverables:['Контракт запроса и ответа с примерами.','Ограничение на параллельную бронь и правила восстановления.'],rubric:[{id:'contract',label:'Контракт API',expectation:'Статусы, поля и примеры'},{id:'invariants',label:'Инварианты данных',expectation:'Нет двойной брони'},{id:'security',label:'Безопасность и доступ',expectation:'Tenant и права на объект'},{id:'reliability',label:'Отказы и восстановление',expectation:'Безопасные повторы'}],facts:[
  {id:'load',label:'Нагрузка',question:'Какая ожидается нагрузка?',answer:'Неизвестно'},
  {id:'sla',label:'Доступность',question:'Какой SLA требуется?',answer:'99.9%'},
  {id:'auth',label:'Авторизация',question:'Нужна ли авторизация?',answer:'Да'}
]};
const d={answer:'Унаследованный текст решения'};
let t=W.ensure(d,card);
assert.equal(t.editor,'free');assert.equal(d.answer,'Унаследованный текст решения');assert.deepEqual(Object.keys(t.sections),['requirements','boundaries','data','flow','resilience','tradeoffs']);t.editor='stages';
const identity=t,sectionsIdentity=t.sections,diagramIdentity=t.diagram,nodesIdentity=t.diagram.nodes,edgesIdentity=t.diagram.edges,defenseIdentity=t.defense;W.ensure(d,card);assert.equal(d.training,identity);assert.equal(t.sections,sectionsIdentity);assert.equal(t.diagram,diagramIdentity);assert.equal(t.diagram.nodes,nodesIdentity);assert.equal(t.diagram.edges,edgesIdentity);assert.equal(t.defense,defenseIdentity);
assert.deepEqual(W.matchFacts(card,'Какая ожидается нагрузка?').facts.map(x=>x.id),['load']);
assert.deepEqual(W.matchFacts(card,'вопрос ни о чём незнакомом'),{facts:[],ambiguous:false});
assert.deepEqual(W.matchFacts(card,'не про нагрузку').facts,[]);
assert.equal(W.matchFacts(card,'нагрузка и SLA').ambiguous,true);
assert.deepEqual(W.matchFacts({...card,facts:[{id:'load',label:'Нагрузка',question:'Какова нагрузка?',answer:'x'}]},'Какой ожидаемый пик запросов в секунду?').facts.map(x=>x.id),['load']);
assert.deepEqual(W.matchFacts({...card,facts:[{id:'auth',label:'Авторизация',question:'Кто имеет право?',answer:'x'},{id:'sla',label:'Доступность',question:'Какой SLA?',answer:'y'}]},'какова доступность сервиса?').facts.map(x=>x.id),['sla']);
assert.deepEqual(W.matchFacts({...card,facts:[{id:'auth',label:'Авторизация',question:'Кто имеет право?',answer:'x'}]},'может ли пользователь читать чужие данные?').facts,[],'неизвестный синоним не должен угадывать подготовленный ответ');
t.sections.flow='API принимает запрос и пишет в базу данных';t.sections.tradeoffs='Не добавляю брокер, чтобы снизить задержку';
t.diagram.nodes=[{id:'a',label:'API',type:'service',x:80,y:80},{id:'b',label:'База данных',type:'store',x:280,y:80}];t.diagram.edges=[{id:'e',from:'a',to:'b',label:'Запись'}];
const ans=W.effectiveAnswer(d,card);assert.match(ans,/API → База данных: Запись/);assert.doesNotMatch(ans,/Унаследованный текст/);assert.doesNotMatch(ans,/data:image/);
const q=W.nextDefense(card,d);assert.match(q.question,/очереди|повторную доставку/);t.defense.push(q);assert.ok(W.nextDefense(card,d));
const defended={answer:'',training:{editor:'free',sections:{},diagram:{nodes:[{id:'a',label:'broker',type:'service'},{id:'b',label:'DB',type:'store'}],edges:[]},defense:[]}};let questions=[];for(let i=0;i<5;i++){const next=W.nextDefense(card,defended);assert.ok(next);questions.push(next.question);defended.training.defense.push(next);}assert.equal(new Set(questions).size,5);assert.equal(W.nextDefense(card,defended),null);
const gapDraft={answer:'',lastReview:{criteria:[{id:'contract',score:1,feedback:'Не хватает деталей.'},{id:'security',score:0,feedback:'Недостаточно проверки.'}]},training:{editor:'free',sections:{},diagram:{nodes:[],edges:[]},defense:[]}};
const gap1=W.nextDefense(card,gapDraft);assert.match(gap1.question,/Безопасность и доступ.*0\/4/);assert.match(gap1.question,/кто проверяет право на конкретный объект/);assert.equal(gap1.reason,'gap-security');gapDraft.training.defense.push({...gap1,answer:'Проверю tenant и владельца записи.'});
const gap2=W.nextDefense(card,gapDraft);assert.match(gap2.question,/Контракт API.*1\/4/);assert.match(gap2.question,/Сервис бронирования переговорной/);assert.notEqual(gap1.question,gap2.question);
const secret='СКРЫТАЯ ВВОДНАЯ: лимит ровно 7 запросов в секунду';const noLeakCard={...card,facts:[{id:'secret',label:'Секрет',question:'Скрытое условие?',answer:secret}]};const noLeak={answer:'',training:{editor:'free',sections:{},diagram:{nodes:[],edges:[]},defense:[]}};const publicQ=W.nextDefense(noLeakCard,noLeak);assert.ok(publicQ);assert.doesNotMatch(publicQ.question,/7 запросов|СКРЫТАЯ ВВОДНАЯ/);assert.doesNotMatch(publicQ.question,/Скрытое условие/);
const component={answer:'',training:{editor:'free',sections:{},diagram:{nodes:[{id:'a',label:'Сервис бронирования',type:'service',x:10,y:10},{id:'b',label:'PostgreSQL',type:'store',x:20,y:20}],edges:[{id:'e',from:'a',to:'b',label:'атомарная запись'}]},defense:[]}};const compQ=W.nextDefense(card,component);assert.match(compQ.question,/Сервис бронирования.*PostgreSQL/);component.training.defense.push(compQ);const compQ2=W.nextDefense(card,component);assert.notEqual(compQ.question,compQ2.question);
const staged={answer:'',training:{editor:'stages',stage:0,sections:{requirements:'',boundaries:'',data:'',flow:'',resilience:'',tradeoffs:''},diagram:{nodes:[],edges:[]},defense:[]}};const stagedHtml=W.html(card,staged);assert.match(stagedHtml,/Контрольная точка: назови пользователей/);assert.match(stagedHtml,/Например: сотрудник создаёт бронь/);staged.training.stage=4;assert.match(W.html(card,staged),/повторяет тот же ключ/i);
const legacy={answer:'Старый черновик',training:null};assert.equal(W.ensure(legacy,card).editor,'free');assert.equal(W.effectiveAnswer(legacy,card),'Свободный ответ:\nСтарый черновик');
const free={answer:'Именно свободный ответ',training:{editor:'free',sections:{flow:'Скрытый этаповый текст'}}};assert.doesNotMatch(W.html(card,free),/data-tw-section/);assert.match(W.effectiveAnswer(free,card),/Именно свободный ответ/);assert.doesNotMatch(W.effectiveAnswer(free,card),/Скрытый этаповый текст/);
const snap=W.snapshotHTML(t);assert.match(snap,/API/);assert.match(snap,/Запись/);
const unsafe={answer:'',training:{editor:'free',sections:{flow:'<img src=x onerror=alert(1)>'},diagram:{nodes:[{id:'n-1',label:'<script>x</script>',type:'service'}]}}};
assert.doesNotMatch(W.html(card,unsafe),/<script>x/);assert.match(W.html(card,unsafe),/&lt;script&gt;/);
assert.equal(W.matchFacts(card,'Какая ожидается нагрузка? Какие роли участвуют?').facts.length,0,'compound question must not receive only the prepared load answer');
console.log('workbench tests passed');
