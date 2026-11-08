"""Independent support-state and exact canonical-matrix reference algorithms.

Infinity is returned only after a certified invariant-space or repeated-level
criterion. Bounded search exhaustion is reported as unresolved.
"""
import itertools, random, math
from fractions import Fraction as Fr

def bits(s, n): return [(s >> (n - 1 - i)) & 1 for i in range(n)]

# ---------------- structures ----------------
def rand_structure(n, U=2, pmax=2, fmax=2, smax=2, rng=random):
    pa = [[tuple(sorted(rng.sample(range(n), rng.randint(0, min(pmax, n))))) for i in range(n)] for u in range(U)]
    fac = [[tuple(sorted(rng.sample(range(n), rng.randint(0, min(smax, n))))) for k in range(rng.randint(1, fmax))] for u in range(U)]
    return dict(n=n, U=U, pa=pa, fac=fac)

def Fsupp(S, a): return set(j for F in S['fac'][a] for j in F)

# ---------------- d-separation on the unrolled graph with separate leaves (Lauritzen) ----------------
def unrolled(S, w):
    n, L = S['n'], len(w); par = {}
    for t in range(L + 1):
        for i in range(n): par[('x', t, i)] = set()
    for t, u in enumerate(w):
        for i in range(n):
            for j in S['pa'][u][i]: par[('x', t + 1, i)].add(('x', t, j))
        for k, F in enumerate(S['fac'][u]): par[('S', t, k)] = {('x', t, j) for j in F}
    return par

def dsep(par, X, Y, Z):
    if X & Y: return False
    anc, st = set(), list(X | Y | Z)
    while st:
        v = st.pop()
        if v in anc: continue
        anc.add(v); st.extend(par[v])
    adj = {v: set() for v in anc}
    for v in anc:
        ps = [p for p in par[v] if p in anc]
        for p in ps: adj[p].add(v); adj[v].add(p)
        for a, b in itertools.combinations(ps, 2): adj[a].add(b); adj[b].add(a)
    seen = {x for x in X if x not in Z}; st = list(seen)
    while st:
        v = st.pop()
        for q in adj[v]:
            if q in Z or q in seen: continue
            seen.add(q); st.append(q)
    return not (seen & Y)

def gsep_full(S, w):
    par = unrolled(S, w); L = len(w); n = S['n']
    Z = {v for v in par if v[0] == 'S'}
    return dsep(par, {('x', 0, i) for i in range(n)}, {('x', L, i) for i in range(n)}, Z)

def gsep_growth(S, w, a):
    par = unrolled(S, w); L = len(w); n = S['n']
    Z = {v for v in par if v[0] == 'S'}
    Y = {('x', L, j) for j in Fsupp(S, a)}
    if not Y: return True
    return dsep(par, {('x', 0, i) for i in range(n)}, Y, Z)

def brute_horizons(S, Lmax):
    """Return finite horizons found through Lmax; None means unresolved."""
    if type(Lmax) is not int or Lmax < 0:
        raise ValueError('Lmax must be a nonnegative integer')
    Hf = Hg = None
    for L in range(0, Lmax + 1):
        words = list(itertools.product(range(S['U']), repeat=L))
        if Hf is None and all(gsep_full(S, w) for w in words): Hf = L
        if Hg is None and all(gsep_growth(S, w, a) for w in words for a in range(S['U'])): Hg = L
        if Hf is not None and Hg is not None: break
    return Hf, Hg     # None = not found through Lmax, never an infinity proof

# ---------------- graph automaton (root-union / non-root antichain) ----------------
def auto_step(S, state, u):
    UR, NR = state; n = S['n']
    labels = [('R', UR)] + [('N', s) for s in NR]
    parent = list(range(len(labels)))
    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for F in S['fac'][u]:
        hit = [idx for idx, (_, s) in enumerate(labels) if s & set(F)]
        for a, b in zip(hit, hit[1:]): parent[find(a)] = find(b)
    rootc = find(0); URn = set(UR); NRc = {}
    for idx, (_, s) in enumerate(labels):
        c = find(idx)
        if c == rootc: URn |= s
        else: NRc.setdefault(c, set()).update(s)
    succ = lambda s: frozenset(i for i in range(n) if set(S['pa'][u][i]) & s)
    UR2 = succ(URn)
    cand = {succ(frozenset(s)) for s in NRc.values()} | {frozenset([i]) for i in range(n)}
    cand = {s for s in cand if s and not s <= UR2}
    anti = frozenset(s for s in cand if not any(s < t for t in cand))
    return (UR2, anti)

class ResourceLimitError(RuntimeError):
    """UNKNOWN outcome: the requested search depth has been exhausted.

    partial_horizons retains any already proved finite result. A None entry
    is unresolved. The exception must never be interpreted as infinity.
    """
    def __init__(self, Lcap, depth, partial_horizons):
        self.Lcap = Lcap
        self.depth = depth
        self.partial_horizons = partial_horizons
        super().__init__(f'UNKNOWN after depth {depth} (cap {Lcap}); partial horizons {partial_horizons}')


def auto_horizons(S, Lcap=10**6):
    """Least horizons, with repeated-level infinity or explicit resource failure.

    Lcap is the largest inspected depth. A proof found at that depth is
    accepted; otherwise no expansion beyond the cap is performed.
    """
    if type(Lcap) is not int or Lcap < 0:
        raise ValueError('Lcap must be a nonnegative integer')
    n = S['n']; init = (frozenset(range(n)), frozenset())
    FS = [Fsupp(S, a) for a in range(S['U'])]
    level = {init}; seen_levels = {}; Hf = Hg = None; L = 0
    while True:
        if Hf is None and all(not st[0] for st in level): Hf = L
        if Hg is None and all(not (st[0] & FS[a]) for st in level for a in range(S['U'])): Hg = L
        if Hf is not None and Hg is not None: return Hf, Hg, L
        key = frozenset(level)
        if key in seen_levels:
            return (Hf if Hf is not None else math.inf), (Hg if Hg is not None else math.inf), L
        if L >= Lcap:
            raise ResourceLimitError(Lcap, L, (Hf, Hg))
        seen_levels[key] = L
        level = {auto_step(S, st, u) for st in level for u in range(S['U'])}; L += 1

# ---------------- matrices ----------------
def canonical_int(S):
    """boundary family (7) scaled to integers: K'(1|x) = 1/2 prod x_Pa (x2), psi' = 1 + 1/2 prod x_F (x2)"""
    n = S['n']; N = 2 ** n; Ms, ms = [], []
    for u in range(S['U']):
        m = []
        for s in range(N):
            x = bits(s, n); v = 1
            for F in S['fac'][u]: v *= 2 + (1 if all(x[j] for j in F) else 0)
            m.append(v)
        M = [[0] * N for _ in range(N)]
        for s in range(N):
            x = bits(s, n)
            on = [all(x[j] for j in S['pa'][u][i]) for i in range(n)]
            for t in range(N):
                y = bits(t, n); v = 1
                for i in range(n): v *= (1 if on[i] else (0 if y[i] else 2))
                M[t][s] = v * m[s]
        Ms.append(M); ms.append(m)
    return Ms, ms

def interior_frac(S, rng=random, R=10**4):
    n = S['n']; N = 2 ** n; Ms, ms = [], []
    for u in range(S['U']):
        th = [{c: Fr(rng.randint(1, R - 1), R) for c in itertools.product((0, 1), repeat=len(S['pa'][u][i]))} for i in range(n)]
        ps = [{c: Fr(rng.randint(1, 4 * R), R) for c in itertools.product((0, 1), repeat=len(F))} for F in S['fac'][u]]
        m = []
        for s in range(N):
            x = bits(s, n); v = Fr(1)
            for k, F in enumerate(S['fac'][u]): v *= ps[k][tuple(x[j] for j in F)]
            m.append(v)
        M = [[Fr(0)] * N for _ in range(N)]
        for s in range(N):
            x = bits(s, n); pr1 = [th[i][tuple(x[j] for j in S['pa'][u][i])] for i in range(n)]
            for t in range(N):
                y = bits(t, n); v = Fr(1)
                for i in range(n): v *= pr1[i] if y[i] else 1 - pr1[i]
                M[t][s] = v * m[s]
        Ms.append(M); ms.append(m)
    return Ms, ms

def matmul(A, B):
    n, k, m = len(A), len(B), len(B[0])
    return [[sum(A[i][l] * B[l][j] for l in range(k) if A[i][l]) for j in range(m)] for i in range(n)]

def word_prod(Ms, w):
    N = len(Ms[0]); A = [[int(i == j) for j in range(N)] for i in range(N)]
    for u in w: A = matmul(Ms[u], A)
    return A

def full_reset(A):
    N = len(A)
    j0 = next(j for j in range(N) if any(A[i][j] for i in range(N)))
    return all(A[i][k] * A[i0][j0] == A[i0][k] * A[i][j0] for i in range(N) for k in range(N) for i0 in [next(i for i in range(N) if A[i][j0])])

def growth_reset(A, m):
    N = len(A); top = [sum(m[i] * A[i][j] for i in range(N)) for j in range(N)]; bot = [sum(A[i][j] for i in range(N)) for j in range(N)]
    return all(top[j] * bot[0] == top[0] * bot[j] for j in range(N))

# ---------------- Exterior-square descent (exact integer/rational row spaces) ----------------
class RowSpace:
    def __init__(self, D): self.D = D; self.rows = {}   # pivot -> row
    def add(self, v):
        v = list(v)
        for p in sorted(self.rows):
            if v[p]:
                r = self.rows[p]; a, b = r[p], v[p]
                v = [a * x - b * y for x, y in zip(v, r)]
                g = 0
                for x in v:
                    if x: g = math.gcd(g, int(x)) if isinstance(x, int) else 0
                if g > 1: v = [x // g for x in v]
        p = next((i for i, x in enumerate(v) if x), None)
        if p is None: return False
        # make it integer if fractions present
        if any(isinstance(x, Fr) for x in v):
            den = 1
            for x in v:
                if isinstance(x, Fr): den = den * x.denominator // math.gcd(den, x.denominator)
            v = [int(x * den) for x in v]
            g = 0
            for x in v: g = math.gcd(g, x)
            v = [x // g for x in v]
        # eliminate this pivot from existing rows is not needed for dimension counting
        self.rows[p] = v; return True
    def dim(self): return len(self.rows)
    def basis(self): return list(self.rows.values())

def compound2(M):
    N = len(M); pairs = [(i, j) for i in range(N) for j in range(i + 1, N)]
    return [[M[i][k] * M[j][l] - M[i][l] * M[j][k] for (k, l) in pairs] for (i, j) in pairs], pairs

def rowvec_times(v, B):
    D = len(B); out = [0] * D
    for i, x in enumerate(v):
        if x:
            Bi = B[i]
            for j in range(D):
                if Bi[j]: out[j] += x * Bi[j]
    return out

def exterior_horizons_exact(Ms, ms, want=('f', 'g')):
    Bs = []; pairs = None
    for M in Ms:
        B, pairs = compound2(M); Bs.append(B)
    D = len(pairs); res = {}; dims = {}
    if 'f' in want:
        S = RowSpace(D)
        for B in Bs:
            for row in B: S.add(row)
        k, seq = 1, [D, S.dim()]
        if D == 0: res['f'] = 0
        else:
            while True:
                if S.dim() == 0: res['f'] = k; break
                T = RowSpace(D)
                for v in S.basis():
                    for B in Bs: T.add(rowvec_times(v, B))
                if T.dim() == S.dim(): res['f'] = math.inf; seq.append(T.dim()); break
                S = T; k += 1; seq.append(S.dim())
        dims['f'] = seq
    if 'g' in want:
        R = RowSpace(D)
        for m in ms: R.add([m[i] - m[j] for (i, j) in pairs])
        while True:
            d0 = R.dim(); new = []
            for v in R.basis():
                for B in Bs: new.append(rowvec_times(v, B))
            for v in new: R.add(v)
            if R.dim() == d0: break
        S = R; k = 0; seq = [S.dim()]
        while True:
            if S.dim() == 0: res['g'] = k; break
            T = RowSpace(D)
            for v in S.basis():
                for B in Bs: T.add(rowvec_times(v, B))
            if T.dim() == S.dim(): res['g'] = math.inf; seq.append(T.dim()); break
            S = T; k += 1; seq.append(S.dim())
        dims['g'] = seq
    return res, dims
