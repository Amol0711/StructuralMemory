#!/usr/bin/env python3
"""Regenerate all control studies in a new directory and compare exact results."""
from pathlib import Path
import argparse,json,subprocess,sys
ROOT=Path(__file__).resolve().parent
# Only machine-dependent timing and release bookkeeping are excluded.
NONSCIENTIFIC={'source_sha256','eight_state_oracle_sha256','artifact_sha256','elapsed_seconds','environment','stage_seconds','stages_seconds'}
def canonical(x):
    if isinstance(x,dict):return {k:canonical(v) for k,v in x.items() if k not in NONSCIENTIFIC}
    if isinstance(x,list):return [canonical(v) for v in x]
    return x

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    if out.exists():raise ValueError('Choose a new output directory')
    frozen=(ROOT/'frozen').resolve()
    if out==frozen or frozen in out.parents:raise ValueError('Frozen records cannot be overwritten')
    out.mkdir(parents=True)
    compared=[]
    for name,script in [('transients','studies/control_transients.py'),('perturbations','studies/control_perturbations.py'),('feasibility','studies/feasibility/run_feasibility.py')]:
        proc=subprocess.run([sys.executable,str(ROOT/script),'--output',str(out/name)],capture_output=True,text=True)
        (out/(name+'.log')).write_text(proc.stdout+proc.stderr)
        if proc.returncode:raise RuntimeError(name+' regeneration failed; inspect '+str(out/(name+'.log')))
        for old in sorted((ROOT/'frozen'/name).rglob('*')):
            if not old.is_file():continue
            relative=old.relative_to(ROOT/'frozen'/name);new=out/name/relative
            if not new.is_file():raise RuntimeError('Missing regenerated file: '+str(relative))
            if old.suffix=='.json':ok=canonical(json.loads(old.read_text()))==canonical(json.loads(new.read_text()))
            else:ok=old.read_bytes()==new.read_bytes()
            if not ok:raise RuntimeError('Scientific output differs: '+name+'/'+str(relative))
            compared.append(name+'/'+relative.as_posix())
    result={'status':'passed','compared_files':len(compared),'files':compared,'timing_policy':'Recorded timings preserved. Fresh timing values are not expected to match and do not replace recorded values.','excluded_comparison_keys':sorted(NONSCIENTIFIC)}
    (out/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
