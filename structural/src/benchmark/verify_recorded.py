"""Validate frozen inputs, sources, all raw trials, certificates and summaries."""
from pathlib import Path
from datetime import datetime
import json,math,sys
from fixtures import instances,REPETITIONS,CAP_SECONDS,MEMORY_BYTES
from run_benchmark import ROOT,ALLOWED,check_frozen,jobs,summarize,csv_text,derived_tables,digest,read,dump,require
sys.path.insert(0,str(ROOT/'src'))
from compact_memory.model import Structure
from compact_memory.certificate_checker import check_certificate as check_pair
from structural_frontend import precheck,check_certificate as check_precheck

def _answer(value):
    return value is None or value=='infinite' or (type(value) is int and value>=0)

def verify(out):
    out=Path(out).resolve();frozen=check_frozen(out);manifest=read(out/'manifest.json')
    require(manifest['source_sha256']==frozen['source_sha256'],'Manifest source snapshot differs')
    for name,sha in manifest['artifact_sha256'].items():
        path=(out/name).resolve();require(path.is_relative_to(out),'Manifest path escapes result root')
        require(path.is_file() and digest(path)==sha,'Recorded artifact changed: '+name)
    actual={p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file() and p.name not in ('manifest.json','verification.json')}
    require(actual==set(manifest['artifact_sha256']),'Manifest coverage differs')
    summary=read(out/'summary.json')
    require(summary['status']=='passed' and summary['source_stable_during_run'],'Benchmark not completed')
    require(summary['protocol_sha256']==digest(out/'protocol.json'),'Protocol identity mismatch')
    allraw=[];rebuilt=[];certificate_count=0;frontcert=0;paircert=0;last_end=None
    for item,mode,method in jobs():
        data=item['structure'];canonical=Structure.from_dict(data).to_dict();front=precheck(data)
        records=[]
        for it in ['warmup',*range(1,REPETITIONS+1)]:
            path=out/'raw'/f"{item['name']}__{mode}__{method}__{it}.json";r=read(path);records.append(r);allraw.append(r)
            for k,v in [('schema','structural-memory.benchmark-worker.v1'),('semantics','graphical-unrestricted'),('instance',item['name']),('family',item['family']),('mode',mode),('method',method),('iteration',it),('measured',it!='warmup'),('wall_cap_seconds',CAP_SECONDS),('address_space_cap_bytes',MEMORY_BYTES)]:
                require(r.get(k)==v,'Raw trial identity/protocol mismatch: '+path.name+' '+k)
            require(r['input_sha256']==digest(out/'inputs'/(item['name']+'.json')),'Input hash binding failed')
            require(r['status'] in ALLOWED,'Unrecognized raw status')
            require(set(r['horizons'])=={'full','growth'} and all(_answer(v) for v in r['horizons'].values()),'Malformed horizon values')
            require(r['parent_wall_seconds']>0,'Missing parent wall time')
            start=datetime.fromisoformat(r['parent_started_utc']);end=datetime.fromisoformat(r['parent_finished_utc'])
            require(start<=end and (last_end is None or last_end<=start),'Trials not sequential in recorded timestamps');last_end=end
            require(all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in r['stages_seconds'].values()),'Invalid stage times')
            expected_pre=front['horizons'] if mode=='preprocessed' else None
            require(r['precheck_horizons']==expected_pre,'Unequal common preprocessing')
            if mode=='preprocessed':
                require(r['J']==front['J'] and r['precheck_stats']==front['stats'],'Preprocessing metadata changed')
                for q,v in front['horizons'].items():
                    if v is not None:require(r['horizons'][q]==v,'Certified preprocessing answer discarded')
            if r['status']=='completed':
                require(all(v is not None for v in r['horizons'].values()),'Completed run unresolved')
                stage=r['stages_seconds'];expected=sum(stage[k] for k in ('input_validation','precheck','matrix_construction','core_decision'))
                require(r['decision_seconds']==expected,'Decision stage sum mismatch')
                require(r['certified_total_seconds']==(sum(stage.values()) if r['all_answers_certified'] else None),'Certified total mismatch')
            else:
                require(r['horizons']==(expected_pre or {'full':None,'growth':None}),'Resource stop misrepresented unresolved core query')
                if r['status']=='unknown_memory_preflight':require(r['dense_compound_pointer_lower_bound_bytes']>MEMORY_BYTES,'Invalid dense preflight')
                if r['status']=='unknown_timeout':require(r['parent_wall_seconds']>=CAP_SECONDS,'Timeout before declared cap')
            queries=set()
            for cert in r['certificates']:
                require(cert['structure']==canonical,'Certificate structure binding failed')
                require(cert['query'] not in queries,'Duplicate certificate query');queries.add(cert['query'])
                if cert['schema']=='structural-memory.pair-certificate.v1':
                    require(check_pair(cert),'Pair certificate rejected');paircert+=1
                else:
                    require(check_precheck(cert,expected_structure=data),'Union certificate rejected');frontcert+=1
                value=cert['horizon'] if cert['status']=='finite' else 'infinite'
                require(r['horizons'][cert['query']]==value,'Certificate/answer mismatch');certificate_count+=1
            if r['status']=='completed':
                require(r['all_answers_certified']==(queries=={'full','growth'}),'Certificate coverage flag incorrect')
                if method=='pair':require(queries=={'full','growth'},'Completed pair run missing certificate')
            if mode=='unpruned_stress':
                require(r['status']=='completed' and r['reachable_states']==item['metadata']['expected_unpruned_states'],'Refresh unpruned2^n check failed')
            if 'expected_horizons' in item['metadata']:
                for q,v in r['horizons'].items():
                    if v is not None:require(v==item['metadata']['expected_horizons'][q],'Fixture expectation mismatch')
        rebuilt.append(summarize(item,mode,method,records))
    require(len(allraw)==380 and len(rebuilt)==95,'Raw trial or method-instance inventory')
    require(summary['summaries']==rebuilt,'Summary differs from raw records')
    require((out/'benchmark.csv').read_text()==csv_text(rebuilt),'CSV differs from raw-derived summary')
    require(read(out/'derived_tables.json')==derived_tables(rebuilt),'Landmarks/counts differ from raw-derived summary')
    require(summary['method_instances']==95 and summary['fresh_process_runs']==380,'Summary counts')
    require(summary['unknown_method_instances']==sum(s['status']!='completed' for s in rebuilt),'Unresolved summary count')
    for item in instances():
        for q in ('full','growth'):
            values={r['horizons'][q] for r in allraw if r['instance']==item['name'] and r['horizons'][q] is not None}
            require(len(values)==1,'Resolved methods disagree or no answer: '+item['name'])
    result={'status':'passed','frozen_inputs':29,'branching_dags':9,'screened_out':0,'main_method_instances':87,'stress_method_instances':8,'raw_trials':380,
      'certificates_checked':certificate_count,'union_certificates':frontcert,'pair_certificates':paircert,
      'artifact_hashes_verified':True,'historical_source_record_verified':True,
      'source_hash_scope':'Original execution-source hashes retained separately from release source hashes; no claim of byte equality after relocation.','all_summaries_and_csv_recomputed':True,
      'scope':'Graphical unrestricted horizons; exact structural/canonical calculations. Finite checks are not proofs of general complexity or universal numerical horizon equality.'}
    return result

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=ROOT/'data/benchmark');args=ap.parse_args()
    print(json.dumps(verify(args.output),indent=2))
