"""Budget-aware continuation preserves the study and blocks invalid evidence."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from evonn_compare import stratograph_budget_resume as c


def test_allowance_covers_each_fit_and_overhead_without_changing_study():
    cells = c.study.slots(c.study.StudySpec())
    prior = dict(slots=cells,completed={cell['id']:{} for cell in cells[:39]})
    before = deepcopy(prior)
    changed = c.amended_slots(prior)
    assert prior == before
    assert changed[:39] == cells[:39]
    for old,new in zip(cells[39:],changed[39:]):
        expected = deepcopy(old)
        expected['config']['timeout'] = 19800.
        assert new == expected
        assert new['config']['timeout'] > new['config']['budget'] * (new['config']['fit_timeout'] + 10.)
    with pytest.raises(ValueError,match='bounded engine allowance'):
        c.budget_timeout(dict(budget=256,fit_timeout=1800.))


def test_partial_epochs_cannot_be_inherited_or_completed(monkeypatch):
    monkeypatch.setattr(c,'read_export',lambda p:None)
    monkeypatch.setattr(c,'artifact_json',lambda *a:{'attempts':[{'status':'ok','epochs':11,'allocated_epochs':12}]})
    with pytest.raises(ValueError,match='full successful'):
        c.full_epochs(Path('/unused'),{'export':'symbiosis'})


def test_failure_blocks_retry(tmp_path,monkeypatch):
    parent,previous = tmp_path/'parent',tmp_path/'previous'
    parent.mkdir()
    previous.mkdir()
    m = {'parent_root':str(parent),'previous_root':str(previous)}
    monkeypatch.setattr(c,'preflight',lambda root:(m,{}, {'failures':[{'reason':'timeout'}]}))
    monkeypatch.setattr(c,'_bounded_process',lambda *a,**k:pytest.fail('must not dispatch'))
    with pytest.raises(ValueError,match='no automatic retries'):
        c.run(tmp_path)


def test_dispatch_failure_is_retained_with_budget_deadline(tmp_path,monkeypatch):
    parent,previous = tmp_path/'parent',tmp_path/'previous'
    parent.mkdir()
    previous.mkdir()
    cell = {'id':'hybrid','config':{'budget':128,'fit_timeout':120.,'timeout':19800.}}
    m = {'parent_root':str(parent),'previous_root':str(previous),'identity':{},'slots':[cell]}
    state = {'failures':[],'completed':{}}
    monkeypatch.setattr(c,'preflight',lambda root:(m,{'cache':'unused'},state))
    monkeypatch.setattr(c.study,'adopt',lambda *a:(None,None))
    def fail(command,timeout,log,**kwargs):
        assert timeout == 19860.
        assert '--resume' not in command
        raise ValueError('failed fit')
    monkeypatch.setattr(c,'_bounded_process',fail)
    with pytest.raises(ValueError,match='failed fit'):
        c.run(tmp_path)
    saved=json.loads((tmp_path/'status.json').read_text())
    assert saved['status']=='incomplete'
    assert saved['failures']==[{'slot':'hybrid','reason':'failed fit'}]


def test_missing_pairs_keep_all_thirty_contrasts_and_block_claims(tmp_path,monkeypatch):
    spec=c.study.StudySpec()
    manifest={'slots':c.study.slots(spec),'origins':{},'identity':{},'sha256':'test',
              'retained_failures':[{'charged_attempts':234}],'inherited':{},'interpretation':'amended'}
    parent={'spec':spec.model_dump(),'hypotheses':c.study.hypotheses(spec)}
    monkeypatch.setattr(c,'preflight',lambda root:(manifest,parent,{'completed':{},'failures':[]}))
    report=c.analyze(tmp_path)
    assert report['status']=='incomplete'
    assert len(report['missing'])==374
    assert len(report['contrasts'])==30
    assert all(r['holm_pvalue']==1 and not r['material_gain'] for r in report['contrasts'])
    assert report['prior_failed_run_cost']==[{'charged_attempts':234}]
