import copy,json,pathlib,tempfile,unittest
from unittest.mock import patch
import server as s
import scenarios

class FocusedTests(unittest.TestCase):
 def test_state_accepts_focused_answer_and_rejects_unknown_version(self):
  state={'version':1,'attempts':[],'drafts':{'api-001':{'focusedVersion':1,'answer':'','revealed':[],'clarifications':[],'mode':'quick','twist':False}},'plans':{},'settings':{'goal':3,'mode':'quick','theme':'light'}}
  s.validate_state(state)
  for invalid in [2,True,'1']:
   state['drafts']['api-001']['focusedVersion']=invalid
   with self.assertRaises(ValueError):s.validate_state(state)
 def test_review_contract_is_scoped_and_does_not_use_hidden_reference(self):
  for pool in ['api','integration']:
   instruction=s.focused_review_instructions({'pool':pool})
   self.assertTrue(instruction)
   self.assertIn('Не требуй',instruction)
  self.assertEqual(s.focused_review_instructions({'pool':'design'}),'')
 def test_real_review_request_contains_focused_answer_but_no_private_dossier(self):
  answer='POST /reservations\nroomId: string, required\n201 {"id":"r1"}\n409 slot occupied'
  request={'kind':'review','cardId':'api-001','answer':answer,'revealed':[],'clarifications':[],'twist':False}
  card=s.BANK['api-001'];result={'summary':'Проверен контракт','criteria':[{'id':r['id'],'score':3,'evidence':'POST /reservations','feedback':'Проверен контракт операции'} for r in card['rubric']],'findings':[],'strengths':[],'nextSteps':[]}
  captured=[]
  def adapter(path,payload,timeout):
   captured.append(payload)
   return {'done':True,'model':'fake','message':{'content':json.dumps(result)}}
  with tempfile.TemporaryDirectory() as tmp,patch.object(s,'DB',pathlib.Path(tmp)/'state.db'),patch.object(s,'adapter',adapter):
   s.init()
   with s.connect() as db:db.execute("INSERT INTO jobs(id,digest,status,request,created) VALUES('focused-test','digest','running','{}',0)")
   s.perform('focused-test',request)
   with s.connect() as db:self.assertEqual(db.execute("SELECT status FROM jobs WHERE id='focused-test'").fetchone()[0],'succeeded')
  payload=json.loads(captured[0]['messages'][1]['content'])
  self.assertEqual(payload['answer'],answer);self.assertEqual(payload['revealedFacts'],[])
  self.assertNotIn('privateContext',payload);self.assertNotIn('reference',payload)
  self.assertIn('Режим «Проектирование API»',captured[0]['messages'][0]['content'])
 def test_focused_banks_have_no_hidden_fact_in_public_contract(self):
  for c in s.BANK.values():
   if c['pool'] not in ['api','integration']:continue
   public=' '.join([c['brief'],*c['deliverables'],*[r['publicExpectation'] for r in c['rubric']]])
   for f in c['facts']:
    if f['id'].startswith('ctx-'):continue
    self.assertNotIn(f['answer'],public,c['id'])
   self.assertNotRegex(public,r'(?i)TODO|TBD|контракт уточняется|API / событие Kafka')

class FocusedContentRegressions(unittest.TestCase):
 def card(self,id):
  for file in ['api','integration','micro']:
   for c in json.loads(pathlib.Path(__file__).with_name('data').joinpath(file+'.json').read_text()):
    if c['id']==id:return c
  self.fail(id)
 def test_range_download_matches_3gb_file_and_http_semantics(self):
  c=self.card('api-026');ref=' '.join(c['reference']['decisions'])
  self.assertIn('bytes 0-1048575/3000000000',ref);self.assertIn('Content-Length: 1048576',ref)
  self.assertIn('HTTP 416',ref);self.assertIn('HTTP 200',ref);self.assertNotIn('HTTP 422',ref)
  self.assertNotIn('operation key',' '.join(f['answer'] for f in c['facts']))
 def test_signature_direction_and_async_ids_are_distinct(self):
  webhook=self.card('api-017');self.assertIn('отправитель',' '.join(f['answer'] for f in webhook['facts']).lower())
  ref=' '.join(self.card('api-112')['reference']['decisions'])
  self.assertIn('Idempotency-Key: export-request-42',ref);self.assertIn('"operationId":"operation-42"',ref)
 def test_quote_is_not_paginated_and_has_private_cache_policy(self):
  c=self.card('api-052');ref=json.dumps(c['reference'],ensure_ascii=False)
  self.assertNotIn('nextCursor',ref);self.assertIn('private, no-cache',ref)
  self.assertIn('2026-11-02T10:00:00Z',ref);self.assertIn('2026-11-02T10:10:00Z',ref)
 def test_micro_scope_is_short_and_dossiers_have_no_service_placeholders(self):
  for file in ['api','integration','micro']:
   for c in json.loads(pathlib.Path(__file__).with_name('data').joinpath(file+'.json').read_text()):
    if c['pool'] not in ['api','integration']:continue
    if c.get('format')=='micro':self.assertLessEqual(len(c['deliverables']),3,c['id'])
    for a in c['privateContext']['areas']:
     self.assertNotRegex(a['answer'],r'(?i)\bTODO\b|\bTBD\b|контракт уточняется|в этой карте|ученик должен|POST статусы',c['id'])
