import base64, json, os, tempfile, unittest
_tmp=tempfile.TemporaryDirectory();os.environ['ARCH_TRAINER_DB']=_tmp.name+'/test.sqlite3';os.environ['ARCH_TRAINER_PORT']='18783'
import server as m

def training():
    return {'version':1,'editor':'stages','stage':0,'sections':{k:'' for k in ('requirements','boundaries','data','flow','resilience','tradeoffs')},'diagram':{'nodes':[],'edges':[],'image':None},'defense':[],'revisionOf':None,'revisionNotes':''}

class V2Tests(unittest.TestCase):
    def test_legacy_state_still_valid(self):
        s={'version':1,'attempts':[],'drafts':{},'plans':{},'settings':{'goal':3,'mode':'quick','theme':'light'}}
        m.validate_state(s)
        s['settings']['practiceFormat']='micro';m.validate_state(s)
        s['settings']['practiceFormat']='invalid'
        with self.assertRaises(ValueError): m.validate_state(s)

    def test_optional_training_valid_and_invalid_image(self):
        t=training();t['diagram']['image']={'name':'sketch.png','mime':'image/png','dataUrl':'data:image/png;base64,AAAA'}
        # Tiny structurally valid PNG header with bounded dimensions.
        png=b'\x89PNG\r\n\x1a\n'+b'\x00\x00\x00\x0dIHDR'+(2).to_bytes(4,'big')+(2).to_bytes(4,'big')+b'\x08\x02\x00\x00\x00'+b'\x00'*4
        t['diagram']['image']['dataUrl']='data:image/png;base64,'+base64.b64encode(png).decode()
        m.validate_training(t)
        t['diagram']['image']['dataUrl']='data:image/png;base64,'+base64.b64encode(b'<svg xmlns="http://www.w3.org/2000/svg"/>').decode()
        with self.assertRaises(ValueError): m.validate_training(t)

    def test_comparison_rejects_hallucinated_evidence(self):
        with self.assertRaises(ValueError): m.validate_comparison({'resolved':[{'issue':'timeout','evidence':'never said'}],'remaining':[],'regressions':[]},'new answer')
        self.assertTrue(m.validate_comparison({'resolved':[{'issue':'timeout','evidence':'retry twice'}],'remaining':[],'regressions':[]},'retry twice'))

    def test_wrong_card_baseline_rejected_before_ai(self):
        card_ids=list(m.BANK)
        if len(card_ids)<2: self.skipTest('need two cards')
        attempt={'id':'saved-attempt','cardId':card_ids[1]}
        # Test the exact ownership predicate used before job creation without touching any real database.
        saved={'attempts':[attempt]}
        self.assertIsNone(m.resolve_baseline(saved,'saved-attempt',card_ids[0]))
        self.assertEqual(m.resolve_baseline(saved,'saved-attempt',card_ids[1]),attempt)
        calls=[];old=m.adapter;m.adapter=lambda *a,**k:calls.append(a)
        try:
            with self.assertRaises(ValueError): m.validate_job_baseline({'kind':'review','cardId':card_ids[0],'baselineId':'saved-attempt'},saved)
            with self.assertRaises(ValueError): m.validate_job_baseline({'kind':'review','cardId':card_ids[1],'baselineId':'saved-attempt','_baselineSnapshot':attempt},saved)
            self.assertEqual(calls,[])
        finally:m.adapter=old

    def test_null_review_baseline_is_safe_and_passes_previous_comments(self):
        card=next(iter(m.BANK.values()));answer='Ответ содержит конкретную цитату.';captured=[]
        baseline={'id':'base-1','cardId':card['id'],'answer':'Старый ответ','review':None,'revealed':[]}
        m.init()
        with m.connect() as db:
            db.execute('INSERT OR REPLACE INTO state VALUES(1,1,?)',(json.dumps({'attempts':[baseline]}),))
            db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?,?,?)',('job-1','digest','running','{}',None,None,0))
        old=m.adapter
        def mock(path,payload=None,timeout=5):
            data=json.loads(payload['messages'][1]['content']);captured.append(data)
            result={'summary':'Хорошо','criteria':[{'id':c['id'],'score':2,'evidence':answer,'feedback':'Обоснование'} for c in card['rubric']],'strengths':[],'nextSteps':[],'comparison':{'resolved':[],'remaining':[],'regressions':[]}}
            return {'done':True,'model':m.MODEL,'message':{'content':json.dumps(result)}}
        m.adapter=mock
        newer=dict(baseline,answer='Updated state after job was queued')
        with m.connect() as db: db.execute('UPDATE state SET body=? WHERE id=1',(json.dumps({'attempts':[newer]}),))
        try:m.perform('job-1',{'cardId':card['id'],'kind':'review','answer':answer,'baselineId':'base-1','_baselineSnapshot':baseline,'revealed':[],'twist':False,'clarifications':[]})
        finally:m.adapter=old
        self.assertEqual(captured[0]['previousAttempt']['comments'],[])
        self.assertEqual(captured[0]['previousAttempt']['answer'],'Старый ответ')
        self.assertEqual(captured[0]['exerciseFormat'],card.get('format','full'))

if __name__=='__main__': unittest.main()
