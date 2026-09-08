"""Executable shared-cell hierarchy features with a genuinely trained GELU head.

Cells are deterministic programs in the Phase-4 proxy regime. MLX trains the
head; this is explicitly not end-to-end learned hierarchy weight sharing.
"""
import hashlib
import numpy as np

from .genome import HierarchicalGenome, order
from .tensors import Backend


def _activation(value,name):
    if name=='relu':
        return np.maximum(value,0)
    if name=='tanh':
        return np.tanh(value)
    if name=='silu':
        return value*(np.tanh(value*.5)+1)*.5
    return .5*value*(1+np.tanh(.7978845608*(value+.044715*value**3)))


class CompiledCell:
    def __init__(self,gene):
        self.gene=gene
        self.ordered,self.incoming,_=order(gene.nodes,gene.edges,gene.output)
        self.nodes={node.id:node for node in gene.nodes}
        self.projections={}

    def project(self,value,width,node):
        key=(node,value.shape[-1],width)
        if key not in self.projections:
            seed=int(hashlib.sha256(f'{self.gene.program_id}:{key}'.encode()).hexdigest()[:8],16)
            rng=np.random.default_rng(seed)
            self.projections[key]=(rng.normal(size=(value.shape[-1],width))/np.sqrt(value.shape[-1])).astype(np.float32)
        return value@self.projections[key]

    def __call__(self,features):
        values={}
        for name in self.ordered:
            gene=self.nodes[name]
            parents=[values[parent] for parent in self.incoming[name]] or [features]
            projected=[self.project(value,gene.width,name) for value in parents]
            merged=sum(projected)/len(projected)
            value=_activation(np.clip(merged,-8,8),gene.activation)
            if gene.primitive=='gate':
                value=value*(np.tanh(merged*.5)+1)*.5
            elif gene.primitive=='residual':
                value=(value+merged)*.5
            elif gene.primitive=='sequence' and value.ndim==3:
                prefix=np.cumsum(value,axis=1)/np.arange(1,value.shape[1]+1,dtype=np.float32)[None,:,None]
                value=(value+prefix)*.5
            values[name]=value.astype(np.float32)
        return values[self.gene.output]


class CompiledHierarchy:
    evaluator_fidelity='hierarchy_features_trained_head'

    def __init__(self,genome,input_shape,output_dim,modality,task,*,backend='numpy_fallback',device='cpu',seed=0):
        self.genome=HierarchicalGenome.model_validate(genome)
        self.backend=Backend(backend,device)
        self.input_shape,self.output_dim,self.modality,self.task=tuple(input_shape),output_dim,modality,task
        self.token_input=task=='language_modeling'
        if output_dim<1 or not input_shape or any(int(size)<1 for size in input_shape):
            raise ValueError('positive explicit input/output dimensions required')
        self.cells={cell.id:CompiledCell(cell) for cell in genome.cells}
        self.executors={node.id:self.cells[node.cell_id] for node in genome.macro_nodes}
        self.ordered,self.incoming,_=order(genome.macro_nodes,genome.macro_edges,genome.output)
        final=self.executors[genome.output].gene
        width=next(node.width for node in final.nodes if node.id==final.output)
        rng=np.random.default_rng(seed)
        hidden=16
        self.weights={'head.w':(rng.normal(size=(width,hidden))/np.sqrt(width)).astype(np.float32),
            'head.b':np.zeros(hidden,dtype=np.float32),
            'readout.w':(rng.normal(size=(hidden,output_dim))/np.sqrt(hidden)).astype(np.float32),
            'readout.b':np.zeros(output_dim,dtype=np.float32)}
        self.buffers={}

    @property
    def parameter_count(self):
        return sum(value.size for value in self.weights.values())

    def features(self,inputs):
        x=np.asarray(inputs,dtype=np.float32)
        if self.token_input:
            if x.ndim!=2 or not np.isfinite(x).all() or not np.equal(x,np.floor(x)).all() or np.any(x<0) or np.any(x>=self.output_dim):
                raise ValueError('LM proxy requires causal integer token sequences within vocabulary')
            x=np.eye(self.output_dim,dtype=np.float32)[x.astype(np.int64)]
        else:
            x=x.reshape((len(x),-1))
        values={}
        for name in self.ordered:
            parents=[values[parent] for parent in self.incoming[name]] or [x]
            executor=self.executors[name]
            if len(parents)>1:
                width=executor.gene.nodes[0].width
                merged=sum(executor.project(parent,width,'macro_merge') for parent in parents)/len(parents)
            else:
                merged=parents[0]
            values[name]=executor(merged)
        return values[self.genome.output]

    def forward(self,parameters,inputs,*,training=False,seed=0):
        features=self.backend.array(self.features(self.backend.numpy(inputs)))
        hidden=self.backend.activate(features@parameters['head.w']+parameters['head.b'],'gelu')
        return hidden@parameters['readout.w']+parameters['readout.b']


def compile_genome(genome,input_shape,output_dim,modality,task,**options):
    return CompiledHierarchy(genome,input_shape,output_dim,modality,task,**options)
