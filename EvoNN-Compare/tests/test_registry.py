"""Durable registry identity, artifact availability and crash rejection."""
import json

import pytest

from evonn_compare.registry import promote, read_registry, supersede, validate_registry


def test_promotion_is_idempotent_and_does_not_qualify_fixture(tmp_path, export_factory):
    source=export_factory(tmp_path/'source')
    registry=tmp_path/'evidence'
    first=promote(source.root,registry=registry,label='before',copy_artifacts=True)
    original=(registry/'index.jsonl').read_bytes()
    assert promote(source.root,registry=registry,label='before',copy_artifacts=True)==first
    assert (registry/'index.jsonl').read_bytes()==original
    row=read_registry(registry)[0]
    assert row['branch'] is None and row['preset'] is None
    assert row['decision_status']=='exploratory'
    assert row['lane_trust_state']!='trusted-core'
    assert validate_registry(registry,require_artifacts=True)['status']=='passed'
    (source.root/'report.md').unlink()
    assert validate_registry(registry,require_artifacts=True)['status']=='blocked'
    assert validate_registry(registry)['status']=='passed'


def test_registry_detects_corruption_missing_copies_and_incomplete_append(tmp_path,export_factory):
    source=export_factory(tmp_path/'source')
    registry=tmp_path/'evidence'
    promote(source.root,registry=registry,label='before',copy_artifacts=True)
    row=read_registry(registry)[0]
    copied=registry/row['copied_registry_paths'][0]
    copied.write_bytes(b'corrupt')
    assert validate_registry(registry)['status']=='blocked'
    with (registry/'index.jsonl').open('ab') as stream:
        stream.write(b'{"incomplete":')
    with pytest.raises(ValueError,match='incomplete'):
        read_registry(registry)


def test_supersession_is_append_only_and_rejects_cycles(tmp_path,export_factory):
    registry=tmp_path/'evidence'
    a=export_factory(tmp_path/'a',run_id='run_a')
    b=export_factory(tmp_path/'b',run_id='run_b')
    promote(a.root,registry=registry,label='before')
    prefix=(registry/'index.jsonl').read_bytes()
    promote(b.root,registry=registry,label='after')
    rows=read_registry(registry)
    supersede(registry,old=rows[0]['record_id'],new=rows[1]['record_id'],reason='replacement measurement')
    assert (registry/'index.jsonl').read_bytes().startswith(prefix)
    assert read_registry(registry)[0]['decision_status']=='superseded'
    with pytest.raises(ValueError):
        supersede(registry,old=rows[1]['record_id'],new=rows[0]['record_id'],reason='cycle')


def test_path_traversal_symlink_and_forged_row_rejected(tmp_path,export_factory):
    source=export_factory(tmp_path/'source')
    with pytest.raises(ValueError):
        promote(source.root,registry=tmp_path/'registry',label='../escape')
    target=tmp_path/'target'
    target.mkdir()
    link=tmp_path/'link'
    link.symlink_to(target,target_is_directory=True)
    with pytest.raises((ValueError,OSError)):
        promote(source.root,registry=link,label='safe')
    registry=tmp_path/'evidence'
    promote(source.root,registry=registry,label='safe')
    lines=(registry/'index.jsonl').read_text().splitlines()
    event=json.loads(lines[0])
    event['row']['lane_trust_state']='trusted-core'
    (registry/'index.jsonl').write_text(json.dumps(event)+'\n')
    with pytest.raises(ValueError,match='hash'):
        read_registry(registry)


def test_rehashed_forgery_cannot_replace_verified_statistics(tmp_path,export_factory):
    from evonn_compare.registry import digest
    source=export_factory(tmp_path/'source')
    registry=tmp_path/'evidence'
    promote(source.root,registry=registry,label='before')
    event=json.loads((registry/'index.jsonl').read_text())
    event['row']['observations'][0]['value']=999999.
    event['event_sha256']=digest({k:v for k,v in event.items() if k!='event_sha256'})
    (registry/'index.jsonl').write_text(json.dumps(event)+'\n')
    import hashlib
    manifest=json.loads((registry/'registry_manifest.json').read_text())
    manifest['index_sha256']=hashlib.sha256((registry/'index.jsonl').read_bytes()).hexdigest()
    (registry/'registry_manifest.json').write_text(json.dumps(manifest))
    result=validate_registry(registry,require_artifacts=True)
    assert result['status']=='blocked'
    assert 'observations' in result['blockers'][0]


def test_report_rebuilds_from_registry_and_preserves_escaping(tmp_path,export_factory):
    from evonn_compare.registry import registry_report
    source=export_factory(tmp_path/'source')
    registry=tmp_path/'evidence'
    promote(source.root,registry=registry,label='before',copy_artifacts=True)
    report=registry_report(registry,require_artifacts=True)
    assert report['registry']['validation']['status']=='passed'
    assert (registry/'fair_matrix_dashboard.html').is_file()
    assert report['descriptive_evidence']['score_distribution']
