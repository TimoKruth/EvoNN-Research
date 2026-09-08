"""Crossover-first hierarchy search with bounded niches and clone lineage."""
from collections import Counter
from copy import deepcopy
from random import Random
import math

from evonn_shared.weight_cache import WeightCache
from .compiler import compile_genome
from .genome import HierarchicalGenome,CellGene,seed_genome,crossover,mutate


def _tuples(value):
    return tuple(_tuples(item) for item in value) if isinstance(value,list) else value


def descriptor(genome):
    return dict(macro_depth=genome.macro_depth,average_cell_depth=genome.average_cell_depth,
        max_cell_depth=genome.max_cell_depth,reuse_ratio=genome.reuse_ratio,
        inter_level_connectivity=len(genome.macro_edges),collapsed=len(genome.macro_nodes)==1,
        widths=[node.width for cell in genome.cells for node in cell.nodes])


class Search:
    system='stratograph'
    worker_module='stratograph.cli'
    evaluator_fidelity='hierarchy_features_trained_head'

    def __init__(self,definitions,*,seed,population_size=4,state=None,budget=64,variant='shared'):
        if not 2<=population_size<=16:
            raise ValueError('population size must be in [2,16]')
        self.rng=Random(seed)
        self.size=population_size
        self.budget=budget
        self.variant=variant
        self.definitions={definition.id:definition for definition in definitions}
        self.cache=WeightCache(2*population_size*len(definitions))
        self.operator_stats={}
        self.benchmarks={}
        if state is not None:
            state=deepcopy(state)
            self.rng.setstate(_tuples(state['rng']))
            self.benchmarks=state['benchmarks']
            self.operator_stats=state['operator_stats']
            self.budget,self.variant=state['budget'],state['variant']
            self.cache=WeightCache(2*population_size*len(definitions),state['cache'])
        else:
            for definition in definitions:
                genomes=[seed_genome(definition.task_kind.value,math.prod(definition.input_shape),budget=budget,
                    modality=definition.input_modality.value,variant=variant,index=index) for index in range(population_size)]
                self.benchmarks[definition.id]=dict(population=[g.model_dump(mode='json') for g in genomes],
                    cursor=0,generation=0,evaluated=0,scores=[],archive=[],parents={},operators={},lineage=[],niches={})

    def candidate(self,benchmark):
        state=self.benchmarks[benchmark]
        return HierarchicalGenome.model_validate(state['population'][state['cursor']])

    def compile(self,genome,definition,**options):
        return compile_genome(genome,definition.input_shape,definition.output_dim,definition.input_modality.value,definition.task_kind.value,**options)

    def inherit(self,model,benchmark,namespace):
        state=self.benchmarks[benchmark]
        genome=model.genome
        parents=state['parents'][genome.genome_id] if genome.genome_id in state['parents'] else []
        return self.cache.inherit(model,namespace=namespace,identity=genome.genome_id,topology='hierarchy_proxy',
            family=genome.profile,parents=parents,compatible_groups=[genome.profile])

    def remember(self,model,namespace):
        self.cache.put(namespace,model.genome.genome_id,'hierarchy_proxy',model.genome.profile,model.weights,model.buffers)

    def observe(self,benchmark,genome,result):
        state=self.benchmarks[benchmark]
        entry=dict(genome=genome.model_dump(mode='json'),identity=genome.genome_id,
            quality=result['score'] if result['status']=='ok' else -1e30,parameters=result.get('parameter_count',0))
        state['scores'].append(entry)
        state['cursor']+=1
        state['evaluated']+=1
        if result['status']=='ok':
            unique={item['identity']:item for item in state['archive']}
            if genome.genome_id not in unique or unique[genome.genome_id]['quality']<entry['quality']:
                unique[genome.genome_id]=entry
            state['archive']=sorted(unique.values(),key=lambda item:(-item['quality'],item['identity']))[:2*self.size]
            niche=f'{genome.macro_depth}:{round(genome.reuse_ratio,1)}:{genome.max_cell_depth}'
            if niche not in state['niches'] or state['niches'][niche]['quality']<entry['quality']:
                state['niches'][niche]=entry
            if len(state['niches'])>16:
                state['niches']=dict(sorted(state['niches'].items(),key=lambda pair:-pair[1]['quality'])[:16])
        if genome.genome_id in state['operators']:
            op,baseline=state['operators'][genome.genome_id]
            if op not in self.operator_stats:
                self.operator_stats[op]=dict(uses=0,successes=0)
            self.operator_stats[op]['uses']+=1
            self.operator_stats[op]['successes']+=int(entry['quality']>baseline)
        if state['cursor']==self.size:
            self._reproduce(benchmark)

    def _reproduce(self,benchmark):
        state=self.benchmarks[benchmark]
        pool=state['scores']
        children=[]
        parents={}
        operators={}
        for _ in range(self.size):
            a=max(self.rng.sample(pool,min(2,len(pool))),key=lambda item:item['quality'])
            b=self.rng.choice(pool)
            child=crossover(HierarchicalGenome.model_validate(a['genome']),HierarchicalGenome.model_validate(b['genome']),self.rng,budget=self.budget)
            motifs=[CellGene.model_validate(cell) for entry in state['archive'] for cell in entry['genome']['cells']]
            child,op=mutate(child,self.rng,budget=self.budget,motif_bank=motifs)
            while child.genome_id in parents:
                child=HierarchicalGenome.model_validate({**child.model_dump(),'learning_rate':self.rng.uniform(.0005,.009)})
            children.append(child.model_dump(mode='json'))
            parents[child.genome_id]=[a['identity'],b['identity']]
            operators[child.genome_id]=[op,a['quality']]
            state['lineage'].append(dict(child=child.genome_id,parents=parents[child.genome_id],operator=op,
                crossover=True,generation=state['generation']+1))
        state.update(population=children,cursor=0,generation=state['generation']+1,scores=[],parents=parents,operators=operators)
        state['lineage']=state['lineage'][-256:]

    def telemetry(self):
        descriptions={key:[descriptor(HierarchicalGenome.model_validate(g)) for g in state['population']] for key,state in self.benchmarks.items()}
        return dict(schema_version='1.0.0',system=self.system,evaluator_fidelity=self.evaluator_fidelity,
            hierarchy=descriptions,operator_success=self.operator_stats,
            motif_frequency={key:dict(Counter(cell['primitive'] for genome in state['population'] for gene in genome['cells'] for cell in gene['nodes'])) for key,state in self.benchmarks.items()},
            lineage={key:state['lineage'] for key,state in self.benchmarks.items()},
            occupied_niches={key:len(state['niches']) for key,state in self.benchmarks.items()},
            clone_specialize_counts={name:self.operator_stats[name]['uses'] if name in self.operator_stats else 0 for name in ('clone','specialize')},
            generations={key:state['generation'] for key,state in self.benchmarks.items()},
            evaluation_cache_hits=0,promotion_screen='disabled')

    def state(self):
        return dict(rng=self.rng.getstate(),benchmarks=self.benchmarks,operator_stats=self.operator_stats,
            cache=self.cache.state(),budget=self.budget,variant=self.variant)
