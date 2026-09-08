"""Append-only research receipts with explicit external-artifact dependencies.

Compact copies preserve review context. Revalidation of scientific claims still
requires the full original exports and dataset caches; historical green receipts
never stand in for missing bytes. Derived views may be rebuilt, events may not.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evonn_shared.artifact_io import append_artifact, create_artifact_directory, publish_artifact, read_verified_artifact
from evonn_shared.export_reader import read_document, read_export
from evonn_shared.runtime_io import source_identity, code_identity
from evonn_shared.telemetry import ArtifactReference
from evonn_shared.active_catalog import get_benchmark
from .audit import apply_admission, artifact_json, benchmark_audit
from .cases import Case, evaluate_case
from .evidence import best_rows, trend_rows
from .quality import classify
from .workspace import derived, encoded, load_cases, ownership

MAX_INDEX = 128*1024*1024
MAX_COPY = 1024*1024


class SourceBinding(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    path: str
    run_id: str
    documents: list[ArtifactReference]=Field(min_length=3,max_length=3)


class InventoryEntry(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    source_root: str
    path: str
    sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    size_bytes: int=Field(ge=0,le=256*1024*1024)
    registry_path: str | None
    role: Literal['export_document','export_dependency']

    @model_validator(mode='after')
    def safe_paths(self):
        ArtifactReference(path=self.path,sha256=self.sha256)
        if self.registry_path is not None:
            ArtifactReference(path=self.registry_path,sha256=self.sha256)
        if not Path(self.source_root).is_absolute():
            raise ValueError('artifact source root must be absolute')
        return self


class CaseDocument(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    case: dict
    systems: list[str]=Field(min_length=1)
    cohort: Literal['current','exploratory','reference']
    no_contenders: bool
    failures: list[dict]

    @model_validator(mode='after')
    def canonical_case(self):
        Case(**self.case)
        if len(self.systems)!=len(set(self.systems)):
            raise ValueError('duplicate expected systems')
        return self


class RegistryRow(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
    schema_version: Literal[1]=1
    record_id: str=Field(pattern=r'^[0-9a-f]{64}$')
    label: str=Field(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}$')
    run_id: str
    case_id: str
    timestamp: str
    git_commit: str=Field(pattern=r'^[0-9a-f]{40}$')
    branch: str | None
    pack: str
    preset: str | None
    budget: int=Field(gt=0)
    seed: int=Field(ge=0)
    backend_class: str
    runtime: dict
    systems_included: list[str]
    case_runs: list[dict]
    contender_floor_state: dict
    output_quality_level: Literal['L0','L1','L2','L3']
    lane_trust_state: Literal['contract-fair','trusted-core','trusted-extended','exploratory','reference']
    budget_accounting_state: str
    repeatability_state: str
    summary_checksum: str=Field(pattern=r'^[0-9a-f]{64}$')
    source_paths: list[str]
    copied_registry_paths: list[str]
    task_families: list[str]
    per_system_score_summaries: list[dict]
    dashboard_report_paths: list[str]
    decision_status: Literal['exploratory','candidate','promoted','rejected','superseded']
    artifacts: list[dict]
    observations: list[dict]
    comparison_policy: dict
    producer: dict
    verification: dict
    case_document: dict
    audit_sources: list[dict]


    @model_validator(mode='after')
    def nested_contract(self):
        from evonn_shared.telemetry import RuntimeMetadata
        RuntimeMetadata.model_validate_json(json.dumps(self.runtime))
        CaseDocument.model_validate(self.case_document)
        for binding in self.case_runs+self.audit_sources:
            parsed=SourceBinding.model_validate(binding)
            if {ref.path for ref in parsed.documents}!={'manifest.json','results.json','summary.json'}:
                raise ValueError('source binding must contain all three export documents')
        for item in self.artifacts:
            InventoryEntry.model_validate(item)
        if self.copied_registry_paths!=[item['registry_path'] for item in self.artifacts if item['registry_path'] is not None]:
            raise ValueError('copied artifact paths differ from inventory')
        for observation in self.observations:
            if not isinstance(observation,dict) or observation['run_id']!=self.run_id or observation['label']!=self.label:
                raise ValueError('observation identity differs from registry row')
            if type(observation['seed']) is not int or type(observation['budget']) is not int:
                raise ValueError('observation seed/budget must be integers')
        return self


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def _events(root):
    try:
        payload=read_document(root,'index.jsonl',limit=MAX_INDEX)
    except FileNotFoundError:
        return b'',[]
    if payload and not payload.endswith(b'\n'):
        raise ValueError('incomplete append-only registry record')
    previous=None
    events=[]
    for i,line in enumerate(payload.splitlines()):
        event=json.loads(line)
        if not isinstance(event,dict) or set(event)!={'schema_version','sequence','event_type','previous_event_sha256','event_sha256','row','supersession'}:
            raise ValueError('invalid registry event fields')
        unsigned={key:value for key,value in event.items() if key!='event_sha256'}
        if type(event['schema_version']) is not int or type(event['sequence']) is not int or event['schema_version']!=1 or event['sequence']!=i or event['previous_event_sha256']!=previous or digest(unsigned)!=event['event_sha256']:
            raise ValueError('registry event hash chain mismatch')
        if event['event_type']=='run':
            RegistryRow.model_validate(event['row'])
            if event['supersession'] is not None:
                raise ValueError('run event cannot supersede implicitly')
        elif event['event_type']=='supersede':
            if event['row'] is not None or not isinstance(event['supersession'],dict) or set(event['supersession'])!={'old','new','reason'} or any(not isinstance(value,str) for value in event['supersession'].values()):
                raise ValueError('invalid supersession event')
        else:
            raise ValueError('unknown registry event type')
        previous=event['event_sha256']
        events.append(event)
    return payload,events


def _rows(events):
    records={}
    superseded={}
    for event in events:
        if event['event_type']=='run':
            row=event['row']
            identity=digest({'label':row['label'],'run_id':row['run_id']})
            if row['record_id']!=identity or identity in records:
                raise ValueError('duplicate or invalid registry record identity')
            records[identity]=row
        else:
            change=event['supersession']
            old,new=change['old'],change['new']
            if old not in records or new not in records or old==new or old in superseded or new in superseded or not change['reason'].strip():
                raise ValueError('invalid, repeated or cyclic supersession')
            superseded[old]=new
    return [{**row,'decision_status':'superseded'} if identity in superseded else row for identity,row in records.items()]


def read_registry(root):
    return _rows(_events(Path(root))[1])


def _append(root, *, row=None, supersession=None):
    payload,events=_events(root)
    unsigned=dict(schema_version=1,sequence=len(events),event_type='run' if row is not None else 'supersede',
        previous_event_sha256=events[-1]['event_sha256'] if events else None,row=row,supersession=supersession)
    event={**unsigned,'event_sha256':digest(unsigned)}
    _rows(events+[event])
    addition=(json.dumps(event,sort_keys=True,allow_nan=False)+'\n').encode()
    if len(payload)+len(addition)>MAX_INDEX:
        raise ValueError('registry index capacity exceeded')
    if events:
        append_artifact(root/'index.jsonl',addition,expected_sha256=hashlib.sha256(payload).hexdigest())
    else:
        publish_artifact(root/'index.jsonl',addition)
    _manifest(root)


def _manifest(root):
    payload,events=_events(root)
    derived(root/'registry_manifest.json',encoded(dict(schema_version=1,index_sha256=hashlib.sha256(payload).hexdigest(),
        event_count=len(events),record_count=len(_rows(events)),last_event_sha256=events[-1]['event_sha256'] if events else None)))


def supersede(registry, *, old, new, reason):
    with ownership(Path(registry)) as root:
        _append(root,supersession=dict(old=old,new=new,reason=reason))


def _policy(bundle):
    config=artifact_json(bundle,bundle.manifest.config_snapshot.path)
    excluded={'git_commit','code_dirty','source_sha256','seed','pack','budget','run_id','output','cache','shared_root','initialization_stream','total'}
    policy={key:value for key,value in config.items() if key not in excluded}
    return dict(runtime=bundle.manifest.runtime.model_dump(mode='json'),budget=bundle.manifest.budget.model_dump(mode='json'),
        seeding=bundle.manifest.seeding.model_dump(mode='json'),training=policy)


def _data_bindings(bundle):
    if not any(ref.path=='dataset_provenance.json' for ref in bundle.summary.artifact_digests):
        return {}
    return {item['benchmark_id']:{key:value for key,value in item.items() if key not in ('cache_directory',)}
        for item in artifact_json(bundle,'dataset_provenance.json')}


def _observations(bundle,case_id,acceptance,label,level):
    config=artifact_json(bundle,bundle.manifest.config_snapshot.path)
    policy=_policy(bundle)
    bindings=_data_bindings(bundle)
    rows=trend_rows(bundle,case_id,acceptance)
    for observation in rows:
        observation['data_binding']=bindings[observation['benchmark']] if observation['benchmark'] in bindings else None
        observation['required_floor']=bundle.manifest.system.value=='contenders' and observation.get('model_family') in get_benchmark(observation['benchmark']).required_contenders
        observation.update(label=label,git_commit=bundle.manifest.git_commit,comparison_policy=policy,
            quality_level=level,source_clean=config.get('code_dirty') is False,run_class=bundle.manifest.run_class.value)
    return rows


def _inventory(bundle):
    result=[]
    for name in ('manifest.json','results.json','summary.json'):
        payload=read_document(bundle.root,name)
        result.append(dict(source_root=str(bundle.root.absolute()),path=name,sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),registry_path=None,role='export_document'))
    for reference in bundle.summary.artifact_digests:
        payload=read_verified_artifact(bundle.root,reference)
        result.append(dict(source_root=str(bundle.root.absolute()),path=reference.path,sha256=reference.sha256,
            size_bytes=len(payload),registry_path=None,role='export_dependency'))
    return result


def _source_binding(bundle):
    return dict(path=str(bundle.root.absolute()),run_id=bundle.manifest.run_id,
        documents=[dict(path=name,sha256=hashlib.sha256(read_document(bundle.root,name)).hexdigest())
            for name in ('manifest.json','results.json','summary.json')])


def _resolve_root(original, roots):
    if roots is None:
        return Path(original)
    if original not in roots:
        raise ValueError('transport missing exact source root: '+original)
    return roots[original]


def _relocation(root):
    try:
        data=json.loads(read_document(root,'artifact_roots.json'))
    except FileNotFoundError:
        return None
    if set(data)!={'schema_version','index_sha256','roots'} or data['schema_version']!=1 or data['index_sha256']!=hashlib.sha256(_events(root)[0]).hexdigest():
        raise ValueError('invalid or stale artifact-root map')
    result={}
    for original,relative in data['roots'].items():
        ArtifactReference(path=relative,sha256='0'*64)
        if not Path(original).is_absolute():
            raise ValueError('transport original root must be absolute')
        result[original]=root/relative
    return result


def _load_source(binding, roots=None):
    root=_resolve_root(binding['path'],roots)
    for ref in binding['documents']:
        read_verified_artifact(root,ArtifactReference(**ref))
    bundle=read_export(root)
    if bundle.manifest.run_id!=binding['run_id']:
        raise ValueError('bound source run identity mismatch')
    return bundle


def _inputs(source):
    if source.is_file():
        # A summary path denotes its verified export or canonical workspace case.
        if source.name not in ('summary.json','fair_matrix_summary.json','fair_matrix_trends.json'):
            raise ValueError('expected a canonical workspace or summary path')
        if source.name=='fair_matrix_trends.json':
            source=source.parent.parent
        elif source.name=='fair_matrix_summary.json':
            source=source.parent.parent.parent
        else:
            source=source.parent
    if (source/'manifest.json').is_file():
        bundle=read_export(source)
        manifest=bundle.manifest
        case=Case(manifest.pack_id,manifest.accounting.evaluation_count,manifest.seed)
        document=dict(case=case.as_dict(),systems=[manifest.system.value],cohort='current',no_contenders=manifest.system.value!='contenders',failures=[])
        return [(case.id,document,[bundle],evaluate_case(case,[bundle],no_contenders=document['no_contenders']))],source
    loaded=load_cases(source)
    if not loaded:
        raise ValueError('no canonical verified comparison cases found')
    return loaded,source


def promote(source, *, registry, label, copy_artifacts=False):
    if not isinstance(label,str) or re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}',label) is None:
        raise ValueError('invalid stable cohort label')
    with ownership(Path(registry)) as root:
        prior={row['record_id']:row for row in read_registry(root)}
        loaded,source=_inputs(Path(source).absolute())
        all_bundles=[bundle for _,_,bundles,_ in loaded for bundle in bundles]
        levels={b.manifest.run_id:classify(b.root,propagated=True)['level'] for b in all_bundles}
        audits={pack:benchmark_audit(pack,all_bundles,decision_grade=True,dashboard_present=(source/'fair_matrix_dashboard.html').is_file(),output_levels=levels)
            for pack in sorted({b.manifest.pack_id for b in all_bundles})}
        added=[]
        consumer_commit,consumer_dirty=code_identity()
        for case_id,document,bundles,acceptance in loaded:
            audit=audits[document['case']['pack']]
            acceptance=apply_admission(acceptance,audit)
            case_sources=[_source_binding(b) for b in bundles]
            audit_sources=[_source_binding(b) for b in all_bundles if b.manifest.pack_id==document['case']['pack']]
            for bundle in bundles:
                manifest=bundle.manifest
                identity=digest(dict(label=label,run_id=manifest.run_id))
                inventory=_inventory(bundle)
                checksum=next(item['sha256'] for item in inventory if item['path']=='summary.json')
                if identity in prior:
                    old=prior[identity]
                    if old['summary_checksum']!=checksum or old['case_id']!=case_id or old['case_runs']!=case_sources:
                        raise ValueError('conflicting evidence for existing label/run identity')
                    added.append(identity)
                    continue
                config=artifact_json(bundle,manifest.config_snapshot.path)
                policy=_policy(bundle)
                rows=_observations(bundle,case_id,acceptance,label,levels[manifest.run_id])
                copies=[]
                if copy_artifacts:
                    directory=create_artifact_directory(root/'runs'/identity)
                    for item in inventory:
                        # JSON/config/report copies only; weights and datasets stay external.
                        if item['size_bytes']>MAX_COPY or Path(item['path']).suffix not in ('.json','.yaml','.md'):
                            continue
                        payload=read_verified_artifact(bundle.root,ArtifactReference(path=item['path'],sha256=item['sha256']),size_bytes=item['size_bytes'])
                        relative=f'runs/{identity}/{item["path"]}'
                        destination=root/relative
                        create_artifact_directory(destination.parent)
                        try:
                            publish_artifact(destination,payload)
                        except FileExistsError:
                            read_verified_artifact(root,ArtifactReference(path=relative,sha256=item['sha256']),size_bytes=item['size_bytes'])
                        item['registry_path']=relative
                        copies.append(relative)
                    del directory
                paths=[str(source/name) for name in ('fair_matrix_dashboard.html','trends/fair_matrix_trends.json','trends/fair_matrix_trends.md') if (source/name).is_file()]
                row=dict(schema_version=1,record_id=identity,label=label,run_id=manifest.run_id,case_id=case_id,
                    timestamp=manifest.timing.started_at.isoformat(),git_commit=manifest.git_commit,branch=None,pack=manifest.pack_id,preset=None,
                    budget=manifest.accounting.evaluation_count,seed=manifest.seed,backend_class=manifest.runtime.backend.value,
                    runtime=manifest.runtime.model_dump(mode='json'),systems_included=sorted(document['systems']),case_runs=case_sources,
                    contender_floor_state=audit,output_quality_level=levels[manifest.run_id],lane_trust_state=acceptance['operating_state'],
                    budget_accounting_state=acceptance['accounting_state'],repeatability_state=acceptance['repeatability_state'],
                    summary_checksum=checksum,source_paths=[str(bundle.root.absolute())],copied_registry_paths=copies,
                    task_families=sorted({r['family'] for r in rows}),per_system_score_summaries=best_rows(rows),dashboard_report_paths=paths,
                    decision_status='candidate' if acceptance['operating_state']=='trusted-core' and config.get('code_dirty') is False else 'exploratory',
                    artifacts=inventory,observations=rows,comparison_policy=policy,
                    producer=dict(git_commit=manifest.git_commit,source_sha256=config.get('source_sha256'),code_dirty=config.get('code_dirty'),branch_provenance='not_recorded',preset_provenance='not_recorded'),
                    verification=dict(timestamp=datetime.now(timezone.utc).isoformat(),consumer_commit=consumer_commit,consumer_dirty=consumer_dirty,
                        consumer_source_sha256=source_identity(),policy='registry-v1',kind='promotion_time_receipt',external_dependencies_required=True),
                    case_document={key:document[key] for key in ('case','systems','cohort','no_contenders','failures')},audit_sources=audit_sources)
                RegistryRow.model_validate(row)
                _append(root,row=row)
                prior[identity]=row
                added.append(identity)
        return added


def validate_registry(registry, *, require_artifacts=False):
    root=Path(registry)
    blockers=[]
    case_checks={}
    audit_checks={}
    try:
        payload,events=_events(root)
        rows=_rows(events)
        roots=_relocation(root) if require_artifacts else None
        manifest=json.loads(read_document(root,'registry_manifest.json'))
        if manifest['index_sha256']!=hashlib.sha256(payload).hexdigest() or manifest['event_count']!=len(events):
            blockers.append('stale registry manifest; rebuild report from intact index')
        for row in rows:
            for item in row['artifacts']:
                ref=ArtifactReference(path=item['path'],sha256=item['sha256'])
                if item['registry_path'] is not None:
                    read_verified_artifact(root,ArtifactReference(path=item['registry_path'],sha256=item['sha256']),size_bytes=item['size_bytes'])
                if require_artifacts:
                    read_verified_artifact(_resolve_root(item['source_root'],roots),ref,size_bytes=item['size_bytes'])
            if require_artifacts:
                case_key=digest([row['case_runs'],row['case_document']])
                if case_key not in case_checks:
                    bundles=[_load_source(binding,roots) for binding in row['case_runs']]
                    doc=row['case_document']
                    if sorted(b.manifest.system.value for b in bundles)!=sorted(doc['systems']):
                        raise ValueError('case expected systems missing from verified sources')
                    acceptance=evaluate_case(Case(**doc['case']),bundles,failures=doc['failures'],cohort=doc['cohort'],no_contenders=doc['no_contenders'])
                    case_checks[case_key]=(bundles,doc,acceptance)
                bundles,doc,acceptance=case_checks[case_key]
                audit_key=digest([row['pack'],row['audit_sources'],row['dashboard_report_paths']])
                if audit_key not in audit_checks:
                    sources=[_load_source(binding,roots) for binding in row['audit_sources']]
                    levels={b.manifest.run_id:classify(b.root,propagated=True)['level'] for b in sources}
                    audit=benchmark_audit(row['pack'],sources,decision_grade=True,
                        dashboard_present=any((_resolve_root(str(Path(path).parent),roots)/Path(path).name).is_file() and Path(path).name=='fair_matrix_dashboard.html' for path in row['dashboard_report_paths']),output_levels=levels,cache_roots=roots)
                    audit_checks[audit_key]=(levels,audit)
                levels,audit=audit_checks[audit_key]
                current=apply_admission(acceptance,audit)
                if current['operating_state']!=row['lane_trust_state'] or current['accounting_state']!=row['budget_accounting_state']:
                    raise ValueError('current source validation differs from recorded lane receipt')
                if levels[row['run_id']]!=row['output_quality_level']:
                    raise ValueError('current source output quality differs from receipt')
                own=[b for b in bundles if b.manifest.run_id==row['run_id']]
                if len(own)!=1:
                    raise ValueError('registry run not uniquely bound to source case')
                bundle=own[0]
                manifest=bundle.manifest
                original=next(binding['path'] for binding in row['case_runs'] if binding['run_id']==row['run_id'])
                expected=_observations(bundle,row['case_id'],current,row['label'],levels[row['run_id']])
                config=artifact_json(bundle,manifest.config_snapshot.path)
                producer=dict(git_commit=manifest.git_commit,source_sha256=config.get('source_sha256'),code_dirty=config.get('code_dirty'),branch_provenance='not_recorded',preset_provenance='not_recorded')
                semantic=dict(observations=expected,per_system_score_summaries=best_rows(expected),comparison_policy=_policy(bundle),
                    producer=producer,git_commit=manifest.git_commit,timestamp=manifest.timing.started_at.isoformat(),
                    pack=manifest.pack_id,budget=manifest.accounting.evaluation_count,seed=manifest.seed,
                    backend_class=manifest.runtime.backend.value,runtime=manifest.runtime.model_dump(mode='json'),
                    branch=None,preset=None,systems_included=sorted(doc['systems']),
                    source_paths=[original],task_families=sorted({r['family'] for r in expected}),
                    contender_floor_state=audit,repeatability_state=current['repeatability_state'])
                for key,value in semantic.items():
                    if row[key]!=value:
                        raise ValueError(f'registry {key} differs from verified source evidence')
                canonical=[{**item,'source_root':original} for item in _inventory(bundle)]
                inventory=[{**item,'registry_path':None} for item in row['artifacts']]
                if inventory!=canonical:
                    raise ValueError('registry artifact inventory differs from verified export')
                if row['summary_checksum']!=next(item['sha256'] for item in canonical if item['path']=='summary.json'):
                    raise ValueError('registry summary checksum differs from verified export')
                expected_status='candidate' if current['operating_state']=='trusted-core' and config.get('code_dirty') is False else 'exploratory'
                if row['decision_status'] not in (expected_status,'superseded'):
                    raise ValueError('registry promotion status lacks a derived decision event')

        return dict(status='blocked' if blockers else 'passed',blockers=blockers,records=len(rows),require_artifacts=require_artifacts)
    except (ValueError,OSError,KeyError,TypeError) as error:
        return dict(status='blocked',blockers=[str(error)],records=None,require_artifacts=require_artifacts)


def registry_report(registry, *, request=None, require_artifacts=False):
    from .dashboard import render_dashboard
    from .evidence import aggregates, winners
    from .statistics import AnalysisRequest, compare_cohorts, descriptive_evidence
    with ownership(Path(registry)) as root:
        _manifest(root)  # Rebuildable receipt only, never repair a damaged index.
        validation=validate_registry(root,require_artifacts=require_artifacts)
        if validation['status']!='passed':
            raise ValueError('; '.join(validation['blockers']))
        records=[r for r in read_registry(root) if r['decision_status'] not in ('superseded','rejected')]
        rows=[r for record in records for r in record['observations']]
        # Alias labels are descriptive provenance; inference checks original run IDs.
        selected=[]
        for row in rows:
            selected.append({**row,'case_id':row['label']+'::'+row['case_id'],'cohort':row['label']})
        cases={}
        for record in records:
            case_id=record['label']+'::'+record['case_id']
            if case_id not in cases:
                cases[case_id]=dict(comparison_id=case_id,case=record['case_document']['case'],
                    acceptance=dict(operating_state=record['lane_trust_state'],accounting_state=record['budget_accounting_state'],
                        repeatability_state=record['repeatability_state'],engine_only='contenders' not in record['systems_included'],blockers=[]),
                    runs=[dict(run_id=x['run_id']) for x in record['case_runs']],failures=record['case_document']['failures'])
        analysis=None
        if request is not None:
            parsed=AnalysisRequest.model_validate(request)
            analysis=compare_cohorts(rows,before=parsed.before,after=parsed.after,request=parsed)
            if not require_artifacts:
                # Offline receipts can explain history, but cannot make new claim-ready verdicts.
                for group in analysis['groups']:
                    group['level']='L3'
                    group['aggregation_label']='blocked'
                    group['blockers'].append('current external-artifact revalidation required')
                analysis['decision_category']='inconclusive'
        description=descriptive_evidence(selected)
        systems={r['engine'] for r in rows}
        data=dict(schema_version='1.0.0',cases=list(cases.values()),rows=selected,statistics=aggregates(selected),
            output_quality=[dict(path=r['source_paths'][0],run_id=r['run_id'],case_id=r['label']+'::'+r['case_id'],level=r['output_quality_level'],gaps=[],next_level='see registry analysis') for r in records],
            all_systems_winners=winners(selected),projects_only_winners=winners(selected,projects_only=True),
            discovered_systems=sorted(systems),absent_systems=sorted({'contenders','prism','topograph','stratograph','primordia'}-systems),
            registry=dict(index_sha256=hashlib.sha256(_events(root)[0]).hexdigest(),validation=validation,record_ids=[r['record_id'] for r in records]),
            analysis=analysis,descriptive_evidence=description)
        report=dict(schema_version=1,registry=data['registry'],analysis=analysis,descriptive_evidence=description)
        derived(root/'evidence_report.json',encoded(report))
        markdown='# Registry evidence\n\nArtifact validation: '+('current sources verified' if require_artifacts else 'compact receipts only')+'\n\n'
        if analysis is not None:
            markdown+='Decision: '+analysis['decision_category']+'\n\n| Pack | Engine | Budget | Seeds | Statistical label | Aggregate | Level |\n|---|---|---|---|---|---|---|\n'
            for group in analysis['groups']:
                markdown+=f"| {group['pack']} | {group['engine']} | {group['budget']} | {group['n']} | {group['statistical_label']} | {group['aggregation_label']} | {group['level']} |\n"
                markdown+=''.join('\nBlocker: '+reason+'\n' for reason in group['blockers'])
        markdown+='\nBest-observed ranks are descriptive. Missing raw artifacts block new claims.\n'
        derived(root/'evidence_report.md',markdown.encode())
        derived(root/'fair_matrix_dashboard.json',encoded(data))
        derived(root/'fair_matrix_dashboard.html',render_dashboard(data).encode())
        return report
