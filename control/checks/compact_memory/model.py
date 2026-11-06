"""Exact pair-state dynamics for selected-root structural-memory queries.

Coordinates/actions are zero-based. Integer bit masks are finite sets, not
unit-cost arithmetic: their cost grows with the number of coordinates.
"""
from dataclasses import dataclass


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer at least {minimum}")
    return value


def _sequence(value, name):
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{name} must be a list or tuple")
    return value


def _indices_mask(value, n, name):
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise ValueError(f"{name} must be a collection of coordinate indices")
    mask = 0
    for coordinate in value:
        _integer(coordinate, name + " coordinate")
        if coordinate >= n:
            raise ValueError(f"{name} contains an out-of-range coordinate")
        mask |= 1 << coordinate
    return mask


def _bits(mask):
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


@dataclass(frozen=True, slots=True)
class Structure:
    """Validated structure; pa/fac internally store immutable bit-mask tuples.

    Use from_dict for ordinary parent/scope lists. A direct constructor takes
    mask tuples and validates them as well. Separate repeated fitness scopes
    are retained, while duplicate coordinates within one scope are normalized.
    """

    n: int
    U: int
    pa: tuple
    fac: tuple

    def __post_init__(self):
        _integer(self.n, "n")
        _integer(self.U, "U", 1)
        if type(self.pa) is not tuple or type(self.fac) is not tuple:
            raise ValueError("Internal pa and fac must be immutable tuples")
        if len(self.pa) != self.U or len(self.fac) != self.U:
            raise ValueError("pa and fac must each contain U actions")
        for u, parents in enumerate(self.pa):
            if type(parents) is not tuple or len(parents) != self.n:
                raise ValueError(f"pa[{u}] must contain n parent masks")
        for name, actions in (("pa", self.pa), ("fac", self.fac)):
            for u, masks in enumerate(actions):
                if type(masks) is not tuple:
                    raise ValueError(f"{name}[{u}] must be an immutable tuple")
                for mask in masks:
                    _integer(mask, name + " mask")
                    if mask.bit_length() > self.n:
                        raise ValueError(f"{name}[{u}] contains an out-of-range mask")

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != {"n", "U", "pa", "fac"}:
            raise ValueError("A structure must have exactly n, U, pa and fac")
        n = _integer(data["n"], "n")
        actions = _integer(data["U"], "U", 1)
        pa = _sequence(data["pa"], "pa")
        fac = _sequence(data["fac"], "fac")
        if len(pa) != actions or len(fac) != actions:
            raise ValueError("pa and fac must each contain U actions")
        parent_masks = []
        scope_masks = []
        for u in range(actions):
            parents = _sequence(pa[u], f"pa[{u}]")
            scopes = _sequence(fac[u], f"fac[{u}]")
            if len(parents) != n:
                raise ValueError(f"pa[{u}] must contain n parent lists")
            parent_masks.append(tuple(_indices_mask(p, n, f"pa[{u}][{i}]")
                                      for i, p in enumerate(parents)))
            scope_masks.append(tuple(_indices_mask(f, n, f"fac[{u}][{k}]")
                                     for k, f in enumerate(scopes)))
        return cls(n, actions, tuple(parent_masks), tuple(scope_masks))

    def to_dict(self):
        return {"n": self.n, "U": self.U,
                "pa": [[list(_bits(p)) for p in action] for action in self.pa],
                "fac": [[list(_bits(f)) for f in action] for action in self.fac]}

    @property
    def fitness_unions(self):
        answer = []
        for scopes in self.fac:
            union = 0
            for scope in scopes:
                union |= scope
            answer.append(union)
        return tuple(answer)


@dataclass(frozen=True, slots=True)
class PairState:
    root: int
    pairs: tuple

    def __post_init__(self):
        _integer(self.root, "root")
        if type(self.pairs) is not tuple:
            raise ValueError("pairs must be an immutable tuple of row masks")
        for row in self.pairs:
            _integer(row, "pair row")

    def to_dict(self):
        return {"root": self.root, "pairs": list(self.pairs)}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != {"root", "pairs"}:
            raise ValueError("A state must have exactly root and pairs")
        return cls(data["root"], tuple(_sequence(data["pairs"], "pairs")))


def _structure(structure):
    if isinstance(structure, Structure):
        return structure
    return Structure.from_dict(structure)


def _action(structure, action):
    _integer(action, "action")
    if action >= structure.U:
        raise ValueError("Action is outside the action alphabet")
    return action


def validate_state(structure, state):
    structure = _structure(structure)
    if not isinstance(state, PairState):
        raise ValueError("Expected a PairState")
    n = structure.n
    if state.root.bit_length() > n or len(state.pairs) != n:
        raise ValueError("State dimensions do not match structure")
    for i, row in enumerate(state.pairs):
        if row.bit_length() > n or not row & (1 << i):
            raise ValueError("Pair relation must be reflexive and in range")
        if state.root & (1 << i) and state.root & ~row:
            raise ValueError("Root support must be a clique in the pair relation")
        for j in _bits(row):
            if not state.pairs[j] & (1 << i):
                raise ValueError("Pair relation must be symmetric")
    return state


def initial_state(structure):
    structure = _structure(structure)
    roots = (1 << structure.n) - 1
    return PairState(roots, (roots,) * structure.n)


def transition(structure, state, action):
    """Process separate fitness scopes, then parents and fresh innovations."""
    structure = _structure(structure)
    validate_state(structure, state)
    action = _action(structure, action)
    root = state.root
    rows = list(state.pairs)
    for scope in structure.fac[action]:
        touched = 0
        for i in _bits(scope):
            touched |= rows[i]
        # Add only this clique. Overlapping cones do not justify a transitive
        # closure of the relation. The root test is scope & root, not H & root.
        for i in _bits(touched):
            rows[i] |= touched
        if scope & root:
            root |= touched

    parents = structure.pa[action]
    next_root = 0
    next_rows = []
    for i, parent_mask in enumerate(parents):
        if parent_mask & root:
            next_root |= 1 << i
        incident = 0
        for parent in _bits(parent_mask):
            incident |= rows[parent]
        row = 1 << i
        for j, other_parents in enumerate(parents):
            if incident & other_parents:
                row |= 1 << j
        next_rows.append(row)
    return PairState(next_root, tuple(next_rows))


def replay(structure, word, state=None):
    structure = _structure(structure)
    if state is None:
        state = initial_state(structure)
    else:
        validate_state(structure, state)
    if not isinstance(word, (list, tuple)):
        raise ValueError("A word must be a finite list or tuple of actions")
    for action in word:
        state = transition(structure, state, action)
    return state


def full_connected(state):
    if not isinstance(state, PairState):
        raise ValueError("Expected a PairState")
    return state.root != 0


def growth_connected(structure, state, next_action):
    structure = _structure(structure)
    validate_state(structure, state)
    next_action = _action(structure, next_action)
    return bool(state.root & structure.fitness_unions[next_action])
