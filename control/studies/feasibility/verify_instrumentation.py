"""Undo every timing-only edit and require exact preceding solver recovery."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[2]

def verify():
    record=json.loads((ROOT/'studies/feasibility/instrumentation.json').read_text())
    original=(ROOT/record['original']).read_bytes()
    if hashlib.sha256(original).hexdigest()!=record['original_sha256']:
        raise RuntimeError('The preserved scheduling solver changed')
    text=(ROOT/record['instrumented']).read_text()
    text=re.sub(r'(?m)^( +)save_timings\(\)\n\1return result$',lambda m:m.group(1)+'return result',text)
    for edit in reversed(record['literal_changes']):
        if text.count(edit['new'])!=1:raise RuntimeError('Unexpected timing instrumentation')
        text=text.replace(edit['new'],edit['old'])
    if text.encode()!=original:raise RuntimeError('Inverse timing edits do not recover the old solver')
    return True

if __name__=='__main__':
    verify();print('Exact inverse timing-only source comparison passed')
