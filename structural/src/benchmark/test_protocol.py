"""Exact reference comparisons and runner failure-semantics checks."""
from pathlib import Path
from unittest.mock import patch
import hashlib,json,math,subprocess,tempfile
from fixtures import instances,protocol,encode
from worker import exterior_selected
from reference import canonical_int,compound2,exterior_horizons_exact
import run_benchmark as runner

def require(ok,msg):
    if not ok:raise RuntimeError(msg)

def main():
    counts={'dense_sparse_query_comparisons':0,'timeout_partial_answer_checks':0,'summary_censoring_checks':0}
    chosen=[x for x in instances() if x['name'] in ('chain_02_separate','chain_02_joint','chain_04_separate','chain_04_joint','delay_04_selected','delay_04_selection_free','cycle_outside_ancestry')]
    for item in chosen:
        ms,masses=canonical_int(item['structure']);bs=[];pairs=None
        for m in ms:
            b,pairs=compound2(m);bs.append([{j:x for j,x in enumerate(row) if x} for row in b])
        reference,_=exterior_horizons_exact(ms,masses)
        expected={q:('infinite' if reference[key]==math.inf else reference[key]) for q,key in [('full','f'),('growth','g')]}
        for queries in (('full','growth'),('full',),('growth',)):
            actual,_=exterior_selected(bs,masses,pairs,queries)
            require(actual=={q:expected[q] for q in queries},'Dense/sparse selected-query mismatch')
            counts['dense_sparse_query_comparisons']+=len(queries)
    item=next(x for x in instances() if x['name']=='cycle_outside_ancestry')
    with tempfile.TemporaryDirectory() as tmp:
        out=Path(tmp);(out/'inputs').mkdir();(out/'inputs'/(item['name']+'.json')).write_text(encode(item['structure']))
        def timed_out(command,**kwargs):
            path=Path(command[command.index('--output')+1])
            runner.dump(path,{'status':'running','phase':'core_decision','precheck_horizons':{'full':'infinite','growth':None},
                'horizons':{'full':'infinite','growth':999},'certificates':[],'stages_seconds':{},'decision_seconds':123,'certified_total_seconds':123})
            raise subprocess.TimeoutExpired(command,10)
        with patch.object(runner.subprocess,'run',side_effect=timed_out):
            record=runner.run_worker(item,'preprocessed','pair',1,out)
        require(record['status']=='unknown_timeout','Timeout not classified unresolved')
        require(record['horizons']=={'full':'infinite','growth':None},'Timeout failed to retain only certified precheck answer')
        require(record['interrupted_candidate_horizons']['growth']==999,'Interrupted candidate not retained as separate diagnostics')
        require('decision_seconds' not in record and 'certified_total_seconds' not in record,'Capped run has headline runtime')
        counts['timeout_partial_answer_checks']=4
        records=[]
        for it in ('warmup',1,2,3):
            records.append({**record,'iteration':it,'measured':it!='warmup'})
        summary=runner.summarize(item,'preprocessed','pair',records)
        require(summary['decision_seconds'] is None and summary['certified_total_seconds'] is None and summary['parent_wall_seconds'] is None,'Censored summary reports completed runtime statistic')
        require(summary['horizons']=={'full':'infinite','growth':None} and summary['completed_repetitions']==0,'Censored partial answer lost')
        counts['summary_censoring_checks']=2
    result={'status':'passed','checks':counts,'reference_instances':[x['name'] for x in chosen],
      'main_table_predeclared':protocol()['main_table_landmarks'],
      'limitations':'Implementation/reference and failure-path checks; not a proof of genericity or algorithmic complexity.'}
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
