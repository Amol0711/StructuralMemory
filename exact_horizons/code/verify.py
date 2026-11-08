"""Validate frozen tables, records and certificates, with optional exact replay."""
from pathlib import Path
from collections import Counter
from fractions import Fraction
from itertools import combinations, product
import argparse
import hashlib
import json
import math
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
# Backends are independent of the checker below and of graphical results.
import primary
import independent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def regenerate(case):
    """Regenerate the full entry list from the preserved integer case seed."""
    rng = random.Random(case['seed'])
    classes, regenerated = {}, []
    s = case['structure']
    for u in range(s['U']):
        for kind, scope_key in [('theta', 'pa'), ('psi', 'fac')]:
            for index, scope in enumerate(s[scope_key][u]):
                for context in product((0, 1), repeat=len(scope)):
                    chi = int(all(context))
                    group = (f'{kind}:chi:{chi}' if case['family'] == 'T' else
                             f'{kind}:{u}:{index}:' + ''.join(map(str, context)))
                    if group not in classes:
                        classes[group] = str(Fraction(rng.randint(1, 96 if kind == 'theta' else 388), 97))
                    regenerated.append(dict(type=kind, action=u, index=index,
                                            context=list(context), chi=chi,
                                            class_id=group, value=classes[group]))
    require(regenerated == case['entries'], 'Seed/entry mismatch: ' + case['case_id'])
    return len(regenerated)


def primitive(row):
    divisor = math.gcd(*row)
    if divisor and next(x for x in row if x) < 0:
        divisor = -divisor
    return [v // divisor for v in row] if divisor else list(row)


def rank(rows):
    basis = {}
    for raw in rows:
        row = raw
        for pivot, reduced in sorted(basis.items()):
            if row[pivot]:
                a, b = reduced[pivot], row[pivot]
                row = primitive([a*x-b*y for x, y in zip(row, reduced)])
        if any(row):
            basis[next(i for i, v in enumerate(row) if v)] = row
    return len(basis)


def matrix(case, action):
    """Independent rational column construction for certificate replay."""
    s = case['structure']
    states = list(product((0, 1), repeat=s['n']))
    params = {(e['type'], e['action'], e['index'], tuple(e['context'])): Fraction(e['value'])
              for e in case['entries']}
    mass = [math.prod(params['psi', action, j, tuple(x[k] for k in scope)]
                      for j, scope in enumerate(s['fac'][action])) for x in states]
    cols = []
    for x, m in zip(states, mass):
        t = [params['theta', action, i, tuple(x[j] for j in parents)]
             for i, parents in enumerate(s['pa'][action])]
        col = [m*math.prod(t[i] if y[i] else 1-t[i] for i in range(len(t))) for y in states]
        require(sum(col) == m and all(v > 0 for v in col), 'Mass or positivity identity')
        cols.append(col)
    return list(map(list, zip(*cols))), mass


def verify_orbit(case, cert):
    require(cert['case_id'] == case['case_id'] and cert['component'] == 'growth', 'Certificate/input binding')
    require(cert['status'] == 'certified_infinity' and cert['horizon'] == 'infinity', 'Certificate decision')
    M, _ = matrix(case, cert['action'])
    _, mass = matrix(case, cert['readout_action'])
    scale = math.lcm(*(v.denominator for row in M for v in row))
    A = [[int(x*scale) for x in row] for row in M]
    pairs = list(combinations(range(len(A)), 2))
    second = [[A[i][k]*A[j][l]-A[i][l]*A[j][k] for k,l in pairs] for i,j in pairs]
    mass_scale = math.lcm(*(v.denominator for v in mass))
    v = primitive([int((mass[i] - mass[j])*mass_scale) for i,j in pairs])
    history = cert['primitive_orbit_rows']
    require(len(history) == 21, 'Certificate orbit length')
    for i, row in enumerate(history):
        require(v == row, f'Orbit row {i} differs for {case["case_id"]}')
        if i+1 < len(history):
            v = primitive([sum(a*x for a,x in zip(v, col)) for col in zip(*second)])
    require(rank(history[:-1]) == rank(history) == 20 and any(history[-1]), 'First nonzero dependence')
    require(cert['first_dependence_length'] == cert['prefix_rank'] == 20, 'Recorded cyclic rank')
    require(cert['primitive_orbit_sha256'] == independent.digest(history), 'Orbit digest')
    # Since v_0,...,v_19 are independent and nonzero v_20 is in their span,
    # the cyclic minimal polynomial cannot be x^20. It divides no x^k.
    return {'action':cert['action'], 'readout_action':cert['readout_action'],
            'prefix_rank':20, 'dependent_row_nonzero':True}


def check_integrity():
    manifest = read(ROOT/'integrity.json')
    present = {str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file()
               and p.name != 'integrity.json' and '__pycache__' not in p.parts}
    require(present == set(manifest['sha256']), 'Manifest/file inventory mismatch')
    for relative, expected in manifest['sha256'].items():
        require(sha(ROOT/relative) == expected, 'Payload changed: ' + relative)
    return len(manifest['sha256'])


def verify(replay=True):
    started = time.monotonic()
    checked_files = check_integrity()
    manifest = read(ROOT/'case_manifest.json')
    require(manifest['protocol_sha256'] == sha(ROOT/'protocol.json'), 'Protocol binding')
    protocol = read(ROOT/'protocol.json')
    require(protocol['limits'] == dict(address_space_bytes_per_worker=2147483648,
            maximum_workers=4,wall_seconds_per_component_backend=120), 'Frozen limits')
    all_items = manifest['cases'] + manifest['controls']
    require(len(manifest['cases']) == 125 and len(manifest['controls']) == 3, 'Cohort sizes')
    require(len({r['case_id'] for r in all_items}) == 128, 'Duplicate/missing case')
    cases, constructions = {}, {}
    table_entries = 0
    for r in all_items:
        path = ROOT/r['path']
        require(sha(path) == r['sha256'], 'Case hash')
        case = read(path)
        require(case['case_id'] == r['case_id'], 'Case identity')
        cases[r['case_id']] = case
        if case['family'] != 'C':
            require(case['family'] in ['U','T'] and type(case['seed']) is int, 'Family or integer seed')
            table_entries += regenerate(case)
        a, ma, ca = primary.build_matrices(case)
        b, mb, cb = independent.build(case)
        require(a == tuple(tuple(tuple(v for v in row) for row in m) for m in b)
                and ma == tuple(tuple(v for v in m) for m in mb), 'Independent matrix construction mismatch')
        constructions[r['case_id']] = {'primary':ca,'independent':cb}
    counts = Counter(c['family'] for c in cases.values())
    require(counts == {'U':65,'T':60,'C':3}, 'Free/tied/control counts')
    groupcounts = Counter((c['input_id'], c['family']) for c in cases.values() if c['family'] != 'C')
    require(len(groupcounts) == 25 and set(groupcounts.values()) == {5}, 'Five draws per eligible family')
    scalar = [c for c in cases.values() if c['input_id'] == 'zero_coordinates']
    require(len(scalar) == 5 and all(c['structure']['n'] == 0 and c['family'] == 'U' for c in scalar), 'Quotient scalar')
    points_doc = read(ROOT/'results/point_results.json')
    points, controls = points_doc['points'], points_doc['controls']
    require(len(points) == 125 and len(controls) == 3, 'Decision counts')
    records = {r['case_id']:r for r in all_items}
    decision_ids = [p['case_id'] for p in points + controls]
    require(len(set(decision_ids)) == 128 and set(decision_ids) == set(cases), 'Decision/input bijection')
    status, values, unknown = Counter(), Counter(), set()
    agreements, exceptions = [], []
    for point in points + controls:
        key = point['case_id']
        require(point['case_sha256'] == records[key]['sha256'], 'Decision/input hash')
        if point['family'] != 'C':
            pair = point['decisions']
            agrees = pair == point['graphical']
            require(agrees == point['agrees_with_graphical'], 'Graphical comparison')
            (agreements if agrees else exceptions).append(key)
            values.update(pair.values())
        for backend, component in product(('primary','independent'), ('full','growth')):
            saved = []
            for mode in ('normal','optimized'):
                r = read(ROOT/f'records/{mode}/{backend}/{component}/{key}.json')
                require(r['case_id'] == key and r['case_sha256'] == records[key]['sha256'], 'Record/input binding')
                require(r['backend'] == backend and r['component'] == component and r['mode'] == mode, 'Record job binding')
                require(r['export_backend_sha256'] == sha(ROOT/f'code/{backend}.py'), 'Backend binding')
                status[r['status']] += 1
                if r['status'] == 'unknown':
                    require(r.get('horizon') is None and r['reason'] == 'wall_time_limit', 'Cap semantics')
                    require(r['wall_seconds'] >= 120, 'Archived cap duration')
                    unknown.add((key,component))
                else:
                    require(r['status'] == 'resolved' and r['horizon'] == point['decisions'][component], 'Recorded decision')
                    details = r['result']['details']
                    construction = details['matrix_construction' if backend == 'primary' else 'construction']
                    require(construction == constructions[key][backend], 'Fresh/archived matrix evidence')
                    saved.append(r['result'])
            if saved:
                require(len(saved) == 2 and saved[0] == saved[1], 'Normal/optimized scientific payloads')
    require(status == {'unknown':20,'resolved':1004}, 'Raw run counts, including controls')
    require(values == {0:20,'infinity':128,1:values[1],2:values[2],4:values[4],6:values[6]} and sum(values.values()) == 250, 'Horizon value population')
    require(sum(v for k,v in values.items() if isinstance(k,int) and k > 0) == 102, 'Positive finite horizon count')
    require(len(agreements) == 124 and exceptions == ['chain_04_joint__T__01'], 'Retained exception')
    capped = {(f'refresh_04__U__{i:02d}','growth') for i in range(1,6)}
    require(unknown == capped, 'Capped query set')
    certificates = {}
    for key, _ in sorted(capped):
        cert = read(ROOT/f'certificates/normal/{key}.json')
        require(cert == read(ROOT/f'certificates/optimized/{key}.json'), 'Certificate modes differ')
        certificates[key] = verify_orbit(cases[key], cert)
    # Check exact rank-one factorization and the exceptional 1-step horizons.
    exc = cases['chain_04_joint__T__01']; pstar = None
    require({(e['type'], e['chi']):e['value'] for e in exc['entries']} ==
            {('theta',0):'94/97',('theta',1):'94/97',('psi',0):'235/97',('psi',1):'368/97'}, 'Exception parameter levels')
    for action in range(exc['structure']['U']):
        M, mass = matrix(exc, action); p = [row[0]/mass[0] for row in M]
        require(len(set(mass)) == 2 and sum(p) == 1 and
                all(M[i][j] == p[i]*mass[j] for i,j in product(range(16),repeat=2)), 'Common-column factorization')
        require(pstar is None or p == pstar, 'Common column across actions');pstar=p
    replayed = []
    if replay:
        for point in points + controls:
            key = point['case_id'];case = cases[key]
            if case['structure']['n'] > 3 and key != 'chain_04_joint__T__01':
                continue
            expected = point['decisions']
            for backend in (primary, independent):
                got = backend.solve(case)
                require({k:got[k] for k in ('full','growth')} == expected, 'Fresh exact replay: ' + key)
            replayed.append(key)
    return {'status':'passed','integrity_files':checked_files,'case_tables':128,'integer_seeds_regenerated':125,
            'rational_entries_regenerated':table_entries,'independent_matrix_comparisons':128,
            'archived_execution_records':1024,'retained_raw_unknown_runs':20,'distinct_capped_queries':5,
            'constant_word_certificates_replayed':certificates,'agreeing_pairs':124,'retained_exception':exceptions[0],
            'horizon_counts':{'zero':20,'positive_finite':102,'infinite':128},
            'direct_two_backend_replayed_cases':replayed,'optimized':bool(sys.flags.optimize),
            'elapsed_seconds':time.monotonic()-started}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-replay',action='store_true',help='Skip direct horizon recomputation; still verify seeds, all matrix constructions, records and orbit certificates.')
    parser.add_argument('--output',type=Path,help='Optional JSON report path, outside the frozen component.')
    args = parser.parse_args()
    if args.output:
        path = args.output.resolve()
        require(path != ROOT and ROOT not in path.parents, 'Verification report must be outside the frozen component')
    result = verify(not args.no_replay)
    output = json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(output)
    print(output,end='')
