"""CLI for exact constrained-history scheduling and matrix checks.

Exit 0: exact answer/certified weights. Exit 2: resource-limited unknown.
Exit 3: infeasible infinite/finite constraint problem or failed memory identity.
Exit 1: malformed input or execution error. Check status before using an output.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from .solver import solve
from .matrices import certify_history_weights,finite_horizon


class Parser(argparse.ArgumentParser):
    def error(self,message):raise ValueError(message)


def _object(pairs):
    obj={}
    for key,value in pairs:
        if key in obj:raise ValueError('Duplicate JSON key: '+key)
        obj[key]=value
    return obj


def _read(path):
    source=sys.stdin.read() if path=='-' else Path(path).read_text()
    return json.loads(source,object_pairs_hook=_object,parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Nonfinite JSON: '+value)))


def _write(value,path):
    text=json.dumps(value,indent=2,allow_nan=False)+'\n'
    if path:
        target=Path(path);target.parent.mkdir(parents=True,exist_ok=True)
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=target.parent,delete=False) as stream:
                temporary=Path(stream.name);stream.write(text);stream.flush();os.fsync(stream.fileno())
            temporary.replace(target)
        finally:
            if temporary is not None and temporary.exists():temporary.unlink()
    sys.stdout.write(text)


def main(argv=None):
    parser=Parser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    solving=commands.add_parser('solve');solving.add_argument('input');solving.add_argument('--output')
    for name,default in [('states',10000),('edges',100000),('cycles',100000),('warmup-steps',100000),('cycle-steps',1000000)]:
        solving.add_argument('--max-'+name,type=int,default=default)
    verifying=commands.add_parser('weights');verifying.add_argument('input');verifying.add_argument('--output');verifying.add_argument('--max-histories',type=int,default=10000)
    finite=commands.add_parser('finite');finite.add_argument('input');finite.add_argument('--output')
    finite.add_argument('--allow-dead-ends',action='store_true')
    finite.add_argument('--max-steps',type=int,default=100000);finite.add_argument('--max-prefixes',type=int,default=100000);finite.add_argument('--max-histories',type=int,default=10000)
    try:
        args=parser.parse_args(argv);data=_read(args.input)
        if args.command=='solve':
            value=solve(data,max_states=args.max_states,max_edges=args.max_edges,max_cycles=args.max_cycles,
                        max_warmup_steps=args.max_warmup_steps,max_cycle_steps=args.max_cycle_steps)
        elif args.command=='weights':
            if type(data) is not dict or set(data)!={'matrices','memory'}:raise ValueError('weights input requires matrices and memory')
            value=certify_history_weights(data['matrices'],data['memory'],max_histories=args.max_histories)
        else:
            if type(data) is not dict or set(data)!={'matrices','model','p','horizon'}:raise ValueError('finite input requires matrices, model, p, horizon')
            value=finite_horizon(data['matrices'],data['model'],data['p'],data['horizon'],require_extendable=not args.allow_dead_ends,
                                 max_steps=args.max_steps,max_prefixes=args.max_prefixes,max_histories=args.max_histories)
        _write(value,args.output)
        return 2 if value['status']=='unknown' else (3 if value['status'] in ('infeasible','not_memory') else 0)
    except (ValueError,TypeError,OSError,RuntimeError) as exc:
        print('scheduling_tools: '+str(exc),file=sys.stderr);return 1


if __name__=='__main__':sys.exit(main())
