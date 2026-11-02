'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const Core = require('./core.js');
const Workbench = require('./workbench.js');
const Requirements = require('./requirements.js');
const DesignTools = require('./design-tools.js');
const bank = ['api.json', 'integration.json', 'design.json', 'micro.json']
  .flatMap(name => JSON.parse(fs.readFileSync(path.join(__dirname, 'data', name), 'utf8')));
const appSource = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');

function makeApp(fetchImpl = async () => ({ ok: true, async json() { return { revision: 1 }; } })) {
  const elements = new Map();
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, { id, textContent: '', style: {}, value: '', hidden: false, onclick: null });
      return elements.get(id);
    },
    querySelector(selector) { return selector === '.req-board' ? null : null; },
    querySelectorAll() { return []; },
    createElement() { return { click() {}, set href(v) {}, set download(v) {} }; },
  };
  const context = {
    TrainerCore: Core, TrainerWorkbench: Workbench, TrainerRequirements: Requirements,
    DesignTools, BANK: bank, document,
    location: { protocol: 'http:', hash: '#case/api-101' },
    localStorage: { value: null, setItem(_k, v) { this.value = v; }, getItem() { return this.value; } },
    fetch: fetchImpl, structuredClone, crypto: { randomUUID: () => 'job-test-1' }, Date, Math, JSON,
    Promise, Error, URL, Blob, setTimeout: fn => { if (fn) queueMicrotask(fn); return 1; }, clearTimeout() {}, confirm: () => true,
    window: { addEventListener() {}, scrollTo() {} }, console,
  };
  context.globalThis = context;
  const exposed = `\nglobalThis.__harness = {
    answerFor, record, beginRevision, startJob, pollJob, caseView, bindQuestions, bindInterview,
    get state(){return state;}, set state(v){state=v;},
    get ai(){return ai;}, set ai(v){ai=v;},
    get persisted(){return persisted;}, set persisted(v){persisted=v;},
    get revision(){return revision;}, set revision(v){revision=v;},
    setRoute(v){route=v;}
  };`;
  vm.runInNewContext(appSource.replace(/\nboot\(\);\s*$/, '\n') + exposed, context, { filename: 'app.js' });
  return { h: context.__harness, context, elements };
}

function draft(answer = '') {
  const card = bank.find(c => c.id === 'api-101');
  const d = { answer, revealed: [], clarifications: [], twist: false, mode: 'quick', started: 1, referenceSeen: false, pending: null, casePhase: 'requirements' };
  Workbench.ensure(d, card);
  Requirements.ensure(d);
  return { card, d };
}

function requirementsReview() {
  return { summary: 'Проверьте источник ограничения.', findings: [{ kind: 'missing', severity: 'minor', entryIds: ['req-1'], message: 'Не хватает правила отказа.', suggestion: 'Уточните поведение при отказе.' }] };
}
function addEntry(d, type, text) {
  d.requirements.entries.push({ id: `req-${d.requirements.entries.length + 1}`, type, text, status: 'confirmed', source: { kind: 'brief', index: 0 }, history: [] });
}

async function testQuestionNeedsNoArchitectureAnswerAndPreparedFactIsNotAutoConfirmed() {
  const calls = [];
  const app = makeApp(async (url, options) => {
    calls.push({ url, body: options?.body && JSON.parse(options.body) });
    return { ok: true, async json() { return url === '/api/state' ? { revision: 1 } : {}; } };
  });
  const { card, d } = draft('');
  app.h.state.drafts[card.id] = d;
  app.h.ai = true;
  app.h.persisted = JSON.stringify(app.h.state);
  await app.h.startJob(card, d, 'question', 'Какой контракт у API?');
  const req = calls.find(c => c.url === '/api/jobs')?.body;
  assert.ok(req, 'a question can be sent before writing an architecture answer');
  assert.equal(req.kind, 'question');
  assert.equal(app.h.state.attempts.length, 0, 'an interview question is not a completed attempt');

  const fresh = makeApp();
  const target = draft('');
  fresh.h.state.drafts[target.card.id] = target.d;
  const bind = Requirements.bind;
  Requirements.bind = () => {};
  try { fresh.h.bindInterview(target.card, target.d); } finally { Requirements.bind = bind; }
  const fact = target.card.facts[0];
  fresh.context.document.getElementById('question').value = fact.question;
  const bindAgain = Requirements.bind;
  Requirements.bind = () => {};
  try { fresh.context.document.getElementById('ask').onclick(); } finally { Requirements.bind = bindAgain; }
  await Promise.resolve();
  assert.equal(target.d.clarifications.length, 1, 'prepared facts are added to the dialogue');
  assert.equal(target.d.requirements.entries.length, 0, 'a prepared answer is never treated as user-confirmed requirement');
}

async function testRequirementsAloneDoNotCompleteArchitecture(){
  const calls=[],app=makeApp(async(url,options)=>{calls.push(url);return {ok:true,async json(){return {revision:1};}};});
  const {card,d}=draft('');addEntry(d,'functional','Система сохраняет заявку и возвращает её идентификатор.');app.h.state.drafts[card.id]=d;app.h.ai=true;
  await app.h.startJob(card,d,'review');assert.equal(calls.includes('/api/jobs'),false);assert.equal(d.pending,null);
}

async function testQuestionDraftRestoredWhenSaveFails() {
  const app = makeApp(async () => ({ ok: false, status: 503, async json() { return { error: 'offline' }; } }));
  const { card, d } = draft('');
  d.requirements.questionDraft = 'Где проверяется право на объект?';
  app.h.state.drafts[card.id] = d;
  app.h.ai = true;
  app.h.persisted = JSON.stringify(app.h.state);
  await app.h.startJob(card, d, 'question', d.requirements.questionDraft);
  assert.equal(d.pending, null);
  assert.equal(d.requirements.questionDraft, 'Где проверяется право на объект?');
}

async function testQuestionDraftRestoredWhenServerRejectsJob() {
  const app = makeApp(async url => url === '/api/jobs'
    ? { ok: false, status: 400, async json() { return { error: 'invalid request' }; } }
    : { ok: true, async json() { return { revision: 1 }; } });
  const { card, d } = draft('');
  d.requirements.questionDraft = 'Что произойдёт при повторе запроса?';
  app.h.state.drafts[card.id] = d;
  app.h.ai = true;
  app.h.persisted = JSON.stringify(app.h.state);
  await app.h.startJob(card, d, 'question', d.requirements.questionDraft);
  assert.equal(d.pending, null);
  assert.equal(d.requirements.questionDraft, 'Что произойдёт при повторе запроса?');
}

async function testPendingRequirementsReviewDoesNotCreateAttemptAndCapturesSnapshot() {
  let pollCount = 0;
  let submitted;
  const app = makeApp(async (url, options) => {
    if (url === '/api/state') return { ok: true, async json() { return { revision: 1 }; } };
    if (url === '/api/jobs') { submitted = JSON.parse(options.body); return { ok: true, async json() { return {}; } }; }
    if (url.startsWith('/api/jobs/')) {
      pollCount++;
      return { ok: true, async json() { return pollCount === 1 ? { status: 'running' } : { status: 'succeeded', result: requirementsReview() }; } };
    }
    throw Error(`Unexpected request ${url}`);
  });
  const { card, d } = draft('');
  addEntry(d, 'fact', 'Бронирование атомарно.');
  const capturedSignature = Requirements.signature(d);
  app.h.state.drafts[card.id] = d;
  app.h.ai = true;
  app.h.persisted = JSON.stringify(app.h.state);
  await app.h.startJob(card, d, 'requirements');
  assert.equal(submitted.kind, 'requirements');
  assert.equal(submitted.requirements.entries.length, 1, 'review receives the captured requirements board');
  assert.equal(app.h.state.attempts.length, 0, 'reviewing requirements does not count as architecture practice');
  d.requirements.entries[0].text = 'Edited while review is pending.';
  await app.h.pollJob(card, d, submitted.id);
  for (let i = 0; i < 20 && d.pending; i++) await new Promise(resolve => setImmediate(resolve));
  assert.equal(app.h.state.attempts.length, 0);
  assert.equal(d.requirements.review?.basedOn, capturedSignature);
  assert.match(Requirements.html(card, d), /req-ai-review is-stale/);
}

async function testStaleRequirementsResultIsNotPresentedAsCurrent() {
  const app = makeApp(async url => ({ ok: true, async json() { return url.startsWith('/api/jobs/') ? { status: 'succeeded', result: requirementsReview() } : { revision: 1 }; } }));
  const { card, d } = draft('');
  addEntry(d, 'fact', 'Исходная запись.');
  const snapshot = structuredClone(d);
  const id = 'stale-review';
  d.pending = { id, kind: 'requirements', snapshot, started: 1 };
  d.requirements.entries[0].text = 'Изменённая запись.';
  app.h.state.drafts[card.id] = d;
  await app.h.pollJob(card, d, id);
  // The result may be retained with its snapshot signature, but it must not appear current after edits.
  assert.match(Requirements.html(card, d), /req-ai-review is-stale/, 'changed board is visibly marked as having a stale review');
}

function testRevisionPreservesRequirementsWithoutDuplicatingAnswer() {
  const app = makeApp();
  const { card, d } = draft('Свободный ответ.');
  addEntry(d, 'functional', 'Запрос можно повторить безопасно.');
  const answer = app.h.answerFor(d, card);
  app.h.state.attempts.push({
    id: 'attempt-req', cardId: card.id, cardSnapshot: structuredClone(card), day: '2026-11-01', created: '2026-11-01T10:00:00.000Z',
    answer, rawAnswer: d.answer, requirements: structuredClone(d.requirements), training: structuredClone(d.training),
    mode: d.mode, revealed: [], clarifications: [], twist: false, referenceSeen: false, source: 'self', score: 75, review: null, minutes: 5,
  });
  app.h.state.drafts[card.id] = d;
  const bind = Requirements.bind;
  Requirements.bind = () => {};
  app.context.location.hash='#history';
  try { app.h.beginRevision('attempt-req'); } finally { Requirements.bind = bind; }
  const revised = app.h.state.drafts[card.id];
  const revisedAnswer = app.h.answerFor(revised, card);
  assert.equal(revised.casePhase,'solution','revision returns to architecture editor');
  assert.equal(revised.requirements.entries.length, 1);
  assert.equal((revisedAnswer.match(/Запрос можно повторить безопасно\./g) || []).length, 1);
  assert.equal(revisedAnswer, answer);
}

function testPersistenceAndPhaseControls() {
  const app = makeApp();
  const { card, d } = draft('');
  d.requirements.questionDraft = 'Что происходит при повторной отправке?';
  app.h.state.drafts[card.id] = d;
  const reloaded = Core.validate(JSON.parse(JSON.stringify(app.h.state)), bank);
  assert.equal(reloaded.drafts[card.id].requirements.questionDraft, d.requirements.questionDraft);
  assert.match(app.h.caseView(card.id), /data-case-phase="requirements"/);
  assert.match(app.h.caseView(card.id), /data-case-phase="solution"/);
  assert.match(app.h.caseView(card.id), /data-req-new/);
  assert.doesNotMatch(app.h.caseView(card.id), /data-compose-source/, 'source selector is hidden until editor opens');
  assert.doesNotThrow(() => Core.validate({ ...Core.initial(), drafts: { [card.id]: { answer: '', revealed: [], clarifications: [], twist: false, mode: 'quick' } } }, bank), 'legacy draft without requirements metadata remains valid');
}

function testRequirementSourcesPointToVisibleTargetsAndEmptyBoardExplainsNextStep() {
  const app = makeApp();
  const { card, d } = draft('');
  d.clarifications.push({ question: 'Как определяется право?', answer: 'По организации пользователя.', source: 'ai', factIds: [] });
  addEntry(d, 'fact', 'Доступ проверяется по организации пользователя.');
  d.requirements.entries[0].source = { kind: 'clarification', index: 0 };
  const markup = Requirements.html(card, d);
  assert.match(markup, /href="#req-source-clarification-0"/);
  assert.match(markup, /id="req-source-clarification-0"/);
  const empty = draft('');
  const emptyMarkup = Requirements.html(empty.card, empty.d);
  assert.match(emptyMarkup, /Пока нет записей/);
  assert.match(emptyMarkup, /Пока нет записей/);
  assert.doesNotThrow(() => Requirements.setReview(empty.d, { summary: 'По пустой доске пока нечего сопоставлять.', findings: [] }, Requirements.signature(empty.d)), 'an empty/complete review may legitimately have no findings');
}

function testSourceLinkInterceptScrollsWithoutNavigatingAway() {
  const target = { scrolled: false, scrollIntoView(options) { this.scrolled = options?.behavior === 'smooth'; } };
  let clickHandler;
  let prevented = false;
  const anchor = {
    getAttribute(name) { return name === 'href' ? '#req-source-clarification-0' : null; },
    addEventListener(event, fn) { if (event === 'click') clickHandler = fn; },
  };
  const board = {
    querySelectorAll(selector) { return selector === 'a[href^="#req-source-"]' ? [anchor] : []; },
    querySelector() { return null; },
  };
  const previousDocument = global.document;
  global.document = {
    querySelector(selector) { return selector === '.req-board' ? board : null; },
    getElementById(id) { return id === 'req-source-clarification-0' ? target : null; },
  };
  try {
    const { card, d } = draft('');
    Requirements.bind(card, d);
    assert.equal(typeof clickHandler, 'function', 'source anchor click handler is bound');
    clickHandler({ preventDefault() { prevented = true; } });
    assert.equal(prevented, true, 'hash navigation is prevented so the case route remains active');
    assert.equal(target.scrolled, true, 'the matching source is scrolled into view');
  } finally { global.document = previousDocument; }
}

(async () => {
  await testQuestionNeedsNoArchitectureAnswerAndPreparedFactIsNotAutoConfirmed();
  await testRequirementsAloneDoNotCompleteArchitecture();
  await testQuestionDraftRestoredWhenSaveFails();
  await testQuestionDraftRestoredWhenServerRejectsJob();
  await testPendingRequirementsReviewDoesNotCreateAttemptAndCapturesSnapshot();
  await testStaleRequirementsResultIsNotPresentedAsCurrent();
  testRevisionPreservesRequirementsWithoutDuplicatingAnswer();
  testPersistenceAndPhaseControls();
  testRequirementSourcesPointToVisibleTargetsAndEmptyBoardExplainsNextStep();
  testSourceLinkInterceptScrollsWithoutNavigatingAway();
  process.stdout.write('10 requirements client regression groups passed\n');
})().catch(error => { console.error(error); process.exitCode = 1; });
