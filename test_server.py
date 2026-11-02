import importlib.util,json,os,pathlib,tempfile,threading,time,unittest,urllib.request,urllib.error,uuid
ROOT=pathlib.Path(__file__).parent
TEMP=tempfile.TemporaryDirectory();os.environ['ARCH_TRAINER_DB']=TEMP.name+'/test.sqlite3';os.environ['ARCH_TRAINER_PORT']='18782'
spec=importlib.util.spec_from_file_location('trainer',ROOT/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  m.init();cls.server=m.http.server.ThreadingHTTPServer(('127.0.0.1',18782),m.Handler);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
 def request(self,path,body=None,origin=None):
  headers={'X-Trainer':'1','Content-Type':'application/json'}
  if origin:headers['Origin']=origin
  req=urllib.request.Request('http://127.0.0.1:18782'+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
  try:
   with urllib.request.urlopen(req) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def test_state_conflict(self):
  state={'version':1,'attempts':[],'drafts':{},'plans':{},'settings':{'goal':3,'mode':'quick','theme':'light'}}
  n,d=self.request('/api/state');rev=d['revision']
  self.assertEqual(self.request('/api/state',{'revision':rev,'state':state})[0],200)
  self.assertEqual(self.request('/api/state',{'revision':rev,'state':state})[0],409)
 def test_origin(self):self.assertEqual(self.request('/api/state',{},'https://evil.test')[0],403)
 def test_paths(self):
  for path in ('/.state/practice.sqlite3','/data/api.json','/scenarios.py'):
   self.assertEqual(self.request(path)[0],404)
 def test_reject_bad_job(self):self.assertEqual(self.request('/api/jobs',{'cardId':'missing'})[0],400)
 def test_review_quotes(self):
  card=next(iter(m.BANK.values()));r={'summary':'ok','criteria':[{'id':c['id'],'score':3,'evidence':'Нет такой цитаты','feedback':'Подходит критерию'} for c in card['rubric']],'strengths':[],'nextSteps':[]}
  self.assertRaises(ValueError,m.validate_review,r,card,'Другой ответ')
  for c in r['criteria']:c['evidence']='Другой ответ'
  self.assertEqual(m.validate_review(r,card,'Другой ответ'),r)
 def test_incomplete_state_rejected(self):
  self.assertRaises(ValueError,m.validate_state,{'version':1,'attempts':[],'drafts':{},'plans':{},'settings':{}})
 def test_null_review_rejected(self):
  card=next(iter(m.BANK.values()));r={'summary':'Нет оценки','criteria':[{'id':c['id'],'score':None,'evidence':'','feedback':'не применимо'} for c in card['rubric']],'strengths':[],'nextSteps':[]}
  self.assertRaises(ValueError,m.validate_review,r,card,'Ответ')
 def test_grader_does_not_receive_hidden_facts(self):
  old=m.adapter;captured=[]
  card=next(iter(m.BANK.values()));jid=str(uuid.uuid4());answer='Это тестовый ответ с конкретным решением.'
  with m.connect() as db:db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(jid,'digest','running','{}',None,None,0))
  def mock(path,payload=None,timeout=5):
   captured.append(json.loads(payload['messages'][1]['content']))
   out={'summary':'Проверка','criteria':[{'id':c['id'],'score':2,'evidence':answer,'feedback':'Обоснование'} for c in card['rubric']],'strengths':['пример'],'nextSteps':['доработать']}
   return {'done':True,'model':m.MODEL,'message':{'content':json.dumps(out)}}
  m.adapter=mock
  try:m.perform(jid,{'cardId':card['id'],'kind':'review','answer':answer,'revealed':[],'clarifications':[],'twist':False})
  finally:m.adapter=old
  self.assertEqual(captured[0]['revealedFacts'],[]);self.assertNotIn('fullReference',captured[0]);self.assertTrue(all('expectation' not in r for r in captured[0]['rubric']))
 def test_job_idempotency(self):
  old=m.adapter
  def mock(path,payload=None,timeout=5):return {'done':True,'model':m.MODEL,'message':{'content':json.dumps({'answer':'В кейсе не задано.','factIds':[]})}}
  m.adapter=mock
  try:
   req={'id':str(uuid.uuid4()),'kind':'question','cardId':next(iter(m.BANK)),'question':'Каков срок?','revealed':[],'clarifications':[]}
   self.assertIn(self.request('/api/jobs',req)[0],(200,202));self.assertEqual(self.request('/api/jobs',req)[0],200)
   req['question']='Другой вопрос';self.assertEqual(self.request('/api/jobs',req)[0],409)
   for _ in range(100):
    if self.request('/api/jobs/'+req['id'])[1]['status']!='running':break
    time.sleep(.01)
   self.assertEqual(self.request('/api/jobs/'+req['id'])[1]['status'],'succeeded')
  finally:m.adapter=old
if __name__=='__main__':unittest.main()
