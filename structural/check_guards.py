"""Check that tampering and accidental frozen-data writes are rejected."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parent

def require(ok,message):
    if not ok:raise RuntimeError(message)

def load(path):return json.loads(path.read_text())
def dump(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')

def invoke(args,optimized):
    return subprocess.run([sys.executable,*(['-O'] if optimized else []),*map(str,args)],capture_output=True,text=True)

def main():
    results=[]
    for optimized in (False,True):
        with tempfile.TemporaryDirectory() as tmp:
            copy=Path(tmp)/'structural';shutil.copytree(ROOT,copy,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            require(invoke([copy/'verify.py'],optimized).returncode==0,'Baseline verification failed')
            cert=copy/'data/chains/certificates/chain_02_separate_full.json'
            before=cert.read_bytes();obj=load(cert);obj['horizon']=999;dump(cert,obj)
            # Update only the artifact manifest so the semantic checker is tested.
            manifest=copy/'data/chains/manifest.json';old=manifest.read_bytes();record=load(manifest)
            record['sha256'][str(cert.relative_to(manifest.parent))]=hashlib.sha256(cert.read_bytes()).hexdigest();dump(manifest,record)
            result=invoke([copy/'verify.py'],optimized)
            require(result.returncode!=0,'Corrupted chain certificate was accepted')
            cert.write_bytes(before);manifest.write_bytes(old)
            results.append({'optimized':optimized,'guard':'invalid_certificate_even_after_artifact_rehash','rejected':True})
            inp=copy/'data/benchmark/inputs/chain_02_separate.json';before=inp.read_bytes();obj=load(inp);obj['n']=3;dump(inp,obj)
            result=invoke([copy/'verify.py'],optimized)
            require(result.returncode!=0,'Changed benchmark input was accepted')
            inp.write_bytes(before);results.append({'optimized':optimized,'guard':'changed_frozen_input','rejected':True})
            result=invoke([copy/'src/benchmark/run_benchmark.py','--freeze','--output',copy/'data/benchmark'],optimized)
            require(result.returncode!=0,'Frozen benchmark write was accepted')
            results.append({'optimized':optimized,'guard':'frozen_benchmark_write','rejected':True})
    print(json.dumps({'status':'passed','rejections':results},indent=2))
if __name__=='__main__':main()
