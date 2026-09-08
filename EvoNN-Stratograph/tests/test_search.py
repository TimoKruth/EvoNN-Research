from evonn_shared.catalog import get_benchmark
from stratograph.search import Search


def test_hierarchy_search_resumes_identically_without_leader_exploitation_slot():
    definition=get_benchmark('iris_classification')
    search=Search([definition],seed=7,population_size=4)
    for index in range(4):
        genome=search.candidate(definition.id)
        search.observe(definition.id,genome,dict(status='ok',score=index/4,parameter_count=10))
    resumed=Search([definition],seed=99,population_size=4,state=search.state())
    assert resumed.candidate(definition.id)==search.candidate(definition.id)
    assert all(item['crossover'] for item in search.benchmarks[definition.id]['lineage'])
    for _ in range(8):
        a,b=search.candidate(definition.id),resumed.candidate(definition.id)
        assert a==b
        result=dict(status='ok',score=.5,parameter_count=20)
        search.observe(definition.id,a,result)
        resumed.observe(definition.id,b,result)
    assert search.state()==resumed.state()
    assert search.telemetry()['hierarchy'][definition.id]
