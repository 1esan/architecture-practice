'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const Core = require('./core.js');
const Workbench = require('./workbench.js');
const DesignTools = require('./design-tools.js');
const bank = ['api.json', 'integration.json', 'design.json', 'micro.json']
  .flatMap(name => JSON.parse(fs.readFileSync(path.join(__dirname, 'data', name), 'utf8')));
const appSource = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');
function draft(answer, card) { const d = { answer, revealed: [], clarifications: [], twist: false, mode: 'quick', started: 1, referenceSeen: false, pending: null }; Workbench.ensure(d, card); return d; }

function makeApp(fetchImpl) {
  const elements = new Map();
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, { textContent: '', style: {}, value: '', hidden: false });
      return elements.get(id);
    },
    querySelectorAll() { return []; },
    createElement() { return { click() {}, set href(v) {}, set download(v) {} }; },
  };
  const location = { protocol: 'http:', hash: '#history' };
  const context = {
    TrainerCore: Core,
    TrainerWorkbench: Workbench,
    DesignTools,
    BANK: bank,
    document,
    location,
    localStorage: { value: null, setItem(_k, v) { this.value = v; }, getItem() { return this.value; } },
    fetch: fetchImpl,
    structuredClone,
    crypto: { randomUUID: () => 'job-test-1' },
    Date,
    Math,
    JSON,
    Promise,
    Error,
    URL,
    Blob,
    setTimeout: () => 1,
    clearTimeout() {},
    confirm: () => true,
    window: { addEventListener() {}, scrollTo() {} },
    console,
  };
  context.globalThis = context;
  const exposed = `\nglobalThis.__harness = {
    persist, startJob, beginRevision, record, pollJob, get state(){return state;}, set state(v){state=v;},
    get persisted(){return persisted;}, set persisted(v){persisted=v;},
    get revision(){return revision;}, set revision(v){revision=v;},
    get ai(){return ai;}, set ai(v){ai=v;},
    get conflict(){return conflict;}, set conflict(v){conflict=v;},
    effectiveAnswer: (d,c)=>answerFor(d,c),
    setRoute(v){route=v;}
  };`;
  const source = appSource.replace(/\nboot\(\);\s*$/, '\n') + exposed;
  vm.runInNewContext(source, context, { filename: 'app.js' });
  return { h: context.__harness, context, elements, location };
}
const ok = async (_url, options) => ({ ok: true, status: 200, async json() { return options?.body ? { revision: 1 } : {}; } });

async function testFailedSQLiteSaveBlocksJob() {
  const calls = [];
  const app = makeApp(async (url, options) => {
    calls.push({ url, options });
    return { ok: false, status: 503, async json() { return { error: 'offline' }; } };
  });
  const c = bank.find(x => x.id === 'api-101');
  const state = Core.initial();
  const d = draft('A sufficiently detailed answer for the task.', c);
  state.drafts[c.id] = d;
  app.h.state = state;
  app.h.ai = true;
  const saved = await app.h.persist();
  assert.equal(saved, false, 'persist must report a rejected SQLite save');
  calls.length = 0;
  await app.h.startJob(c, d, 'review');
  assert.equal(calls.some(x => x.url === '/api/jobs'), false, 'job must not be created without durable pending snapshot');
  assert.equal(d.pending, null, 'unsaved pending marker is rolled back');
}

async function testRevisionUsesRawAndPreservesLegacyAnswer() {
  const app = makeApp(ok);
  const c = bank.find(x => x.id === 'sys-101');
  const state = Core.initial();
  const t = draft('Raw answer text.', c);
  t.training.editor = 'free';
  t.training.diagram.nodes.push({ id: 'n-1', label: 'Orders', type: 'service', x: 100, y: 100 });
  t.training.diagram.nodes.push({ id: 'n-2', label: 'DB', type: 'store', x: 300, y: 100 });
  t.training.diagram.edges.push({ id: 'e-1', from: 'n-1', to: 'n-2', label: 'commit' });
  t.training.defense.push({ id: 'd-1', question: 'Why?', answer: 'Use a transaction.', reason: 'generated' });
  const oldEffective = Workbench.effectiveAnswer(t, c);
  state.attempts.push({
    id: 'attempt-with-raw', cardId: c.id, cardSnapshot: structuredClone(c), day: '2026-10-30',
    created: '2026-10-30T10:00:00.000Z', answer: oldEffective, rawAnswer: 'Raw answer text.',
    training: structuredClone(t.training), mode: 'quick', revealed: [], clarifications: [], twist: false,
    referenceSeen: false, source: 'self', score: 75, review: null, minutes: 5,
  });
  state.attempts.push({
    id: 'legacy-attempt', cardId: 'api-101', day: '2026-10-30', created: '2026-10-30T11:00:00.000Z',
    answer: 'Legacy free-form answer with no training metadata.', mode: 'quick', revealed: [], clarifications: [],
    twist: false, referenceSeen: false, source: 'self', score: 75, review: null, minutes: 5,
  });
  app.h.state = state;
  app.h.beginRevision('attempt-with-raw');
  const revised = state.drafts[c.id];
  assert.equal(revised.answer, 'Raw answer text.');
  assert.equal(app.h.effectiveAnswer(revised, c), oldEffective, 'diagram and defense text should occur once after revision');
  assert.equal((app.h.effectiveAnswer(revised, c).match(/Компонент: Orders/g) || []).length, 1);
  assert.equal((app.h.effectiveAnswer(revised, c).match(/Use a transaction\./g) || []).length, 1);

  app.h.beginRevision('legacy-attempt');
  assert.equal(state.drafts['api-101'].answer, 'Legacy free-form answer with no training metadata.', 'legacy attempt answer remains editable');
  await app.h.persist();
}

function testTrainingStateRoundTrip() {
  const c = bank.find(x => x.id === 'sys-001');
  const d = draft('Raw notes.', c);
  d.training.editor = 'free';
  d.training.sections.requirements = 'SLO p95 300 ms.';
  d.training.diagram.nodes = [{ id: 'api', label: 'API', type: 'service', x: 50, y: 50 }, { id: 'db', label: 'DB', type: 'store', x: 200, y: 50 }];
  d.training.diagram.edges = [{ id: 'edge-1', from: 'api', to: 'db', label: 'read/write' }];
  d.training.defense = [{ id: 'def-1', question: 'Failure?', answer: 'Retry safely.', reason: 'derived from answer' }];
  const effective = Workbench.effectiveAnswer(d, c);
  assert.equal((effective.match(/Связь: API → DB: read\/write/g) || []).length, 1);
  assert.equal((effective.match(/Retry safely\./g) || []).length, 1);
  const state = Core.initial();
  state.drafts[c.id] = d;
  state.attempts.push({
    id: 'with-training', cardId: c.id, cardSnapshot: structuredClone(c), day: '2026-10-31',
    created: '2026-10-31T10:00:00.000Z', answer: effective, rawAnswer: d.answer,
    training: structuredClone(d.training), mode: 'quick', revealed: [], clarifications: [], twist: false,
    referenceSeen: false, source: 'self', score: 75, review: null, minutes: 10,
  });
  const roundTrip = JSON.parse(JSON.stringify(Core.validate(state, bank)));
  Core.validateTraining(roundTrip.drafts[c.id].training);
  assert.equal(Workbench.effectiveAnswer(roundTrip.drafts[c.id], c), effective);
  assert.equal(roundTrip.attempts[0].training.defense[0].answer, 'Retry safely.');
  assert.equal(roundTrip.attempts[0].answer, effective);
}

function testMicroAttemptSnapshotIsClientValidatable() {
  const c = bank.find(x => x.id === 'sys-101' && x.format === 'micro');
  const s = Core.initial();
  s.attempts.push({
    id: 'micro-saved', cardId: c.id, cardSnapshot: structuredClone(c), day: '2026-10-31',
    created: '2026-10-31T10:00:00.000Z', answer: 'Micro answer saved.', rawAnswer: 'Micro answer saved.',
    mode: 'quick', revealed: [], clarifications: [], twist: false, referenceSeen: false,
    source: 'self', score: 75, review: null, minutes: 5,
  });
  assert.doesNotThrow(() => Core.validate(JSON.parse(JSON.stringify(s)), bank), 'saved micro attempt must survive client validation after SQLite reload/import');
}

function testMiniPlanAndFixedExistingPlan() {
  const day = '2026-11-05';
  const s = Core.initial();
  s.settings.goal = 3;
  s.settings.practiceFormat = 'micro';
  const fresh = Core.plan(bank, s, day);
  assert.equal(fresh.length, 3);
  assert.ok(fresh.every(id => bank.find(c => c.id === id)?.format === 'micro'));
  const fullIds = bank.filter(c => c.pool === 'api' && c.format !== 'micro').slice(0, 2).map(c => c.id);
  const fixed = Core.initial();
  fixed.settings.practiceFormat = 'micro';
  fixed.plans[day] = fullIds;
  assert.deepEqual(Core.plan(bank, fixed, day), fullIds, 'format changes must not reshuffle a fixed existing plan');
}


async function testDesignToolsSnapshotAndFactDisclosure(){
  const app=makeApp(ok),c=bank.find(x=>x.id==='sys-001'),s=Core.initial(),d=draft('Сохраняем бронь атомарно и возвращаем стабильный ID.',c);
  d.training.editor='free';DesignTools.ensure(d);d.designTools.capacity.requestsPerDay='86400';
  app.h.state=s;s.drafts[c.id]=d;
  const snapshot=structuredClone(d);snapshot.rawAnswer=d.answer;snapshot.answer=app.h.effectiveAnswer(d,c);
  const a=app.h.record(c,snapshot,null,'self',75);d.designTools.capacity.requestsPerDay='172800';
  assert.equal(a.designTools.capacity.requestsPerDay,'86400','attempt stores an immutable tools snapshot');
  app.h.beginRevision(a.id);
  assert.equal(s.drafts[c.id].designTools.capacity.requestsPerDay,'86400');
  const revised=app.h.effectiveAnswer(s.drafts[c.id],c);
  assert.equal((revised.match(/Расчёты и свойства решения:/g)||[]).length,1,'tools must not duplicate on revision');
  assert.equal(revised,a.answer);
  const qapp=makeApp(async(url,options)=>({ok:true,status:200,async json(){return url.startsWith('/api/jobs/')?{status:'succeeded',result:{answer:'40 запросов в секунду.',factIds:['load']}}:{revision:1};}}));
  const qs=Core.initial(),qd=draft('',c);qd.pending={id:'question-id',kind:'question',question:'Какой поток?',snapshot:structuredClone(qd)};qs.drafts[c.id]=qd;qapp.h.state=qs;qapp.h.setRoute('history');
  await qapp.h.pollJob(c,qd,'question-id');
  assert.deepEqual([...qd.revealed],['load'],'AI used fact IDs become revealed and activate applicable criteria');
  assert.equal(qd.clarifications.length,1);
}

(async () => {
  await testDesignToolsSnapshotAndFactDisclosure();
  await testFailedSQLiteSaveBlocksJob();
  await testRevisionUsesRawAndPreservesLegacyAnswer();
  testTrainingStateRoundTrip();
  testMiniPlanAndFixedExistingPlan();
  try { testMicroAttemptSnapshotIsClientValidatable(); } catch (error) { console.error('FAIL micro attempt snapshot validation:', error.message); process.exitCode = 1; return; }
  process.stdout.write('6 client regression groups passed\n');
})().catch(error => { console.error(error); process.exitCode = 1; });
