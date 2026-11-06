"""Exact finite-population study of transient control and periodic phases.

Enumerate all legal binary action words through length twelve. Full eight-state
propagation uses an existing independent oracle; the four-state visible model
is constructed separately here from its two coordinate update probabilities.
All scientific comparisons use fractions.Fraction. Decimal plot columns are
presentation-only conversions of exact saved rational values.
"""
from pathlib import Path
from fractions import Fraction as F
from itertools import product
import argparse,csv,hashlib,json,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'checks'))
from control_validation.oracles import matrices as eight_state_matrices
from control_validation.oracles import constraints as reference_constraints, model_data
from scheduling_tools import finite_horizon

REGIMES=('unrestricted','no11','alternating')
CYCLES={'unrestricted':(0,0,1,1),'no11':(0,0,1),'alternating':(0,1)}
VISIBLE_LAWS={
 'uniform':(F(1,4),F(1,4),F(1,4),F(1,4)),
 'correlated':(F(1,2),F(0),F(0),F(1,2)),
 'anticorrelated':(F(0),F(1,2),F(1,2),F(0)),
}


def require(condition,message):
 if not condition:raise RuntimeError(message)


def four_state_matrices():
 states=tuple(product((0,1),repeat=2));answer=[]
 for action in (0,1):
  matrix=[]
  for next_a,next_c in states:
   row=[]
   for old_a,old_c in states:
    probability_a=F(9,10) if next_a==action else F(1,10)
    probability_c=F(9,10) if next_c==old_a else F(1,10)
    fitness=F(3,2) if old_c==action else F(1,4)
    row.append(fitness*probability_a*probability_c)
   matrix.append(row)
  answer.append(matrix)
 return answer


def multiply(matrix,vector):
 return tuple(sum((a*b for a,b in zip(row,vector)),F(0)) for row in matrix)


def project(vector):
 return tuple(vector[2*i]+vector[2*i+1] for i in range(4))


def allowed(regime,word,action):
 if regime=='unrestricted':return True
 if regime=='no11':return not ((word[-1] if word else 0)==action==1)
 if regime=='alternating':return not word or word[-1]!=action
 raise ValueError(regime)


def wordstr(word):return ''.join(str(a) for a in word)


def repeated(phase,length):return (phase*((length+len(phase)-1)//len(phase)))[:length]


def legal_infinite_phases(regime):
 cycle=CYCLES[regime]
 phases=sorted({cycle[i:]+cycle[:i] for i in range(len(cycle))})
 # These restrictions depend only on adjacent actions. Check a legal initial
 # action and all cyclic adjacencies, including the period boundary.
 result=[]
 for phase in phases:
  check=repeated(phase,2*len(phase)+1)
  if all(allowed(regime,check[:i],a) for i,a in enumerate(check)):result.append(phase)
 require(tuple(cycle) in result,'Chosen fixed phase is not indefinitely legal')
 return result


def scientific_input(full,visible,max_horizon):
 return {
  'schema':'finite-control-transient-input.v1','max_horizon':max_horizon,
  'state_order_full':[''.join(map(str,x)) for x in product((0,1),repeat=3)],
  'state_order_visible':[''.join(map(str,x)) for x in product((0,1),repeat=2)],
  'initial_visible_laws':{k:list(map(str,v)) for k,v in VISIBLE_LAWS.items()},
  'initial_hidden':'independent Bernoulli(1/2)',
  'constraints':{
   'unrestricted':'Every binary word is legal.',
   'no11':'Last-action state initially 0; transition 1 with action 1 forbidden; either first action allowed.',
   'alternating':'Either first action, then only the opposite preceding action.'},
  'fixed_periodic_phases':{k:wordstr(v) for k,v in CYCLES.items()},
  'legal_periodic_phases':{k:[wordstr(p) for p in legal_infinite_phases(k)] for k in REGIMES},
  'tie_rule':'For both minimum and maximum mass choose the lexicographically smallest legal finite word; phase ties use lexicographically smallest phase after finite-word ties.',
  'matrix_convention':'Rows are next states; columns are old states; selection precedes independent coordinate transitions.',
  'full_matrices':[[list(map(str,row)) for row in matrix] for matrix in full],
  'visible_matrices':[[list(map(str,row)) for row in matrix] for matrix in visible],
  'arithmetic':'Exact Fraction rational arithmetic; decimal data columns are for plotting only.'}


def run(output,max_horizon=12):
 from output_guard import fresh_output
 output=fresh_output(output)
 output.mkdir(parents=True,exist_ok=True)
 summary_path=output/'summary.json'
 summary_path.write_text(json.dumps({'status':'running'},indent=2)+'\n')
 full=eight_state_matrices();visible=four_state_matrices()
 for a in (0,1):
  for old in range(8):
   lhs=project(tuple(full[a][row][old] for row in range(8)))
   rhs=tuple(visible[a][row][old//2] for row in range(4))
   require(lhs==rhs,'Exact marginal matrix intertwining failed')
 input_data=scientific_input(full,visible,max_horizon)
 (output/'input.json').write_text(json.dumps(input_data,indent=2,sort_keys=True)+'\n')
 rows=[];word_records=[];by_case={};prefix_records=[]
 agreements=0;history_checks=0
 for population,p4 in VISIBLE_LAWS.items():
  p8=tuple(value/2 for value in p4 for _ in (0,1))
  require(project(p8)==p4 and sum(p8,F(0))==1,'Initial marginal mismatch')
  for regime in REGIMES:
   current={(): (p8,p4)};masses={};counts=[];case_rows=[]
   phases=legal_infinite_phases(regime)
   for length in range(max_horizon+1):
    values={}
    for word,(z8,z4) in current.items():
     require(project(z8)==z4,'Visible-vector mismatch at '+wordstr(word))
     mass8,mass4=sum(z8,F(0)),sum(z4,F(0))
     require(mass8==mass4 and mass8>0,'Mass mismatch')
     agreements+=1;values[word]=mass8;masses[word]=mass8
     if length>=2:
      predicted=masses[word[:2]]
      for t in range(2,length):predicted*=F(51,40) if word[t]==word[t-2] else F(19,40)
      require(predicted==mass8,'Exact history factorization mismatch')
      history_checks+=1
     word_records.append({'population':population,'constraint':regime,'horizon':length,'word':wordstr(word),'mass_full':str(mass8),'mass_visible':str(mass4)})
    require(values,'No legal word in a stipulated feasible regime')
    counts.append(len(values))
    low,high=min(values.values()),max(values.values())
    low_words=sorted(w for w,v in values.items() if v==low)
    high_words=sorted(w for w,v in values.items() if v==high)
    fixed_word=repeated(CYCLES[regime],length)
    require(fixed_word in values,'Fixed periodic word absent from legal tree')
    candidates=sorted((values[repeated(phase,length)],repeated(phase,length),phase) for phase in phases)
    best_mass,best_word,best_phase=candidates[0]
    require(low<=best_mass<=values[fixed_word]<=high,'Phase comparison ordering fails')
    row={'population':population,'constraint':regime,'horizon':length,'legal_words':len(values),
      'minimum_mass':str(low),'minimum_word':wordstr(low_words[0]),'minimum_ties':len(low_words),
      'maximum_mass':str(high),'maximum_word':wordstr(high_words[0]),'maximum_ties':len(high_words),
      'fixed_cycle_phase':wordstr(CYCLES[regime]),'fixed_cycle_word':wordstr(fixed_word),'fixed_cycle_mass':str(values[fixed_word]),
      'best_cycle_phase':wordstr(best_phase),'best_cycle_word':wordstr(best_word),'best_cycle_mass':str(best_mass),
      'fixed_to_optimum':str(values[fixed_word]/low),'best_phase_to_optimum':str(best_mass/low),
      'minimum_mass_float':float(low),'maximum_mass_float':float(high),
      'fixed_cycle_mass_float':float(values[fixed_word]),'best_cycle_mass_float':float(best_mass),
      'fixed_to_optimum_float':float(values[fixed_word]/low),'best_phase_to_optimum_float':float(best_mass/low)}
    rows.append(row);case_rows.append(row)
    if length==2 and regime=='unrestricted':
     prefix_records.append({'population':population,'masses':{wordstr(w):str(v) for w,v in sorted(values.items())}})
    if length<max_horizon:
     nxt={}
     for word,(z8,z4) in current.items():
      for action in (0,1):
       if allowed(regime,word,action):nxt[word+(action,)]=(multiply(full[action],z8),multiply(visible[action],z4))
     current=nxt
   by_case[population+'/'+regime]={'counts_by_horizon':counts,'total_word_population_checks':sum(counts),
       'fixed_phase_suboptimal_horizons':[r['horizon'] for r in case_rows if F(r['fixed_to_optimum'])>1],
       'best_phase_suboptimal_horizons':[r['horizon'] for r in case_rows if F(r['best_phase_to_optimum'])>1],
       'largest_fixed_to_optimum':str(max(F(r['fixed_to_optimum']) for r in case_rows)),
       'largest_best_phase_to_optimum':str(max(F(r['best_phase_to_optimum']) for r in case_rows))}
 # Independent finite-history dynamic programming checks extremal values.
 # Its witness tie rule is not used: the enumeration above explicitly selects
 # the lexicographically smallest minimizer and maximizer among all words.
 dp_checks=0
 for row in rows:
  p4=VISIBLE_LAWS[row['population']]
  p8=tuple(value/2 for value in p4 for _ in (0,1))
  answer=finite_horizon(full,model_data(reference_constraints()[row['constraint']]),p8,row['horizon'])
  require(answer['status']=='optimal','Independent DP failed to resolve')
  require(answer['minimum']['mass']==row['minimum_mass'] and answer['maximum']['mass']==row['maximum_mass'],'Independent DP extremum mismatch')
  dp_checks+=1
 for regime in REGIMES:
  expected=[];f0,f1=1,2
  for length in range(max_horizon+1):
   if regime=='unrestricted':expected.append(2**length)
   elif regime=='alternating':expected.append(1 if length==0 else 2)
   else:
    expected.append(f0);f0,f1=f1,f0+f1
  for population in VISIBLE_LAWS:require(by_case[population+'/'+regime]['counts_by_horizon']==expected,'Legal word count mismatch')
 for name,records in [('finite_horizons.csv',rows),('all_legal_word_masses.csv',word_records)]:
  with (output/name).open('w',newline='') as handle:
   writer=csv.DictWriter(handle,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
 (output/'finite_horizons.json').write_text(json.dumps(rows,indent=2)+'\n')
 (output/'two_step_prefixes.json').write_text(json.dumps(prefix_records,indent=2)+'\n')
 # Single whitespace-delimited table for PGFPlots; records stay exact in CSV/JSON.
 columns=['T']
 for regime in REGIMES:
  for population in VISIBLE_LAWS:
   columns.extend([regime+'_'+population+'_optimal',regime+'_'+population+'_fixed_ratio',regime+'_'+population+'_phase_ratio'])
 lookup={(r['constraint'],r['population'],r['horizon']):r for r in rows}
 with (output/'control_transients.dat').open('w') as handle:
  handle.write(' '.join(columns)+'\n')
  for length in range(max_horizon+1):
   fields=[str(length)]
   for regime in REGIMES:
    for population in VISIBLE_LAWS:
     row=lookup[regime,population,length]
     fields.extend(format(float(F(row[key])),'.17g') for key in ['minimum_mass','fixed_to_optimum','best_phase_to_optimum'])
   handle.write(' '.join(fields)+'\n')
 expected_prefixes={'uniform':['49/64']*4,'correlated':['69/64','29/64','29/64','69/64'],
                    'anticorrelated':['29/64','69/64','69/64','29/64']}
 for record in prefix_records:require(list(record['masses'].values())==expected_prefixes[record['population']],'Prior exact prefix values not reproduced')
 source=ROOT/'checks/control_validation/oracles.py'
 summary={'status':'passed','schema':'finite-control-transient-study.v1','max_horizon':max_horizon,
   'initial_populations':3,'constraints':3,'optimization_queries':len(rows),'mass_and_marginal_agreements':agreements,
   'history_factorization_checks':history_checks,'matrix_intertwining_columns':16,'independent_dynamic_programming_extrema_checks':dp_checks,
   'all_exact':True,'results':by_case,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
   'eight_state_oracle_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
   'limitations':'Finite exact enumeration through the specified maximum horizon; not an all-horizon optimality proof. Only the baseline model is evaluated here. Periodic phase comparisons use legal infinite rotations; constrained finite-horizon minima are computed independently.'}
 summary['artifact_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir()) if p.is_file() and p.name!='summary.json'}
 summary_path.write_text(json.dumps(summary,indent=2)+'\n')
 return summary


def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--output',type=Path,default=ROOT/'reruns/transients')
 ap.add_argument('--max-horizon',type=int,default=12)
 args=ap.parse_args()
 if args.max_horizon<2:raise ValueError('The study requires at least horizon two')
 result=run(args.output.resolve(),args.max_horizon)
 print(json.dumps({k:v for k,v in result.items() if k not in {'results','artifact_sha256'}},indent=2))

if __name__=='__main__':main()
