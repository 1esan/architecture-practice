"""Deterministic evaluator scope and result-shape checks (no model calls)."""
import importlib.util, json, pathlib, unittest

ROOT=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('trainer_eval_v3',ROOT/'server.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
cal_spec=importlib.util.spec_from_file_location('calibrate_evaluator',ROOT/'calibrate_evaluator.py')
cal=importlib.util.module_from_spec(cal_spec);cal_spec.loader.exec_module(cal)

class EvaluationV3Tests(unittest.TestCase):
    def test_hidden_expectation_never_enters_evaluation_prompt(self):
        card=next(iter(m.BANK.values()))
        card['rubric'][0]['expectation']='SECRET: undisclosed numeric threshold 999'
        card['rubric'][0]['publicExpectation']='Check whether repeated commands are safe.'
        card['rubric'][0]['factIds']=['retry']
        hidden=m.evaluation_rubric(card,[])
        self.assertFalse(hidden[0]['active'])
        self.assertEqual(hidden[0]['publicExpectation'],'Check whether repeated commands are safe.')
        self.assertNotIn('SECRET',json.dumps(hidden))
        self.assertTrue(m.evaluation_rubric(card,['retry'])[0]['active'])

    def test_unreleased_criterion_must_have_null_score(self):
        card=next(iter(m.BANK.values())); card['rubric'][0]['factIds']=['not-revealed']
        for r in card['rubric'][1:]:r['factIds']=[]
        answer='Предлагаю атомарно сохранить результат.'
        criteria=[{'id':r['id'],'score':None if i==0 else 2,'evidence':'' if i==0 else answer,'feedback':'Не применимо к текущим вводным' if i==0 else 'Решение закрывает часть требования'} for i,r in enumerate(card['rubric'])]
        result={'summary':'Рабочее решение','criteria':criteria,'strengths':[],'nextSteps':[]}
        self.assertIs(m.validate_review(result,card,answer,[]),result)
        criteria[0].update(score=2,evidence=answer,feedback='Оцениваемый вывод')
        with self.assertRaises(ValueError):m.validate_review(result,card,answer,[])

    def test_finding_requires_stable_mapping_and_grounded_evidence(self):
        card=next(iter(m.BANK.values()));answer='Повтор запускает операцию заново.'
        result={'summary':'Есть риск','criteria':[{'id':r['id'],'score':1,'evidence':answer,'feedback':'Повтор может создать дубликат операции'} for r in card['rubric']],'strengths':[],'nextSteps':[],'findings':[{'id':'F1','criterionId':card['rubric'][0]['id'],'severity':'major','kind':'contradiction','statement':'Повтор повторно выполняет операцию','evidence':answer,'rationale':'Это может привести к дублированию результата.','optional':False}]}
        m.validate_review(result,card,answer)
        result['findings'][0]['evidence']='Цитаты в ответе нет'
        with self.assertRaises(ValueError):m.validate_review(result,card,answer)
        result['findings'][0]['evidence']=answer;result['findings'][0]['criterionId']='unknown'
        with self.assertRaises(ValueError):m.validate_review(result,card,answer)

    def test_calibration_cases_are_manual_guidance_not_model_ground_truth(self):
        cases=json.loads((ROOT/'evaluation_calibration.json').read_text())
        self.assertEqual({x['name'] for x in cases},{'weak-evidence-only','strong-reasoned','contradictory-claims','reasonable-alternative','unrevealed-fact-does-not-apply'})
        self.assertTrue(all('grading_guidance' in x and 'expected_score' in x and 'evaluation_context' in x for x in cases))

    def test_design_tools_property_schema_and_optional_legacy(self):
        empty={'version':1,'capacity':{k:'' for k in ('requestsPerDay','peakFactor','latencyMs','eventBytes','retentionDays','replicas','overhead','arrivalRps','serviceRps','outageMinutes','assumptions')},'nodes':{},'edges':{},'risks':{k:'' for k in ('security','recovery','observability','migration','cost')}}
        m.validate_design_tools(empty)
        card=next(iter(m.BANK.values()))
        # Existing drafts without designTools remain valid.
        d={'answer':'','mode':'quick','twist':False,'revealed':[],'clarifications':[]}
        m.validate_state({'version':1,'attempts':[],'drafts':{card['id']:d},'plans':{},'settings':{'goal':3,'mode':'quick','theme':'light'}})
        d['designTools']=empty
        m.validate_state({'version':1,'attempts':[],'drafts':{card['id']:d},'plans':{},'settings':{'goal':3,'mode':'quick','theme':'light'}})
        bad=json.loads(json.dumps(empty));bad['nodes']={'n1':{'owner':'','trust':'mystery','failureDomain':''}}
        with self.assertRaises(ValueError):m.validate_design_tools(bad)
        bad=json.loads(json.dumps(empty));bad['capacity']['assumptions']='x'*2001
        with self.assertRaises(ValueError):m.validate_design_tools(bad)

    def test_calibration_does_not_leak_manual_expected_labels(self):
        import calibrate_evaluator as runner
        case=json.loads((ROOT/'evaluation_calibration.json').read_text())[0]
        payload=json.loads(runner.build_messages(case)[1]['content'])
        for name in ('grading_guidance','expected_score','expected_behavior','name'):
            self.assertNotIn(name,payload)

    def test_question_result_fact_ids_are_known_and_unique(self):
        card=next(iter(m.BANK.values()));fact=card['facts'][0]['id']
        self.assertEqual(m.validate_question_result({'answer':'Условие уточнено.','factIds':[fact]},card)['factIds'],[fact])
        for ids in (["not-a-fact"],[fact,fact],[{}]):
            with self.subTest(ids=ids),self.assertRaises(ValueError):m.validate_question_result({'answer':'Условие уточнено.','factIds':ids},card)

    def test_live_calibration_runner_is_opt_in_and_payload_is_single_criterion(self):
        cases=json.loads((ROOT/'evaluation_calibration.json').read_text())
        self.assertEqual(len(cases),5)
        for case in cases:
            msgs=cal.build_messages(case)
            payload=json.loads(msgs[1]['content'])
            self.assertEqual(set(payload['criterion']),{'id','label','publicExpectation','severity','active'})
            self.assertIn('single-criterion',msgs[0]['content'])
            self.assertNotIn('fullReference',msgs[1]['content'])
        with self.assertRaises(ValueError):cal.validate_sample(cases[0],{'score':3,'evidence':cases[0]['answer'],'feedback':'Looks good because evidence.'})
        with self.assertRaises(ValueError):cal.validate_sample(cases[4],{'score':0,'evidence':'','feedback':'Not applicable to current inputs.'})

if __name__=='__main__':unittest.main()
