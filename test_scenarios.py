"""Private scenario coverage, exposure boundaries, and progressive question provenance."""
import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest
import scenarios
import requirements_backend

ROOT=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('scenario_test_server',ROOT/'server.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

class ScenariosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cards=[c for name in ('api','integration','design','micro') for c in json.loads((ROOT/'data'/f'{name}.json').read_text(encoding='utf-8'))]

    def test_every_card_has_valid_private_context(self):
        self.assertEqual(len(self.cards),216)
        for card in self.cards:
            with self.subTest(card=card['id']):
                value=scenarios.validate_context(card)
                self.assertIsNotNone(value)
                self.assertGreaterEqual(len({a['answer'] for a in value['areas']}),4)
                self.assertTrue(any(a['id'] in ('ctx-actors','ctx-process','ctx-trigger') for a in value['areas']))

    def test_public_bank_does_not_include_hidden_dossier(self):
        for c in self.cards:
            public=scenarios.public_card(c)
            self.assertNotIn('privateContext',public)
            self.assertEqual(public['facts'],c['facts'])
            self.assertNotIn('ctx-actors',json.dumps(public,ensure_ascii=False))
        source=(ROOT/'index.html').read_text(encoding='utf-8')
        bank=json.loads(source.split('const BANK=',1)[1].split(';</script>',1)[0])
        self.assertEqual(len(bank),216)
        self.assertTrue(all('privateContext' not in c for c in bank))
        for c in bank:self.assertTrue(all(not f['id'].startswith('ctx-') for f in c['facts']))

    def test_expansion_preserves_existing_fact_values_and_ids(self):
        for c in self.cards:
            before=copy.deepcopy(c);expanded=scenarios.expanded_card(c)
            self.assertEqual(c,before)
            self.assertEqual(expanded['facts'][:len(c['facts'])],c['facts'])
            self.assertEqual(len({f['id'] for f in expanded['facts']}),len(expanded['facts']))
            self.assertGreater(len(expanded['facts']),len(c['facts']))
        legacy={'id':'old','facts':[{'id':'f1','answer':'old answer'}]}
        self.assertEqual(scenarios.expanded_card(legacy),legacy)

    def test_questions_receive_actual_roles_but_grader_only_sees_exploration_topics(self):
        card=s.BANK['int-001'];actors=next(a for a in card['privateContext']['areas'] if a['id']=='ctx-actors')
        self.assertIn('администратор',actors['answer'].lower());self.assertIn('кассир',actors['answer'].lower())
        self.assertIn('вручную',actors['answer'].lower())
        self.assertIn(actors['id'],{f['id'] for f in card['facts']})
        board={'version':1,'entries':[],'review':None,'questionDraft':''}
        payload=requirements_backend.review_payload(card,{'revealed':[],'clarifications':[],'requirements':board})
        self.assertEqual(payload['revealedFacts'],[])
        self.assertNotIn(actors['answer'],json.dumps(payload,ensure_ascii=False))
        self.assertTrue(any(a['id']=='ctx-actors' and not a['explored'] for a in payload['discoveryAreas']))
        opened=requirements_backend.review_payload(card,{'revealed':['ctx-actors'],'clarifications':[],'requirements':board})
        self.assertTrue(any(a['id']=='ctx-actors' and a['explored'] for a in opened['discoveryAreas']))
        self.assertIn(actors['answer'],json.dumps(opened,ensure_ascii=False))

    def test_context_fact_ids_survive_state_and_question_validation(self):
        card=s.BANK['int-001'];s.validate_question_result({'answer':'Администратор проверяет файл.','factIds':['ctx-actors']},card)
        draft={'answer':'','mode':'quick','twist':False,'revealed':['ctx-actors'],'clarifications':[{'question':'Кто проверяет файл?','answer':'Администратор магазина.','source':'ai','factIds':['ctx-actors']}]}
        s.validate_state({'version':1,'attempts':[],'drafts':{'int-001':draft},'plans':{},'settings':{'goal':3,'mode':'quick','theme':'light'}})
        with self.assertRaises(ValueError):s.validate_question_result({'answer':'Неизвестно.','factIds':['ctx-nonexistent']},card)

    def test_customer_prompt_contains_fixed_dossier_without_reference_solution(self):
        with tempfile.TemporaryDirectory() as directory:
            old_db,old_adapter=s.DB,s.adapter;s.DB=pathlib.Path(directory)/'test.sqlite3';captured=[]
            s.init()
            with s.connect() as db:db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',('scenario-question','x','running','{}',None,None,0))
            def adapter(path,payload=None,timeout=5):
                captured.append(json.loads(payload['messages'][1]['content']))
                return {'done':True,'model':s.MODEL,'message':{'content':json.dumps({'answer':'Администратор магазина проверяет файл вручную.','factIds':['ctx-actors']})}}
            s.adapter=adapter
            try:
                s.perform('scenario-question',{'cardId':'int-001','kind':'question','question':'Кто сейчас проверяет файл?','clarifications':[],'revealed':[]})
                with s.connect() as db:
                    row=db.execute('select status,result from jobs').fetchone();self.assertEqual(row['status'],'succeeded')
                    self.assertEqual(json.loads(row['result'])['contextRevision'],scenarios.revision(s.BANK['int-001']))
            finally:s.DB,s.adapter=old_db,old_adapter
            self.assertTrue(any(f['id']=='ctx-actors' for f in captured[0]['facts']))
            self.assertNotIn('reference',captured[0]);self.assertNotIn('rubric',captured[0])

    def test_context_revision_and_duplicate_validation(self):
        c=copy.deepcopy(self.cards[0]);before=scenarios.revision(c)
        c['privateContext']['areas'][0]['answer']+=' Уточнённый процесс.'
        self.assertNotEqual(before,scenarios.revision(c))
        c['privateContext']['areas'].append(copy.deepcopy(c['privateContext']['areas'][0]))
        with self.assertRaises(ValueError):scenarios.validate_context(c)

    def test_design_catalog_does_not_get_unrelated_course_or_tenant_migration(self):
        c=next(c for c in self.cards if c['id']=='sys-011')
        actors=next(x['answer'] for x in c['privateContext']['areas'] if x['id']=='ctx-actors')
        process=next(x['answer'] for x in c['privateContext']['areas'] if x['id']=='ctx-process')
        self.assertNotRegex(actors+' '+process,r'курса|residency|control-plane|cutover')
        self.assertIn('центрального офиса',actors)

if __name__=='__main__':unittest.main()
