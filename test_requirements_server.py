import contextlib, io, json, os, tempfile, unittest, urllib.error
_tmp=tempfile.TemporaryDirectory();os.environ['ARCH_TRAINER_DB']=_tmp.name+'/requirements.sqlite3';os.environ['ARCH_TRAINER_PORT']='18784'
import server as m
import requirements_backend as rb


def board():
    return {'version':1,'entries':[{'id':'req-1','type':'functional','text':'Пользователь может отправить заявку.','status':'confirmed','source':{'kind':'brief','index':0},'history':[]}], 'review':None, 'questionDraft':''}


class RequirementsBackendTests(unittest.TestCase):
    def test_customer_reply_decoding_does_not_invent_provenance(self):
        value=m.decode_model_response('Этот параметр не задан. {"factIds":["load"]}','question')
        self.assertEqual(value,{'answer':'Этот параметр не задан.','factIds':['load']})
        self.assertEqual(m.decode_model_response('Параметр нужно согласовать.','question')['factIds'],[])
        self.assertEqual(m.decode_model_response('Сверяем `revision` и checksum.','question'),{'answer':'Сверяем `revision` и checksum.','factIds':[]})
        self.assertEqual(m.decode_model_response('```JSON\n{"answer":"Да","factIds":[]}\n```','question')['answer'],'Да')
        for raw in ('', '{"answer":', 'Текст {broken}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):m.decode_model_response(raw,'question')
        with self.assertRaises(ValueError):m.decode_model_response('Хорошие требования.','requirements')

    def test_question_decoder_accepts_common_wrapped_reply_shapes(self):
        self.assertEqual(m.decode_model_response('Срок не задан. — {"factIds":[]}','question'),{'answer':'Срок не задан.','factIds':[]})
        self.assertEqual(m.decode_model_response('Ответ заказчика: {"answer":"Да, можно.","factIds":["load"]}','question'),{'answer':'Да, можно.','factIds':['load']})
        self.assertEqual(m.decode_model_response('Ответ заказчика: {"answer":"Не задано.","factIds":[]}','question')['factIds'],[])
        wrapped='Заказчик уточнил: ```json\n{"answer":"Срок не задан.","factIds":[]}\n```'
        self.assertEqual(m.decode_model_response(wrapped,'question')['answer'],'Срок не задан.')
        # Do not salvage a valid nested object from a malformed JSON envelope.
        for raw in ('{"outer": broken, "inner":{"answer":"да","factIds":[]}}',
                    'Ответ: ```json\n{"answer":"да","factIds":[]}\n``` лишний текст'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):m.decode_model_response(raw,'question')
        # The strict review decoder must not inherit question's prose tolerance.
        with self.assertRaises(ValueError):m.decode_model_response('Разбор: {"summary":"ok"}','review')

    def test_failed_job_message_and_diagnostics_do_not_expose_exception_payload(self):
        card=next(iter(m.BANK.values()));m.init()
        secret='Bearer private-token; user prompt private text'
        with m.connect() as db:db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?,?,?)',('diag-question','d','running','{}',None,None,0))
        old=m.adapter
        def broken(*a,**k):raise RuntimeError(secret)
        output=io.StringIO();handler=m.DIAGNOSTICS.handlers[0];old_stream=handler.stream;handler.setStream(output);m.adapter=broken
        try:m.perform('diag-question',{'cardId':card['id'],'kind':'question','question':'Секретный запрос','revealed':[],'clarifications':[],'twist':False})
        finally:m.adapter=old;handler.setStream(old_stream)
        with m.connect() as db:row=db.execute('SELECT error FROM jobs WHERE id=?',('diag-question',)).fetchone()
        self.assertIn('Ответ заказчика не завершён',row['error'])
        self.assertIn('RuntimeError',output.getvalue());self.assertIn('traceback_frames',output.getvalue())
        self.assertNotIn(secret,output.getvalue());self.assertNotIn('Секретный запрос',output.getvalue())

    def test_http_error_message_is_specific_and_error_body_is_not_logged(self):
        card=next(iter(m.BANK.values()));m.init()
        with m.connect() as db:db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?,?,?)',('diag-http','d','running','{}',None,None,0))
        old=m.adapter
        def broken(*a,**k):raise urllib.error.HTTPError('http://127.0.0.1/private',503,'unavailable',{},io.BytesIO(b'Bearer private-token'))
        output=io.StringIO();handler=m.DIAGNOSTICS.handlers[0];old_stream=handler.stream;handler.setStream(output);m.adapter=broken
        try:m.perform('diag-http',{'cardId':card['id'],'kind':'review','answer':'мой закрытый ответ','revealed':[],'clarifications':[],'twist':False})
        finally:m.adapter=old;handler.setStream(old_stream)
        with m.connect() as db:row=db.execute('SELECT error FROM jobs WHERE id=?',('diag-http',)).fetchone()
        self.assertIn('HTTP 503',row['error']);self.assertNotIn('private-token',output.getvalue());self.assertNotIn('private',output.getvalue())

    def test_validation_reason_is_preserved_safely_and_diagnostics_include_stage_code(self):
        card=next(iter(m.BANK.values()));m.init()
        with m.connect() as db:db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?,?,?)',('diag-validation','d','running','{}',None,None,0))
        result={'answer':'Ответ есть.','factIds':['not-a-real-fact']}
        old=m.adapter
        m.adapter=lambda *a,**k:{'done':True,'model':m.MODEL,'message':{'content':json.dumps(result,ensure_ascii=False)}}
        output=io.StringIO();handler=m.DIAGNOSTICS.handlers[0];old_stream=handler.stream;handler.setStream(output)
        try:m.perform('diag-validation',{'cardId':card['id'],'kind':'question','question':'Что известно?','revealed':[],'clarifications':[],'twist':False})
        finally:m.adapter=old;handler.setStream(old_stream)
        with m.connect() as db:row=db.execute('SELECT error FROM jobs WHERE id=?',('diag-validation',)).fetchone()
        self.assertIn('неизвестную вводную',row['error'])
        self.assertIn('stage=validate',output.getvalue());self.assertIn('error_code=question_unknown_fact_ids',output.getvalue())

    def test_legacy_state_without_requirements_remains_valid(self):
        m.validate_state({'version':1,'attempts':[],'drafts':{},'plans':{},'settings':{'goal':3,'mode':'quick','theme':'light'}})

    def test_requirements_persist_in_draft_and_pending_snapshot(self):
        card=next(iter(m.BANK.values()));d={'answer':'','revealed':[],'clarifications':[],'twist':False,'mode':'quick','requirements':board()}
        d['pending']={'id':'job-1','kind':'requirements','snapshot':dict(d)}
        m.validate_state({'version':1,'attempts':[],'drafts':{card['id']:d},'plans':{},'settings':{'goal':3,'mode':'quick','theme':'light'}})

    def test_requirements_job_kind_is_accepted_and_requires_board(self):
        card=next(iter(m.BANK.values()))
        request={'cardId':card['id'],'kind':'requirements','answer':'requirementsreview','requirements':board(),'revealed':[],'clarifications':[]}
        self.assertIs(m.validate_job_request(request),request)
        del request['requirements']
        with self.assertRaises(ValueError):m.validate_job_request(request)

    def test_review_rejects_unknown_entry_reference(self):
        result={'summary':'Есть пробел.','findings':[{'kind':'missing','severity':'major','entryIds':['ghost'],'message':'Не задан результат.','suggestion':'Уточнить результат.'}]}
        with self.assertRaises(ValueError):rb.validate_requirements_review(result,{'req-1'})

    def test_general_missing_finding_can_have_no_entry_reference(self):
        result={'summary':'Доска пока пуста.','findings':[{'kind':'missing','severity':'major','entryIds':[],'message':'Не задано ни одного требования.','suggestion':'Добавить проверяемые требования по основным результатам.'}]}
        self.assertEqual(rb.validate_requirements_review(result,set()),result)

    def test_board_rejects_confirmed_assumptions_and_invalid_history_dates(self):
        b=board();b['entries'][0].update(type='assumption',status='confirmed')
        with self.assertRaises(ValueError):rb.validate_requirements(b)
        b=board();b['entries'][0]['history']=[{'text':'x','type':'functional','status':'confirmed','changedAt':'sometime'}]
        with self.assertRaises(ValueError):rb.validate_requirements(b)

    def test_job_and_saved_state_reject_dangling_clarification_source(self):
        card=next(iter(m.BANK.values()));b=board();b['entries'][0]['source']={'kind':'clarification','index':0}
        request={'cardId':card['id'],'kind':'requirements','answer':'requirementsreview','requirements':b,'revealed':[],'clarifications':[]}
        with self.assertRaises(ValueError):m.validate_job_request(request)
        d={'answer':'','revealed':[],'clarifications':[],'twist':False,'mode':'quick','requirements':b}
        with self.assertRaises(ValueError):m.validate_state({'version':1,'attempts':[],'drafts':{card['id']:d},'plans':{},'settings':{'goal':3,'mode':'quick','theme':'light'}})

    def test_review_prompt_contains_only_revealed_facts(self):
        card=next(iter(m.BANK.values()));secret=next((f for f in card['facts'] if f['id'] not in []),None)
        captured=[];old=m.adapter
        m.init()
        with m.connect() as db:db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?,?,?)',('review-1','d','running','{}',None,None,0))
        def mock(path,payload=None,timeout=5):
            captured.append(json.loads(payload['messages'][1]['content']))
            return {'done':True,'model':m.MODEL,'message':{'content':json.dumps({'summary':'Требования можно уточнить.','findings':[]})}}
        m.adapter=mock
        try:m.perform('review-1',{'cardId':card['id'],'kind':'requirements','answer':'requirementsreview','requirements':board(),'revealed':[],'clarifications':[],'twist':False})
        finally:m.adapter=old
        payload=captured[0]
        self.assertEqual(payload['revealedFacts'],[])
        self.assertNotIn('facts',payload);self.assertNotIn('fullReference',payload);self.assertNotIn('rubric',payload)
        if secret:self.assertNotIn(secret.get('answer','\0'),json.dumps(payload,ensure_ascii=False))

    def test_follow_up_question_receives_bounded_dialogue_history(self):
        card=next(iter(m.BANK.values()));captured=[];old=m.adapter
        m.init()
        with m.connect() as db:db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?,?,?)',('question-1','d','running','{}',None,None,0))
        def mock(path,payload=None,timeout=5):
            captured.append(json.loads(payload['messages'][1]['content']))
            return {'done':True,'model':m.MODEL,'message':{'content':'{"answer":"Параметр не задан.","factIds":[]}'} }
        m.adapter=mock
        try:
            m.perform('question-1',{'cardId':card['id'],'kind':'question','question':'А это обязательно?','revealed':[],'clarifications':[{'question':'Какой срок?','answer':'Срок — 3 дня.','source':'ai'}],'twist':False})
        finally:m.adapter=old
        self.assertEqual(captured[0]['history'],[{'question':'Какой срок?','answer':'Срок — 3 дня.'}])

    def test_oversized_latest_history_is_truncated_not_dropped(self):
        card=next(iter(m.BANK.values()));captured=[];old=m.adapter
        m.init()
        with m.connect() as db:db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?,?,?)',('question-2','d','running','{}',None,None,0))
        def mock(path,payload=None,timeout=5):
            captured.append(json.loads(payload['messages'][1]['content']))
            return {'done':True,'model':m.MODEL,'message':{'content':'{"answer":"Не задано.","factIds":[]}'} }
        m.adapter=mock
        try:
            m.perform('question-2',{'cardId':card['id'],'kind':'question','question':'Что уточнить?','revealed':[],'clarifications':[{'question':'q'*2000,'answer':'\x01'*8000}],'twist':False})
        finally:m.adapter=old
        self.assertEqual(len(captured[0]['history']),1)
        self.assertLessEqual(len(json.dumps(captured[0]['history'],ensure_ascii=False)),12000)

    def test_question_history_retains_all_fifty_pairs_within_limit(self):
        history=[{'question':f'question-{i}-'+'q'*2000,'answer':f'answer-{i}-'+'a'*8000} for i in range(50)]
        bounded=m.question_history(history)
        self.assertEqual(len(bounded),50)
        self.assertLessEqual(len(json.dumps(bounded,ensure_ascii=False).encode()),40000)
        self.assertTrue(all(row['question'] and row['answer'] for row in bounded))
        self.assertTrue(bounded[-1]['question'].startswith('question-49'))

if __name__=='__main__':unittest.main()
