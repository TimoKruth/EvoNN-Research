"""Hierarchy-first genomes: macro routing over reusable micrograph programs."""
from collections import Counter
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator, model_serializer


class Gene(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True,allow_inf_nan=False)


class Edge(Gene):
    source: str
    target: str


class CellNodeGene(Gene):
    id: str=Field(pattern=r'^[a-z][a-z0-9_]{0,31}$')
    width: int=Field(default=16,ge=4,le=64,strict=True)
    activation: Literal['relu','tanh','gelu','silu']='gelu'
    primitive: str=Field(default='projection', pattern=r'^[a-z][a-z0-9_]{0,31}$')
    projection_seed: int | None=Field(default=None, ge=0, lt=2**32, strict=True)

    @model_serializer(mode='wrap')
    def serialized(self, handler):
        value=handler(self)
        if self.projection_seed is None:
            value.pop('projection_seed', None)
        return value


def order(nodes,edges,output):
    ids=[n.id for n in nodes]
    if not ids or len(ids)!=len(set(ids)) or output not in ids:
        raise ValueError('distinct nodes and a declared output required')
    if len({(e.source,e.target) for e in edges})!=len(edges):
        raise ValueError('duplicate graph edges')
    incoming={name:[] for name in ids}
    outgoing={name:[] for name in ids}
    for edge in edges:
        if edge.source not in incoming or edge.target not in incoming or edge.source==edge.target:
            raise ValueError('invalid graph edge')
        incoming[edge.target].append(edge.source)
        outgoing[edge.source].append(edge.target)
    degrees={name:len(parents) for name,parents in incoming.items()}
    ready=sorted(name for name,value in degrees.items() if value==0)
    ordered=[]
    while ready:
        name=ready[0]
        del ready[0]
        ordered.append(name)
        for target in sorted(outgoing[name]):
            degrees[target]-=1
            if degrees[target]==0:
                ready.append(target)
                ready.sort()
    if len(ordered)!=len(ids):
        raise ValueError('graph must be acyclic')
    ancestors={output}
    for name in reversed(ordered):
        if name in ancestors:
            ancestors.update(incoming[name])
    if ancestors!=set(ids):
        raise ValueError('every node must reach output')
    depth={}
    for name in ordered:
        depth[name]=1+max((depth[parent] for parent in incoming[name]),default=0)
    return ordered,incoming,depth[output]


class CellGene(Gene):
    id: str=Field(pattern=r'^[a-z][a-z0-9_]{0,31}$')
    nodes: tuple[CellNodeGene,...]=Field(min_length=1,max_length=6)
    edges: tuple[Edge,...]
    output: str
    origin: str | None=None
    parameter_id: str | None=Field(default=None, pattern=r"^[a-f0-9]{16}$")
    origin_parameter_id: str | None=Field(default=None, pattern=r"^[a-f0-9]{16}$")

    @model_serializer(mode="wrap")
    def serialized(self, handler):
        value=handler(self)
        for key in ("parameter_id", "origin_parameter_id"):
            if value[key] is None:
                del value[key]
        return value

    @model_validator(mode='after')
    def valid(self):
        order(self.nodes,self.edges,self.output)
        return self

    @property
    def depth(self):
        return order(self.nodes,self.edges,self.output)[2]

    @property
    def program_id(self):
        # Arbitrary cell IDs/lineage do not alter initial projection functions.
        return _digest(dict(nodes=[n.model_dump() for n in self.nodes],edges=[e.model_dump() for e in self.edges],output=self.output))


class MacroNodeGene(Gene):
    id: str=Field(pattern=r'^[a-z][a-z0-9_]{0,31}$')
    cell_id: str


class HierarchicalGenome(Gene):
    schema_version: Literal[1,2]=1
    execution: dict | None=None
    macro_nodes: tuple[MacroNodeGene,...]=Field(min_length=1,max_length=8)
    macro_edges: tuple[Edge,...]
    cells: tuple[CellGene,...]=Field(min_length=1,max_length=8)
    output: str
    profile: Literal['tabular','high_dimensional','regression','image','language_modeling']='tabular'
    variant: Literal['flat','unshared','shared','no-clone','no-motif-bias']='shared'
    learning_rate: float=Field(default=.003,gt=0,le=.1)
    weight_decay: float=Field(default=.01,ge=0,le=.1)

    @model_validator(mode='after')
    def valid(self):
        if self.schema_version == 1:
            if self.execution is not None or any(c.parameter_id is not None or c.origin_parameter_id is not None for c in self.cells) or any(n.projection_seed is not None or n.primitive not in ('projection','gate','residual','sequence') for c in self.cells for n in c.nodes):
                raise ValueError('v2 fields require genome schema 2')
        else:
            from .research import ResearchPolicy
            from .operators import OPERATORS
            policy=ResearchPolicy.model_validate(self.execution)
            if policy.model_dump(mode="json") != self.execution:
                raise ValueError("v2 execution policy must be canonical and explicit")
            if any(c.parameter_id is None for c in self.cells) or len({c.parameter_id for c in self.cells}) != len(self.cells):
                raise ValueError("v2 cells require unique persistent parameter identities")
            if len(self.macro_nodes)>policy.max_macro_nodes or any(len(c.nodes)>policy.max_cell_nodes or any(n.width>policy.max_width or n.projection_seed is None or n.primitive not in OPERATORS for n in c.nodes) for c in self.cells):
                raise ValueError('genome exceeds declared envelope or has an unsupported primitive')
        ids={cell.id for cell in self.cells}
        if len(ids)!=len(self.cells) or {node.cell_id for node in self.macro_nodes}!=ids:
            raise ValueError('unique cell library must match all macro references')
        order(self.macro_nodes,self.macro_edges,self.output)
        if self.variant=='flat' and len(self.macro_nodes)!=1:
            raise ValueError('flat ablation has exactly one macro node')
        if self.variant=='unshared' and len(self.cells)!=len(self.macro_nodes):
            raise ValueError('unshared ablation has a distinct cell per macro node')
        return self

    @model_serializer(mode='wrap')
    def serialized(self, handler):
        value=handler(self)
        if self.schema_version == 1:
            value.pop('execution', None)
        return value

    @property
    def genome_id(self):
        return _digest(self.model_dump(mode='json'))

    @property
    def macro_depth(self):
        return order(self.macro_nodes,self.macro_edges,self.output)[2]

    @property
    def reuse_ratio(self):
        return 1-len(self.cells)/len(self.macro_nodes)

    @property
    def max_cell_depth(self):
        return max(cell.depth for cell in self.cells)

    @property
    def average_cell_depth(self):
        return sum(cell.depth for cell in self.cells)/len(self.cells)


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def depth_limit(budget):
    return min(8,2+max(0,int(budget)//16))


def seed_genome(task,input_dim,*,budget=64,modality='tabular',variant='shared',index=0):
    profile=('language_modeling' if task=='language_modeling' else 'regression' if task=='regression' else
             'image' if modality=='image' else 'high_dimensional' if input_dim>=64 else 'tabular')
    width=24 if profile in ('regression','high_dimensional','language_modeling') else 16
    width=min(64,width+4*(index%3))
    primitive='sequence' if profile=='language_modeling' else 'residual' if profile=='regression' else 'gate' if profile=='image' else 'projection'
    if variant=='no-motif-bias':
        primitive='projection'
    nodes=(CellNodeGene(id='a',width=width,primitive=primitive),CellNodeGene(id='b',width=width,activation='tanh' if profile=='regression' else 'gelu',primitive='gate'))
    cell=CellGene(id='cell0',nodes=nodes,edges=(Edge(source='a',target='b'),),output='b')
    count=1 if variant=='flat' else min(depth_limit(budget),3 if profile in ('regression','language_modeling','high_dimensional') else 2)
    macros=tuple(MacroNodeGene(id=f'm{i}',cell_id='cell0') for i in range(count))
    genome=HierarchicalGenome(macro_nodes=macros,macro_edges=tuple(Edge(source=f'm{i}',target=f'm{i+1}') for i in range(count-1)),cells=(cell,),output=macros[-1].id,profile=profile,variant='shared' if variant=='unshared' else variant)
    if variant=='unshared':
        for node in genome.macro_nodes[1:]:
            genome=clone_cell(genome,node.id)
        genome=HierarchicalGenome.model_validate({**genome.model_dump(),'variant':'unshared'})
    return genome


def _construct(genome,**updates):
    data={**genome.model_dump(),**updates}
    used={node['cell_id'] if isinstance(node,dict) else node.cell_id for node in data['macro_nodes']}
    data['cells']=[cell for cell in data['cells'] if (cell['id'] if isinstance(cell,dict) else cell.id) in used]
    return HierarchicalGenome.model_validate(data)


def clone_cell(genome,node_id):
    node=next(n for n in genome.macro_nodes if n.id==node_id)
    counts=Counter(n.cell_id for n in genome.macro_nodes)
    if counts[node.cell_id]<2 or len(genome.cells)>=8:
        return genome
    cell=next(c for c in genome.cells if c.id==node.cell_id)
    identity=next(f'cell{i}' for i in range(16) if f'cell{i}' not in {c.id for c in genome.cells})
    extra={} if genome.schema_version == 1 else dict(parameter_id=_digest([cell.parameter_id,node_id,genome.genome_id])[:16],origin_parameter_id=cell.parameter_id)
    copied=CellGene.model_validate({**cell.model_dump(),'id':identity,'origin':cell.id,**extra})
    nodes=[MacroNodeGene(id=n.id,cell_id=identity if n.id==node_id else n.cell_id) for n in genome.macro_nodes]
    return _construct(genome,macro_nodes=nodes,cells=[*genome.cells,copied])


def specialize(genome,cell_id,rng):
    cell=next(c for c in genome.cells if c.id==cell_id)
    chosen=rng.randrange(len(cell.nodes))
    nodes=[CellNodeGene.model_validate({**n.model_dump(),'activation':rng.choice([a for a in ('relu','tanh','gelu','silu') if a!=n.activation])}) if i==chosen else n for i,n in enumerate(cell.nodes)]
    replacement=CellGene.model_validate({**cell.model_dump(),'nodes':nodes})
    return _construct(genome,cells=[replacement if c.id==cell_id else c for c in genome.cells])


def mutate(genome,rng,*,budget=64,motif_bank=()):
    operations=['activation','width','specialize','cell-grow','cell-prune','cell-rewire']
    if motif_bank:
        operations.append('motif')
    if genome.variant!='flat':
        operations+=['rewire','skip','expand']
    if genome.variant not in ('no-clone','unshared','flat'):
        operations.append('clone')
    if genome.variant=='no-motif-bias' and 'motif' in operations:
        operations.remove('motif')
    op=rng.choice(operations)
    cell=rng.choice(genome.cells)
    if op in ('activation','specialize'):
        return specialize(genome,cell.id,rng),op
    if op=='clone':
        child=clone_cell(genome,rng.choice(genome.macro_nodes).id)
        return (specialize(child,cell.id,rng),'specialize') if child==genome else (child,op)
    if op=='motif':
        donor=rng.choice(motif_bank)
        changed=CellGene.model_validate({**donor.model_dump(),'id':cell.id,'origin':donor.id})
        return _construct(genome,cells=[changed if c.id==cell.id else c for c in genome.cells]),op
    if op=='width':
        nodes=[CellNodeGene.model_validate({**n.model_dump(),'width':rng.choice([w for w in (8,16,24,32) if w!=n.width])}) for n in cell.nodes]
        changed=CellGene.model_validate({**cell.model_dump(),'nodes':nodes})
        return _construct(genome,cells=[changed if c.id==cell.id else c for c in genome.cells]),op
    if op.startswith('cell-'):
        payload=cell.model_dump()
        if op=='cell-grow' and len(cell.nodes)<6:
            identity=next(f'n{i}' for i in range(7) if f'n{i}' not in {n.id for n in cell.nodes})
            payload.update(nodes=[*cell.nodes,CellNodeGene(id=identity,width=cell.nodes[-1].width,primitive=rng.choice(['projection','gate','residual','sequence']))],
                edges=[*cell.edges,Edge(source=cell.output,target=identity)],output=identity)
        elif op=='cell-prune' and len(cell.nodes)>1:
            ordered,incoming,_=order(cell.nodes,cell.edges,cell.output)
            removed=ordered[0]
            payload.update(nodes=[n for n in cell.nodes if n.id!=removed],edges=[e for e in cell.edges if e.source!=removed and e.target!=removed])
        elif op=='cell-rewire':
            alternatives=_rewirings(cell.nodes,cell.edges,cell.output)
            if alternatives:
                payload['edges']=rng.choice(alternatives)
        changed=CellGene.model_validate(payload)
        if changed!=cell:
            return _construct(genome,cells=[changed if c.id==cell.id else c for c in genome.cells]),op
        return specialize(genome,cell.id,rng),'specialize'
    if op=='expand' and len(genome.macro_nodes)<depth_limit(budget):
        node=MacroNodeGene(id=f'm{len(genome.macro_nodes)}',cell_id=cell.id)
        child=_construct(genome,variant='shared' if genome.variant=='unshared' else genome.variant,
            macro_nodes=[*genome.macro_nodes,node],macro_edges=[*genome.macro_edges,Edge(source=genome.output,target=node.id)],output=node.id)
        if genome.variant=='unshared':
            child=clone_cell(child,node.id)
            child=_construct(child,variant='unshared')
        return child,op
    if op=='rewire':
        alternatives=_rewirings(genome.macro_nodes,genome.macro_edges,genome.output)
        if alternatives:
            return _construct(genome,macro_edges=rng.choice(alternatives)),op
    if op=='skip':
        ordered,_,_=order(genome.macro_nodes,genome.macro_edges,genome.output)
        choices=[(a,b) for i,a in enumerate(ordered) for b in ordered[i+1:] if (a,b) not in {(e.source,e.target) for e in genome.macro_edges}]
        if choices:
            source,target=rng.choice(choices)
            return _construct(genome,macro_edges=[*genome.macro_edges,Edge(source=source,target=target)]),op
    return specialize(genome,cell.id,rng),'specialize'


def _rewirings(nodes,edges,output):
    alternatives=[]
    ordered=order(nodes,edges,output)[0]
    for index in range(len(edges)):
        retained=[edge for i,edge in enumerate(edges) if i!=index]
        for i,source in enumerate(ordered):
            for target in ordered[i+1:]:
                replacement=Edge(source=source,target=target)
                if replacement==edges[index] or replacement in retained:
                    continue
                candidate=[*retained,replacement]
                try:
                    order(nodes,candidate,output)
                except ValueError:
                    continue
                alternatives.append(candidate)
    return alternatives


def crossover(a,b,rng,*,budget=64):
    if a.variant=='flat':
        recipient=a.cells[0]
        donor=rng.choice(b.cells)
        replacement=CellGene.model_validate({**donor.model_dump(),'id':recipient.id,'origin':donor.id})
        return _construct(a,cells=[replacement])
    limit=depth_limit(budget)
    left_order=order(a.macro_nodes,a.macro_edges,a.output)[0]
    right_order=order(b.macro_nodes,b.macro_edges,b.output)[0]
    left_count=rng.randint(1,min(len(left_order),limit-1))
    right_count=rng.randint(1,min(len(right_order),limit-left_count))
    segments=[('a',a,left_order[:left_count]),('b',b,right_order[-right_count:])]
    nodes=[]
    cells=[]
    edges=[]
    identities={}
    mappings={}
    for side,parent,segment in segments:
        mapping={old:f'm{len(nodes)+i}' for i,old in enumerate(segment)}
        mappings[side]=mapping
        for old in segment:
            source=next(node for node in parent.macro_nodes if node.id==old)
            key=(side,source.cell_id,old if a.variant=='unshared' else '')
            if key not in identities:
                cell=next(cell for cell in parent.cells if cell.id==source.cell_id)
                identity=f'cell{len(cells)}'
                extra={} if a.schema_version == 1 else dict(parameter_id=_digest([cell.parameter_id,side,identity,a.genome_id,b.genome_id])[:16],origin_parameter_id=cell.parameter_id)
                cells.append(CellGene.model_validate({**cell.model_dump(),'id':identity,'origin':cell.id,**extra}))
                identities[key]=identity
            nodes.append(MacroNodeGene(id=mapping[old],cell_id=identities[key]))
        edges.extend(Edge(source=mapping[e.source],target=mapping[e.target]) for e in parent.macro_edges if e.source in mapping and e.target in mapping)
    left_last=mappings['a'][left_order[left_count-1]]
    left_ids=set(mappings['a'].values())
    for name in sorted(left_ids-{left_last}):
        if not any(e.source==name for e in edges):
            edges.append(Edge(source=name,target=left_last))
    right_ids=set(mappings['b'].values())
    for name in sorted(right_ids):
        if not any(e.target==name for e in edges):
            edges.append(Edge(source=left_last,target=name))
    return _construct(a,macro_nodes=nodes,macro_edges=edges,cells=cells,output=mappings['b'][b.output])
