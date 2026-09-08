"""Optional hosted qualification of real, immutable registry transport artifacts."""
import hashlib
import json
import os
from pathlib import Path
import tarfile
import urllib.request

import pytest

from evonn_compare.registry import registry_report
from evonn_compare.transport import hydrate_registry


@pytest.mark.skipif(os.environ.get('EVONN_REGISTRY_TRANSPORT')!='1',reason='versioned external artifact qualification is explicit')
def test_hosted_real_registry_transport(tmp_path):
    receipt=json.loads((Path(__file__).resolve().parents[2]/'governance/phase3-runtime-evidence.json').read_text())
    transport=receipt['transport']
    def download(url,target,expected_size,expected_sha):
        assert url.startswith('https://github.com/TimoKruth/EvoNN-Research/releases/download/evidence-phase3-20260908/')
        digest=hashlib.sha256()
        size=0
        with urllib.request.urlopen(url,timeout=60) as response,target.open('xb') as stream:
            while chunk:=response.read(1024*1024):
                size+=len(chunk)
                assert size<=expected_size
                digest.update(chunk)
                stream.write(chunk)
        assert (size,digest.hexdigest())==(expected_size,expected_sha)
    archive=tmp_path/'registry.tar.gz'
    download(transport['registry_url'],archive,transport['registry_size_bytes'],transport['registry_sha256'])
    registry=tmp_path/'registry'
    registry.mkdir()
    with tarfile.open(archive,'r:gz') as packed:
        seen=set()
        expanded=0
        for entry in packed:
            path=Path(entry.name)
            assert entry.isfile() and not path.is_absolute() and '..' not in path.parts and entry.name not in seen
            seen.add(entry.name)
            expanded+=entry.size
            assert len(seen)<=1000 and expanded<=128*1024**2
            target=registry/path
            target.parent.mkdir(parents=True,exist_ok=True)
            with packed.extractfile(entry) as source,target.open('xb') as output:
                output.write(source.read())
    dependency=tmp_path/'dependencies.tar.gz'
    descriptor=transport['descriptor']
    download(transport['dependency_url'],dependency,descriptor['archive_size_bytes'],descriptor['archive_sha256'])
    original=(registry/'index.jsonl').read_bytes()
    assert hydrate_registry(registry,archive=dependency,descriptor=descriptor)['status']=='passed'
    assert (registry/'index.jsonl').read_bytes()==original
    request=json.loads((registry/'analysis-request.json').read_text())
    report=registry_report(registry,request=request,require_artifacts=True)
    group=report['analysis']['groups'][0]
    assert {key:group[key] for key in receipt['analysis']}==receipt['analysis']
    assert report['analysis']['decision_category']==receipt['decision_category']
