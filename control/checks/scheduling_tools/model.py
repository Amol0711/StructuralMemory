"""Strict rational history weights and partial deterministic action constraints."""
from dataclasses import dataclass
from fractions import Fraction
from itertools import product


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')
    return value


def rational(value, name='rational', *, positive=False):
    if type(value) not in (str, int, Fraction):
        raise ValueError(f'{name} must be an integer, rational string or Fraction; floats/bools are rejected')
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError(f'Invalid {name}') from exc
    if positive and result <= 0:
        raise ValueError(f'{name} must be strictly positive')
    return result


def encode(value):
    value = Fraction(value)
    return str(value.numerator) if value.denominator == 1 else f'{value.numerator}/{value.denominator}'


def sequence(value, name):
    if type(value) not in (list, tuple):
        raise ValueError(f'{name} must be an array')
    return value


def exact_keys(data, keys, name):
    if type(data) is not dict or set(data) != set(keys):
        raise ValueError(f'{name} must have exactly {sorted(keys)}')


def bounded_power(base, exponent, cap):
    """Return base**exponent, or None when it exceeds cap, without a huge int."""
    if base == 1:
        return 1 if cap >= 1 else None
    value = 1
    for _ in range(exponent):
        if value > cap // base:
            return None
        value *= base
    return value if value <= cap else None


@dataclass(frozen=True, slots=True)
class Constraint:
    actions: int
    states: int
    initial: tuple
    next: tuple

    def __post_init__(self):
        integer(self.actions, 'actions', 1)
        integer(self.states, 'constraint states', 1)
        if type(self.initial) is not tuple or not self.initial:
            raise ValueError('initial must be a nonempty immutable tuple')
        if len(set(self.initial)) != len(self.initial):
            raise ValueError('initial states must be distinct')
        for q in self.initial:
            integer(q, 'initial state')
            if q >= self.states:
                raise ValueError('initial state out of range')
        if type(self.next) is not tuple or len(self.next) != self.states:
            raise ValueError('next must contain one immutable row per constraint state')
        for row in self.next:
            if type(row) is not tuple or len(row) != self.actions:
                raise ValueError('next rows must have one entry per action')
            for q in row:
                if q is not None:
                    integer(q, 'successor state')
                    if q >= self.states:
                        raise ValueError('successor state out of range')

    @classmethod
    def from_dict(cls, data, actions):
        exact_keys(data, {'states', 'initial', 'next'}, 'constraint')
        initial = sequence(data['initial'], 'initial')
        rows = sequence(data['next'], 'next')
        return cls(actions, data['states'], tuple(initial),
                   tuple(tuple(sequence(row, 'next row')) for row in rows))

    def to_dict(self):
        return {'states': self.states, 'initial': list(self.initial),
                'next': [list(row) for row in self.next]}

    def viable_states(self):
        """States admitting an infinite path, by iterative sink deletion."""
        reverse = [[] for _ in range(self.states)]
        degree = [0] * self.states
        for q, row in enumerate(self.next):
            for r in row:
                if r is not None:
                    degree[q] += 1
                    reverse[r].append(q)
        removed = {q for q, d in enumerate(degree) if d == 0}
        stack = list(removed)
        while stack:
            r = stack.pop()
            for q in reverse[r]:
                degree[q] -= 1
                if degree[q] == 0:
                    removed.add(q)
                    stack.append(q)
        return frozenset(set(range(self.states)) - removed)


@dataclass(frozen=True, slots=True)
class HistoryModel:
    actions: int
    memory: int
    weights: tuple
    constraint: Constraint

    def __post_init__(self):
        integer(self.actions, 'actions', 1)
        integer(self.memory, 'memory')
        if not isinstance(self.constraint, Constraint) or self.constraint.actions != self.actions:
            raise ValueError('constraint action alphabet differs from weights')
        if type(self.weights) is not tuple:
            raise ValueError('weights must be an immutable tuple of Fractions')
        if bounded_power(self.actions, self.memory + 1, len(self.weights)) != len(self.weights):
            raise ValueError('exactly actions**(memory+1) weights are required')
        if any(type(x) is not Fraction or x <= 0 for x in self.weights):
            raise ValueError('internal weights must be positive Fractions')

    @classmethod
    def from_dict(cls, data):
        exact_keys(data, {'actions', 'memory', 'weights', 'constraint'}, 'history model')
        actions = integer(data['actions'], 'actions', 1)
        memory = integer(data['memory'], 'memory')
        records = sequence(data['weights'], 'weights')
        if bounded_power(actions, memory + 1, len(records)) != len(records):
            raise ValueError('a complete history/action weight table is required')
        weights = {}
        for record in records:
            exact_keys(record, {'history', 'action', 'value'}, 'weight record')
            history = tuple(sequence(record['history'], 'history'))
            if len(history) != memory:
                raise ValueError('history length differs from memory')
            action = integer(record['action'], 'action')
            for a in (*history, action):
                integer(a, 'action')
                if a >= actions:
                    raise ValueError('action out of range')
            index = 0
            for a in (*history, action):
                index = index * actions + a
            if index in weights:
                raise ValueError('duplicate history/action weight')
            weights[index] = rational(record['value'], 'weight', positive=True)
        return cls(actions, memory, tuple(weights[i] for i in range(len(records))),
                   Constraint.from_dict(data['constraint'], actions))

    def weight(self, history, action):
        index = 0
        for a in (*history, action):
            index = index * self.actions + a
        return self.weights[index]

    def successor_history(self, history, action):
        return (history[1:] + (action,)) if self.memory else ()

    def to_dict(self):
        records = [{'history': list(w), 'action': a, 'value': encode(self.weight(w, a))}
                   for w in product(range(self.actions), repeat=self.memory)
                   for a in range(self.actions)]
        return {'actions': self.actions, 'memory': self.memory, 'weights': records,
                'constraint': self.constraint.to_dict()}


def as_model(value):
    return value if isinstance(value, HistoryModel) else HistoryModel.from_dict(value)
