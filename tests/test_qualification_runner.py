"""Recovery scheduling regressions; no engines or model fits are dispatched."""
import contextlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('qualification_runner', Path(__file__).resolve().parents[1] / 'EvoNN-Compare/tests/research_archive/qualification_runner.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class QualificationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        for name in ('logs', 'receipts', 'boundaries', 'campaigns/row'):
            (self.base/name).mkdir(parents=True)
        self.row = dict(id='row', stage='Q-core', pack='tier_b_core_v2', regime={'proposal_limit':256}, seed=1002, systems=['topograph'])
        (self.base/'qualification-matrix.json').write_text(json.dumps([self.row]))
        self.run = self.base/'existing-run'
        self.run.mkdir()
        (self.run/'config.yaml').write_text('{}')
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(runner, 'BASE', self.base))
        self.stack.enter_context(patch.object(runner, 'PRODUCER', self.base))
        for name in ('check_inputs', 'preflight', 'match_config', 'journal_completion'):
            self.stack.enter_context(patch.object(runner, name))
        self.stack.enter_context(patch.object(runner, 'read_manifest', return_value={'spec':{}}))
        self.stack.enter_context(patch.object(runner, 'CampaignSpec', SimpleNamespace(model_validate=lambda x:x)))
        self.stack.enter_context(patch.object(runner, 'lease', side_effect=lambda p:contextlib.nullcontext(7)))
        self.stack.enter_context(patch.object(runner.os, 'killpg'))
        self.clock = self.stack.enter_context(patch.object(runner.time, 'monotonic', return_value=0))

    def state(self, n):
        return dict(completed=n, elapsed=1100, attempts=[dict(status='ok', id=i) for i in range(n)])

    def chunk(self, start, target):
        output=self.base/'campaigns/row/runs'/runner.slot_id(runner.Case('tier_b_core_v2',256,1002),'topograph')
        output.mkdir(parents=True)
        (output/'one-run').mkdir()
        with patch.object(runner,'adopted',return_value=(self.run,None)), \
             patch.object(runner,'checkpoint',side_effect=[self.state(start),self.state(target)]), \
             patch.object(runner,'command_run') as command, \
             patch.object(runner,'run_campaign') as finalize:
            runner.worker(0,'topograph',9)
        self.assertEqual(command.call_count,1)
        args=command.call_args.args[0]
        self.assertEqual(args[args.index('--stop-after')+1],str(target))
        self.assertIn('--resume',args)
        self.assertEqual(command.call_args.args[2],1520)
        finalize.assert_not_called()
        self.assertEqual(json.loads((self.base/'status.json').read_text())['committed_fits'],target)
        self.assertEqual(len(list((self.base/'boundaries').glob('*.json'))),1)
        self.assertFalse(list((self.base/'receipts').glob('*.json')))

    def test_one_chunk_then_yield(self):
        self.chunk(224,240)

    def test_final_chunk_yields_before_export_validation(self):
        self.chunk(240,256)

    def test_insufficient_supervisor_allowance_does_not_dispatch(self):
        self.clock.side_effect=[0,200]
        with patch.object(runner,'adopted',return_value=(self.run,None)), \
             patch.object(runner,'checkpoint',return_value=self.state(224)), \
             patch.object(runner,'command_run') as command:
            runner.worker(0,'topograph',9)
        command.assert_not_called()
        self.assertEqual(json.loads((self.base/'status.json').read_text())['committed_fits'],224)

    def test_complete_run_only_replays_without_refitting(self):
        export=self.run/'symbiosis';export.mkdir()
        for name in ('manifest.json','summary.json','results.json'):
            (export/name).write_text('{}')
        accounting=SimpleNamespace(failed_evaluations=0,model_dump=lambda **kw:{'evaluation_count':256})
        bundle=SimpleNamespace(manifest=SimpleNamespace(accounting=accounting))
        def replay(command,path,seconds,fd):
            self.assertEqual(command[3],'replay')
            path.write_text(json.dumps({'status':'passed','checks':[1,2,3,4]}))
            return path
        with patch.object(runner,'adopted',return_value=(self.run,{'complete':True})), \
             patch.object(runner,'checkpoint',return_value=self.state(256)), \
             patch.object(runner,'run_campaign') as campaign, \
             patch.object(runner,'read_export',return_value=bundle), \
             patch.object(runner,'command_run',side_effect=replay) as command:
            runner.worker(0,'topograph',9)
        command.assert_called_once()
        campaign.assert_called_once_with(self.base/'campaigns/row',session_timeout=1)
        self.assertEqual(len(list((self.base/'receipts').glob('*.json'))),1)

    def test_recovery_preserves_previous_command_log(self):
        old=self.base/'logs/chunk.log';old.write_text('original timeout log')
        new=runner.command_run([sys.executable,'-c','print("resumed")'],old,5,1)
        self.assertNotEqual(new,old)
        self.assertEqual(old.read_text(),'original timeout log')
        self.assertEqual(new.read_text().strip(),'resumed')

    def test_completed_receipts_skip_all_dispatch(self):
        p=self.base/'receipts/row-topograph.json';p.write_text('{"preserved":true}')
        with patch.object(runner.subprocess,'Popen') as process:
            runner.tick()
        process.assert_not_called()
        self.assertEqual(p.read_text(),'{"preserved":true}')
        self.assertFalse(json.loads((self.base/'qualification-execution-complete.json').read_text())['next_stage_authorized'])

    def test_deferred_slot_prevents_false_completion_and_stays_visible(self):
        (self.base/'deferred-slots.json').write_text(json.dumps({'slots':{'row-topograph':'Unsupported loader'}}))
        with patch.object(runner.subprocess,'Popen') as process:
            runner.tick()
        process.assert_not_called()
        self.assertFalse((self.base/'qualification-execution-complete.json').exists())
        status=json.loads((self.base/'status.json').read_text())
        self.assertEqual(status['state'],'blocked_incomplete')
        self.assertEqual(status['blocked_slots'],{'row-topograph':'Unsupported loader'})
        self.assertEqual(status['total'],30)

    def test_deferred_slot_does_not_prevent_next_eligible_worker(self):
        self.row['systems']=['primordia','topograph']
        (self.base/'qualification-matrix.json').write_text(json.dumps([self.row]))
        (self.base/'deferred-slots.json').write_text(json.dumps({'slots':{'row-primordia':'Unsupported loader'}}))
        with patch.object(runner.subprocess,'Popen') as process:
            process.return_value.returncode=0
            runner.tick()
        process.assert_called_once()
        self.assertEqual(process.call_args.args[0][4],'topograph')
        self.assertFalse((self.base/'qualification-execution-complete.json').exists())


    def test_contender_dispatch_targets_only_selected_slot(self):
        manifest={'spec':{'timeout':1500,'fit_timeout':90,'enhanced':True},'cache':'/frozen/cache'}
        case=runner.Case('language_breadth_v1',64,1003)
        with patch.object(runner,'adopted',return_value=(None,None)), \
             patch.object(runner,'command_run') as command:
            runner.contender_slot(self.base/'campaigns/row',manifest,case,'row-contenders',1680)
        args=command.call_args.args[0]
        self.assertEqual(args[2:4],['evonn_contenders.cli','run'])
        self.assertIn('--enhanced',args)
        self.assertEqual(args[args.index('--timeout')+1],'1500')
        self.assertEqual(args[args.index('--seed')+1],'1003')

    def test_incomplete_contenders_is_never_restarted(self):
        with patch.object(runner,'adopted',return_value=(self.run,None)), \
             patch.object(runner,'command_run') as command:
            with self.assertRaisesRegex(RuntimeError,'no replacement authorized'):
                runner.contender_slot(self.base/'campaigns/row',{},runner.Case('language_breadth_v1',64,1003),'row-contenders',1680)
        command.assert_not_called()


if __name__ == '__main__':
    unittest.main()


def test_recovery_revalidates_export_artifacts(tmp_path, monkeypatch):
    base=tmp_path
    (base/'receipts').mkdir()
    (base/'receipts/one.json').write_text('{}')
    documents={name:'digest' for name in ['manifest.json','summary.json','results.json']}
    data={
        'runner-amendment-v5.json':{'runner_sha256':'digest','original_readiness_sha256':'digest',
                                 'deferred_slots_sha256':'digest','retained_evidence':{}},
        'qualification-matrix.json':[], 'deferred-slots.json':{'slots':{}},
        'readiness.json':{'identity':{},'files':{}},
        'one.json':{'documents':documents,'export':str(base/'export')},
    }
    monkeypatch.setattr(runner,'BASE',base)
    monkeypatch.setattr(runner,'read',lambda p:data[p.name])
    monkeypatch.setattr(runner,'digest',lambda p:'digest')
    monkeypatch.setattr(runner,'identity',lambda:{})
    calls=[]
    def corrupt_export(path):
        calls.append(path)
        raise ValueError('corrupt attempts artifact')
    monkeypatch.setattr(runner,'read_export',corrupt_export)
    import pytest
    with pytest.raises(ValueError,match='corrupt attempts'):
        runner.check_inputs()
    assert calls==[base/'export']
    documents.pop('results.json')
    with pytest.raises(ValueError,match='Incomplete completion'):
        runner.check_inputs()
