"""Read-only replay of frozen structural examples and benchmark records."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'src/benchmark')]
from compact_memory.model import Structure
from compact_memory.solver import solve
from compact_memory.certificate_checker import check_certificate
from structural_frontend import precheck
from fixtures import instances
from verify_recorded import verify as verify_benchmark

def require(condition,message):
    if not condition:raise RuntimeError(message)

def load(p):return json.loads(p.read_text())

def main():
    chains=ROOT/'data/chains';manifest=load(chains/'manifest.json')['sha256']
    actual={str(p.relative_to(chains)) for p in chains.rglob('*') if p.is_file() and p.name!='manifest.json'}
    require(set(manifest)==actual,'Chain manifest coverage mismatch')
    for name,expected in manifest.items():
        path=(chains/name).resolve()
        require(path.is_relative_to(chains),'Chain manifest path escapes root')
        require(hashlib.sha256(path.read_bytes()).hexdigest()==expected,'Changed chain artifact: '+name)
    summary=load(chains/'summary.json');require(summary['status']=='passed','Chain study status')
    require(summary['source_sha256']==load(ROOT/'recorded_execution_sources.json')['chains'],'Historical chain execution source record changed')
    counts={'chain_inputs':0,'chain_certificates':0,'chain_recomputed_answers':0,'benchmark_recomputed_answers':0,'new_pair_certificates':0}
    for row in summary['instances']:
        name=row['instance'];data=load(chains/'inputs'/f'{name}.json');result=solve(data)
        require(result['exploration']['complete'],'Unresolved chain replay')
        counts['chain_inputs']+=1
        for q in ('full','growth'):
            cert=load(chains/'certificates'/f'{name}_{q}.json')
            require(check_certificate(cert),'Rejected frozen chain certificate')
            require(cert['structure']==Structure.from_dict(data).to_dict(),'Chain certificate input binding')
            require(cert['query']==q,'Chain certificate query binding')
            require({k:result[q][k] for k in ('status','horizon')}==row[q],'Chain recomputed answer mismatch')
            require({k:cert[k] for k in ('status','horizon')}==row[q],'Chain recorded certificate answer mismatch')
            counts['chain_certificates']+=1;counts['chain_recomputed_answers']+=1
    require(counts['chain_inputs']==12 and counts['chain_certificates']==24,'Chain inventory count')
    benchmark=verify_benchmark(ROOT/'data/benchmark')
    by={r['instance']:r for r in load(ROOT/'data/benchmark/derived_tables.json')['inputs']}
    for item in instances():
        front=precheck(item['structure']);result=solve(item['structure'])
        require(result['exploration']['complete'],'Unresolved fresh pair replay: '+item['name'])
        require(front['horizons']==by[item['name']]['precheck_horizons'],'Fresh common precheck disagreement')
        for q in ('full','growth'):
            answer=result[q]['horizon'] if result[q]['status']=='finite' else 'infinite'
            require(answer==by[item['name']]['horizons'][q],'Fresh pair replay differs: '+item['name'])
            require(check_certificate(result[q]['certificate']),'Fresh pair certificate rejected')
            counts['benchmark_recomputed_answers']+=1;counts['new_pair_certificates']+=1
    result={'status':'passed','checks':counts,'benchmark':benchmark,'timing_policy':'Recorded times are checked and summarized, not replaced by verification runtimes.'}
    print(json.dumps(result,indent=2,sort_keys=True))
    return result
if __name__=='__main__':main()
