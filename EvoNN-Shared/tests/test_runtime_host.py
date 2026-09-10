"""Network renames must not change machine provenance or expose raw IDs."""
import plistlib
from types import SimpleNamespace

import pytest
from evonn_shared import runtime_host as h

FIRST = '00112233-4455-6677-8899-aabbccddeeff'
SECOND = '11223344-5566-7788-99aa-bbccddeeff00'


def test_rename_stable_but_machine_and_platform_changes_detected(monkeypatch):
    monkeypatch.setattr(h, '_machine_id', lambda system: FIRST)
    monkeypatch.setattr(h.platform, 'node', lambda: 'old.router')
    before = h.host_fields()
    monkeypatch.setattr(h.platform, 'node', lambda: 'new.router')
    assert h.host_fields() == before
    assert before['host'].startswith('machine-v1:') and FIRST not in str(before)
    monkeypatch.setattr(h, '_machine_id', lambda system: SECOND)
    assert h.host_fields()['host'] != before['host']
    monkeypatch.setattr(h, '_machine_id', lambda system: FIRST)
    monkeypatch.setattr(h.platform, 'machine', lambda: 'another-architecture')
    assert h.host_fields() != before


def test_macos_reads_platform_uuid_and_hashes_only_that_id(monkeypatch):
    monkeypatch.setattr(h.platform, 'system', lambda: 'Darwin')
    outputs = iter([FIRST.upper(), FIRST])
    monkeypatch.setattr(h.subprocess, 'run', lambda *a, **k: SimpleNamespace(
        stdout=plistlib.dumps([{'IOPlatformUUID': next(outputs), 'IOPlatformSerialNumber': 'do-not-export'}])))
    first = h.machine_token()
    assert h.machine_token() == first
    assert 'do-not-export' not in first


@pytest.mark.parametrize('invalid', ['', 'not-a-uuid', '0' * 32, 'f' * 32, None])
def test_missing_invalid_or_unprovisioned_id_fails_closed(monkeypatch, invalid):
    monkeypatch.setattr(h, '_machine_id', lambda system: invalid)
    with pytest.raises(ValueError, match='refusing hostname fallback'):
        h.machine_token()


def test_probe_failure_does_not_leak_raw_identifiers(monkeypatch):
    def fail(system):
        raise OSError('sensitive raw identifier')
    monkeypatch.setattr(h, '_machine_id', fail)
    with pytest.raises(ValueError) as error:
        h.machine_token()
    assert 'sensitive' not in str(error.value)


def test_linux_machine_id_is_used_without_network_lookup(monkeypatch):
    monkeypatch.setattr(h.Path, 'is_file', lambda path: str(path) == '/etc/machine-id')
    monkeypatch.setattr(h.Path, 'read_text', lambda path: FIRST.replace('-', '') + '\n')
    assert h._machine_id('Linux') == FIRST.replace('-', '')
