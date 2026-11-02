"""Opt-in, isolated live calibration calls; writes only the calibration report."""
import argparse
import tempfile
import concurrent.futures
import datetime
import json
import pathlib
import sys

ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import server

FIXTURES=ROOT/'evaluation_calibration.json'

def read_content(envelope):
    if not isinstance(envelope,dict) or envelope.get('done') is not True:
        raise ValueError('Adapter returned an incomplete response')
    raw=envelope.get('message',{}).get('content','')
    if not isinstance(raw,str): raise ValueError('Adapter response has no text content')
    raw=raw.strip()
    if raw.startswith('```json') and raw.endswith('```'): raw=raw[7:-3].strip()
    elif raw.startswith('```') and raw.endswith('```'): raw=raw[3:-3].strip()
    value=json.loads(raw)
    if not isinstance(value,dict): raise ValueError('Model response is not a JSON object')
    return value

def build_messages(case):
    c=case['criterion']
    focus=('For this isolated calibration request, use the output schema below instead of the general review schema above. '
           'This is an isolated single-criterion calibration sample, not a full practice review. '
           'Treat the public expectation and supplied context as the complete grading scope. '
           'Do not infer hidden facts, exact thresholds, or required technologies. A quote alone does not establish correctness: explain the causal reasoning. '
           'Accept a reasonable alternative when its reasoning meets the public expectation. Detect direct contradictions. '
           'If active is false, return score null and do not penalize the answer. '
           'Return only JSON with exactly score (integer 0..4 or null), evidence (exact continuous quote from answer or empty string), and feedback (short causal rationale).')
    system=server.SYSTEM+'\n'+focus
    payload={'context':case['evaluation_context'],'criterion':{k:c[k] for k in ('id','label','publicExpectation','severity','active')},'answer':case['answer']}
    return [{'role':'system','content':system},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}]

def validate_sample(case,result):
    if set(result)!={'score','evidence','feedback'}: raise ValueError('Expected exactly score, evidence, feedback')
    score=result['score']; ev=result['evidence']; feedback=result['feedback']
    if case['criterion'].get('active') is False:
        if score is not None: raise ValueError('Unrevealed criterion must return null')
    else:
        if type(score) is not int or not 0<=score<=4: raise ValueError('Score must be an integer from 0 through 4')
    if not isinstance(ev,str) or len(ev)>1200 or (ev and ev not in case['answer']): raise ValueError('Evidence must be an exact quote from the answer')
    if score is not None and score>0 and not ev: raise ValueError('Positive score requires answer evidence')
    if not isinstance(feedback,str) or len(feedback.strip())<8 or len(feedback)>1200: raise ValueError('Feedback is missing or too long')
    expected=case['expected_score']
    if not expected.get('inactive') and not expected['min']<=score<=expected['max']:
        raise ValueError('Score outside the manually expected range')
    return True

def run_one(case):
    try:
        env=server.adapter('/api/chat',{'model':server.MODEL,'stream':False,'messages':build_messages(case)},timeout=190)
        result=read_content(env)
        validate_sample(case,result)
        return {'name':case['name'],'passed':True,'model':env.get('model',server.MODEL),'result':result}
    except Exception as e:
        # Error reports intentionally exclude request headers, adapter config, and key material.
        return {'name':case.get('name','unknown'),'passed':False,'error':str(e)[:500]}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true',help='make live calls to the configured local adapter')
    parser.add_argument('--case',action='append',dest='case_names',help='run only named sample(s)')
    parser.add_argument('--report',type=pathlib.Path,help='report path (default: a timestamped file in the system temporary directory)')
    args=parser.parse_args()
    if not args.run:
        parser.error('live calls are opt-in; pass --run to execute calibration')
    cases=json.loads(FIXTURES.read_text(encoding='utf-8'))
    if args.case_names: cases=[c for c in cases if c.get('name') in args.case_names]
    if not isinstance(cases,list) or not cases: parser.error('calibration fixture dataset is empty or invalid')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(run_one,cases))
    report={'kind':'isolated-rubric-calibration','createdAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model':server.MODEL,'sampleCount':len(results),'passedCount':sum(bool(r['passed']) for r in results),'results':results,'limitation':'Small hand-authored calibration set; not a measure of general grading accuracy.'}
    path=args.report or pathlib.Path(tempfile.gettempdir())/('architecture-practice-calibration-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
    path=path.expanduser().resolve()
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(path),'sampleCount':len(results),'passedCount':report['passedCount']},ensure_ascii=False))
    return 0 if report['passedCount']==len(results) else 1

if __name__=='__main__': raise SystemExit(main())
