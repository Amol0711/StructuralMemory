"""Exact positive-matrix memory verification and finite-horizon optimization."""
from fractions import Fraction
from itertools import product
from .model import as_model, rational, encode, integer, sequence, bounded_power


def matrix_family(matrices):
    family=sequence(matrices,'matrices')
    if not family:raise ValueError('matrices must be nonempty')
    n=len(sequence(family[0],'matrix'))
    if n==0:raise ValueError('matrix dimension must be positive')
    result=[]
    for matrix in family:
        sequence(matrix,'matrix')
        if len(matrix)!=n:raise ValueError('matrix dimensions disagree')
        rows=[]
        for row in matrix:
            sequence(row,'matrix row')
            if len(row)!=n:raise ValueError('matrices must be square')
            rows.append(tuple(rational(x,'matrix entry',positive=True) for x in row))
        result.append(tuple(rows))
    return tuple(result)


def _identity(n):
    return tuple(tuple(Fraction(i==j) for j in range(n)) for i in range(n))


def _multiply(left,right):
    n=len(left)
    return tuple(tuple(sum((left[i][k]*right[k][j] for k in range(n)),Fraction(0))
                       for j in range(n)) for i in range(n))


def _apply(matrix,vector):
    return tuple(sum((a*b for a,b in zip(row,vector)),Fraction(0)) for row in matrix)


def certify_history_weights(matrices, memory, *, max_histories=10000):
    """Verify every next-action ratio on every initial column, exactly.

    Input matrices must be strictly positive. No numerical rank or approximate
    reset criterion is used. Limits count length-memory histories, not bits or
    matrix arithmetic. A failed identity is reported with an exact witness.
    """
    family=matrix_family(matrices)
    memory=integer(memory,'memory')
    max_histories=integer(max_histories,'max_histories')
    actions=len(family);n=len(family[0])
    count=bounded_power(actions,memory,max_histories)
    result={'schema':'structural-memory.history-weight-verification.v1',
            'status':None,'memory':memory,'actions':actions,'dimension':n,
            'weights':None,'histories_checked':0,'column_ratio_checks':0,'reason':None}
    if count is None:
        result.update(status='unknown',reason='max_histories')
        return result
    records=[]
    masses=[tuple(sum(matrix[i][j] for i in range(n)) for j in range(n)) for matrix in family]
    for word in product(range(actions),repeat=memory):
        accumulated=_identity(n)
        for action in word:accumulated=_multiply(family[action],accumulated)
        denominator=tuple(sum(accumulated[i][j] for i in range(n)) for j in range(n))
        for action in range(actions):
            numerator=tuple(sum(masses[action][i]*accumulated[i][j] for i in range(n)) for j in range(n))
            reference=numerator[0]/denominator[0]
            for j in range(n):
                result['column_ratio_checks']+=1
                ratio=numerator[j]/denominator[j]
                if ratio!=reference:
                    result.update(status='not_memory',reason='unequal_column_growth_ratios',
                                  witness={'history':list(word),'action':action,'columns':[0,j],
                                           'ratios':[encode(reference),encode(ratio)]})
                    return result
            records.append({'history':list(word),'action':action,'value':encode(reference)})
        result['histories_checked']+=1
    result.update(status='certified',weights=records)
    return result


def finite_horizon(matrices, model, p, horizon, *, require_extendable=True,
                   max_steps=100000,max_prefixes=100000,max_histories=10000):
    """Exact minimum/maximum mass with initial-composition-dependent warm-up.

    Default words extend to an infinite constraint-admissible schedule.
    require_extendable=False optimizes all words legal through the requested
    finite horizon, including terminal dead ends. The first min(L,T) steps use
    direct matrix propagation. Tail DP uses only exactly verified weights.
    """
    model=as_model(model);family=matrix_family(matrices)
    if len(family)!=model.actions:raise ValueError('matrix and history action alphabets differ')
    horizon=integer(horizon,'horizon')
    if type(require_extendable) is not bool:raise ValueError('require_extendable must be Boolean')
    for name,value,lower in [('max_steps',max_steps,0),('max_prefixes',max_prefixes,1),('max_histories',max_histories,0)]:
        integer(value,name,lower)
    composition=tuple(rational(x,'composition') for x in sequence(p,'composition'))
    if len(composition)!=len(family[0]) or any(x<0 for x in composition) or sum(composition)!=1:
        raise ValueError('composition must be a probability vector of the matrix dimension')
    result={'schema':'structural-memory.finite-scheduling.v1','status':None,'reason':None,
            'horizon':horizon,'require_extendable':require_extendable,'minimum':None,'maximum':None,
            'history_weights_checked':False,'steps':0,'warmup_length':min(horizon,model.memory)}

    def stop(reason):
        result.update(status='unknown',reason=reason)
        return result

    if horizon>model.memory:
        verified=certify_history_weights(family,model.memory,max_histories=max_histories)
        if verified['status']=='unknown':return stop('max_histories')
        if verified['status']!='certified':raise ValueError('matrices do not have the supplied memory upper bound')
        exact=tuple(Fraction(r['value']) for r in verified['weights'])
        if exact!=model.weights:raise ValueError('supplied history weights disagree with the matrix ratios')
        result['history_weights_checked']=True
    viable=model.constraint.viable_states() if require_extendable else frozenset(range(model.constraint.states))
    starts=[q for q in model.constraint.initial if q in viable]
    if not starts:
        result.update(status='infeasible',reason='no_admissible_initial_state')
        return result
    # Equal word/state keys have the same unnormalized vector, even if reached
    # from different admissible initial automaton states.
    prefixes={((),q):(composition,q) for q in starts}
    if len(prefixes)>max_prefixes:return stop('max_prefixes')
    for _ in range(min(horizon,model.memory)):
        following={}
        for (word,q),(vector,origin) in prefixes.items():
            for action,r in enumerate(model.constraint.next[q]):
                if r is None or r not in viable:continue
                if result['steps']>=max_steps:return stop('max_steps')
                result['steps']+=1
                key=(word+(action,),r)
                if key not in following:
                    if len(following)>=max_prefixes:return stop('max_prefixes')
                    following[key]=(_apply(family[action],vector),origin)
        prefixes=following
        if not prefixes:
            result.update(status='infeasible',reason='no_legal_word_of_requested_length')
            return result
    # Each record holds (mass, full action word, initial constraint state).
    current={key:((sum(vector),key[0],origin),(sum(vector),key[0],origin))
             for key,(vector,origin) in prefixes.items()}
    for _ in range(max(0,horizon-model.memory)):
        following={}
        for (history,q),records in current.items():
            for action,r in enumerate(model.constraint.next[q]):
                if r is None or r not in viable:continue
                if result['steps']>=max_steps:return stop('max_steps')
                result['steps']+=1
                key=(model.successor_history(history,action),r)
                factor=model.weight(history,action)
                candidates=tuple((mass*factor,word+(action,),origin) for mass,word,origin in records)
                if key not in following:
                    if len(following)>=max_prefixes:return stop('max_prefixes')
                    following[key]=candidates
                else:
                    old_min,old_max=following[key]
                    following[key]=(candidates[0] if candidates[0][0]<old_min[0] else old_min,
                                    candidates[1] if candidates[1][0]>old_max[0] else old_max)
        current=following
        if not current:
            result.update(status='infeasible',reason='no_legal_word_of_requested_length')
            return result
    low=min((records[0] for records in current.values()),key=lambda x:x[0])
    high=max((records[1] for records in current.values()),key=lambda x:x[0])
    for kind,(mass,word,origin) in [('minimum',low),('maximum',high)]:
        result[kind]={'mass':encode(mass),'word':list(word),'initial_constraint_state':origin}
    result['status']='optimal'
    return result
