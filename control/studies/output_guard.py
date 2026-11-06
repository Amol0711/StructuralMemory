"""Keep immutable recorded results separate from every new run."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]

def fresh_output(path):
    path=Path(path).resolve()
    frozen=(ROOT/'frozen').resolve()
    if path==frozen or frozen in path.parents:
        raise ValueError('The frozen result tree is read-only; choose a fresh output directory')
    if path.exists():
        names={p.name for p in path.iterdir()}
        allowed=not names or names=={'protocol.json'}
        if names <= {'rational_samples.json','sample_freeze.json','status.json'} and 'status.json' in names:
            allowed=json.loads((path/'status.json').read_text()).get('status')=='samples_frozen'
        if not allowed:
            raise ValueError('Output directory already contains results; choose a fresh directory')
    return path
