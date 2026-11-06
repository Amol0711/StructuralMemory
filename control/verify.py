#!/usr/bin/env python3
"""Verify sealed recorded payloads and replay independent exact checks."""
from pathlib import Path
from fractions import Fraction
import hashlib,json,sys,subprocess
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'checks'))
sys.path.insert(0,str(ROOT/'studies'))
sys.path.insert(0,str(ROOT/'studies/feasibility'))
import control_perturbations as perturb
import run_feasibility as cascades
from compact_memory.certificate_checker import check_certificate

def require(ok,message):
    if not ok:raise RuntimeError(message)

def read(path):return json.loads(path.read_text())

def main():
    manifest=read(ROOT/'payload_manifest.json')
    for name,expected in manifest['sha256'].items():
        p=ROOT/name
        require(p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==expected,'Changed or missing payload: '+name)
    frozen=ROOT/'frozen'
    samples=read(frozen/'perturbations/rational_samples.json')
    require(samples==perturb.make_sample_artifact(),'Frozen samples differ from seed generator')
    saved=read(frozen/'perturbations/sample_results.json')['samples']
    require(len(saved)==len(samples['samples'])==256,'Sample count mismatch')
    regenerated=[perturb.evaluate(x) for x in samples['samples']]
    require(saved==regenerated,'Recomputed perturbation results disagree')
    summary=read(frozen/'perturbations/summary.json')
    require(summary['counts']['two_step_initial_column_growth_checks']==16384,'Two-step identity count')
    require(all(summary['counts'][k]==sum(r['counts'][k] for r in regenerated) for k in summary['counts']),'Sample summary count mismatch')
    protocol=read(frozen/'feasibility/protocol.json')
    require(protocol==cascades.frozen_protocol(),'Cascade protocol mismatch')
    totals={'structural_certificates':0,'scheduling_cases':0,'optima':0,'caps':0,'weights':0,'ratio_evaluations':0}
    for model in protocol['models']:
        name=model['name'];structural=read(frozen/'feasibility/structural'/f'{name}.json')
        for query in ('full','growth'):
            require(check_certificate(structural[query]['certificate']),'Structural certificate failed')
            expected=model['expected_graphical_horizon']
            got=structural[query]['horizon'] if structural[query]['status']=='finite' else structural[query]['status']
            require(got==expected,'Structural horizon mismatch')
            totals['structural_certificates']+=1
        if model['expected_graphical_horizon']=='infinite':continue
        record=read(frozen/'feasibility/weights'/f'{name}.json')
        values,evidence=cascades.weights(model,record['memory'])
        require(values==record['weights'] and evidence==record['evidence'],'All-column weights mismatch')
        totals['weights']+=len(values);totals['ratio_evaluations']+=evidence['all_column_ratio_evaluations']
        for cname,con in cascades.constraints(model['structure']['U']).items():
            answer=read(frozen/'feasibility/scheduling'/f'{name}__{cname}.json')
            data={'actions':model['structure']['U'],'memory':record['memory'],'weights':values,'constraint':con}
            checked=cascades.verify_graph_and_cycles(data,answer)
            require(checked==answer['independent_checks'],'Independent graph/cycle check mismatch')
            totals['scheduling_cases']+=1
            totals['optima' if answer['status']=='optimal' else 'caps']+=1
    require(totals=={'structural_certificates':14,'scheduling_cases':18,'optima':14,'caps':4,'weights':435,'ratio_evaluations':13776},'Cascade counts mismatch')
    cascades.verify_timing_copy()
    proc=subprocess.run([sys.executable,str(ROOT/'checks/analytic_control_check.py')],capture_output=True,text=True,check=True)
    analytic=json.loads(proc.stdout)
    require(analytic['status']=='passed' and analytic['edge_corner_evaluations']==256,'Analytic corner verification')
    transient=read(frozen/'transients/summary.json');rows=read(frozen/'transients/finite_horizons.json')
    require(transient['mass_and_marginal_agreements']==27603 and len(rows)==117,'Transient counts')
    require(max(Fraction(x['fixed_to_optimum']) for x in rows if x['population']=='correlated' and x['constraint']=='no11')==Fraction(3519,551),'Transient ratio mismatch')
    result={'status':'passed','sealed_payloads':len(manifest['sha256']),'seed':samples['seed'],'recomputed_samples':256,'two_step_growth_identities':16384,'cascade_checks':totals,'analytic_corner_evaluations':256,'transient_recorded_masses':27603,'transient_recorded_extrema':117,'transient_recomputation':'Use reproduce.py for exhaustive fresh propagation and comparison.'}
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
