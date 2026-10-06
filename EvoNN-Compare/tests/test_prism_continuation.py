"""Safety caps must not relax fit budgets or the original campaign scope."""
import importlib.util
import json
from pathlib import Path

import pytest
from evonn_compare import campaign as c
from evonn_shared.prism_policy import PrismResearchPolicy
from prism.config import RunConfig


spec = importlib.util.spec_from_file_location('prism_continuation',
    Path(__file__).parents[1]/'src/evonn_compare/prism_continuation.py')
continuation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(continuation)


def test_budget_allowance_and_scoped_admission():
    for budget, expected in ((128,19800.),(256,39000.)):
        assert continuation.timeout({'budgets':[budget],'fit_timeout':120.}) == expected
        assert RunConfig(timeout=expected).fit_timeout == 120
        allowed = c.CampaignSpec(systems=['prism'], budgets=[budget], timeout=expected,
            prism_research=PrismResearchPolicy(), prism_version_study='user-requested-20260921')
        assert allowed.timeout == expected
    for value in (1741.,19800.,39000.):
        with pytest.raises(ValueError):
            c.CampaignSpec(timeout=value)
    for values in ({'timeout':43201.},{'timeout':float('inf')},{'fit_timeout':1801.}):
        with pytest.raises(ValueError):
            RunConfig(**values)


def test_dispatch_exact_slot_and_keep_resume_fail_closed(tmp_path, monkeypatch):
    row=next(r for r in continuation.study.campaigns() if r['stage']=='main' and r['arm']=='frontier_v2' and r['panel']=='breadth128')
    entry={k:row[k] for k in ('campaign','stage','arm','panel')}
    entry['seed']=21601
    manifest={'spec':{**row['spec'],'timeout':19800.},'sha256':'a'*64,'cache':str(tmp_path/'cache')}
    history=[]
    results=[(None,None)]
    calls=[]
    monkeypatch.setattr(c,'preflight',lambda *a: None)
    monkeypatch.setattr(c,'read_manifest',lambda *a: manifest)
    monkeypatch.setattr(c,'events',lambda *a: history)
    monkeypatch.setattr(c,'active_dispatch',lambda *a: None)
    monkeypatch.setattr(c,'adopted',lambda *a: results[-1])
    monkeypatch.setattr(continuation.study,'replay',lambda *a: None)
    monkeypatch.setattr(continuation,'observation',lambda *a: {'verified':True})
    def bounded(command,seconds,log,**kwargs):
        event=json.loads(Path(command[-2]).read_bytes())
        cmd=event['details']['command']
        assert cmd[cmd.index('--seed')+1]=='21601'
        assert cmd[cmd.index('--budget')+1]=='128'
        assert cmd[cmd.index('--timeout')+1]=='19800.0'
        assert cmd[cmd.index('--fit-timeout')+1]=='120.0'
        assert seconds==19820.
        assert len(kwargs['pass_fds'])==3
        calls.append(cmd)
        results.append((tmp_path/'run',{'run_id':'verified'}))
    monkeypatch.setattr(c,'_bounded_process',bounded)
    assert continuation.dispatch(tmp_path,row,entry,(101,102))=={'verified':True}
    assert len(calls)==1 and [e['kind'] for e in history]==['dispatch','complete']
    continuation.dispatch(tmp_path,row,entry,(101,102))
    assert len(calls)==1
    history.clear()
    results.append((tmp_path/'partial',None))
    with pytest.raises(ValueError,match='no automatic retry'):
        continuation.dispatch(tmp_path,row,entry,(101,102))


def test_incomplete_report_never_computes_inference(tmp_path,monkeypatch):
    row=next(r for r in continuation.study.campaigns() if r['stage']=='main')
    entry={k:row[k] for k in ('campaign','stage','arm','panel')}
    entry['seed']=21601
    plan={'schedule':[entry],'inherited':{},'sha256':'a'*64,'retained_failures':[{'charged_attempts':98}], 'interpretation':'amended'}
    monkeypatch.setattr(continuation,'preflight',lambda root:(plan,{'campaigns':[row]}))
    monkeypatch.setattr(c,'read_manifest',lambda *a: {})
    monkeypatch.setattr(c,'events',lambda *a: [])
    monkeypatch.setattr(continuation.study,'inference',lambda *a: pytest.fail('early inference'))
    result=continuation.analyze(tmp_path)
    assert result['status']=='incomplete' and result['statistics'] is None
    assert result['retained_failure_cost'][0]['charged_attempts']==98


def test_fit_timeout_amendment_rejects_other_failure_modes():
    state = {'completed':128,'attempts':[{'status':'ok','charged':1} for _ in range(127)] +
        [{'status':'failed','charged':1,'reason':'training wall-clock cap reached'}]}
    assert continuation.fit_failure(state,128)['status'] == 'failed'
    state['attempts'][-1]['reason'] = 'non-finite gradient'
    with pytest.raises(ValueError,match='diagnosed single per-fit timeout'):
        continuation.fit_failure(state,128)
    state['attempts'][-1]['reason'] = 'training wall-clock cap reached'
    state['completed'] = 127
    with pytest.raises(ValueError):
        continuation.fit_failure(state,128)


def test_amended_caps_preserve_protocol_and_admit_full_allowance():
    for row in continuation.study.campaigns():
        if row['stage'] != 'main':
            continue
        original = row['spec']
        amended = {**original,'timeout':43200.,'fit_timeout':1800.}
        parsed = c.CampaignSpec.model_validate(amended)
        assert parsed.timeout == 43200 and parsed.fit_timeout == 1800
        assert {k:v for k,v in amended.items() if k not in ('timeout','fit_timeout')} == {
            k:v for k,v in original.items() if k not in ('timeout','fit_timeout')}


def test_size_failure_requires_exact_uncharged_rejection():
    attempts=[{'status':'ok','charged':1} for _ in range(255)]
    attempts.append(dict(status='failed',charged=0,invalid=1,compiled_parameter_count=3367792,
        reason='invalid pre-fit candidate: compiled candidate exceeds local runtime parameter safety cap'))
    state={'completed':256,'attempts':attempts}
    assert continuation.size_failure(state,256)['charged']==0
    for field,value in [('charged',1),('invalid',0),('reason','training wall-clock cap reached'),('compiled_parameter_count',1)]:
        saved=attempts[-1][field]
        attempts[-1][field]=value
        with pytest.raises(ValueError,match='uncharged oversized proposal'):
            continuation.size_failure(state,256)
        attempts[-1][field]=saved
