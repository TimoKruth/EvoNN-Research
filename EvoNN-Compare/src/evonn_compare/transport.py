"""Checksummed full dependency transport; never rewrite original evidence."""
import hashlib
import io
import json
import os
import uuid
import time
from pathlib import Path
import tarfile
import urllib.parse
import urllib.request
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from evonn_shared.artifact_io import create_artifact_directory, publish_artifact, read_verified_artifact
from evonn_shared.export_reader import read_document
from evonn_shared.telemetry import ArtifactReference
from .audit import artifact_json
from .registry import _events, _inventory, _load_source, digest, read_registry, validate_registry
from .workspace import derived, encoded, ownership

MAX_ARCHIVE=2*1024**3
MAX_FILES=20000
MAX_EXPANDED=4*1024**3


class TransportDescriptor(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    schema_version: Literal[1]=1
    archive_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    archive_size_bytes: int=Field(gt=0,le=MAX_ARCHIVE)
    index_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    transport_manifest_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    run_ids: list[str]=Field(min_length=1,max_length=MAX_FILES)


def file_digest(path):
    result=hashlib.sha256()
    size=0
    with Path(path).open('rb') as stream:
        while chunk:=stream.read(1024*1024):
            result.update(chunk)
            size+=len(chunk)
            if size>MAX_ARCHIVE:
                raise ValueError('archive exceeds 2 GiB transport limit')
    return result.hexdigest(),size


def _dependencies(records):
    roots={}
    for row in records:
        for binding in row['case_runs']+row['audit_sources']:
            original=binding['path']
            if original in roots:
                continue
            bundle=_load_source(binding)
            roots[original]=[{k:item[k] for k in ('path','sha256','size_bytes')} for item in _inventory(bundle)]
            if bundle.manifest.system.value=='contenders' and any(ref.path=='dataset_provenance.json' for ref in bundle.summary.artifact_digests):
                for item in artifact_json(bundle,'dataset_provenance.json'):
                    cache=item['cache_directory']
                    entries=item['cache_artifacts']
                    if cache in roots and roots[cache]!=entries:
                        raise ValueError('conflicting cache transport identity')
                    roots[cache]=entries
        for name in row['dashboard_report_paths']:
            path=Path(name)
            payload=read_document(path.parent,path.name,limit=128*1024*1024)
            original=str(path.parent)
            if original not in roots:
                roots[original]=[]
            entry=dict(path=path.name,sha256=hashlib.sha256(payload).hexdigest(),size_bytes=len(payload))
            if entry not in roots[original]:
                roots[original].append(entry)
    return roots


def pack_registry(registry, *, archive):
    root=Path(registry)
    with ownership(root):
        validation=validate_registry(root,require_artifacts=True)
        if validation['status']!='passed':
            raise ValueError('; '.join(validation['blockers']))
        dependencies=_dependencies(read_registry(root))
        files=[]
        roots={}
        for original,entries in sorted(dependencies.items()):
            relative='dependencies/'+hashlib.sha256(original.encode()).hexdigest()
            roots[original]=relative
            for entry in sorted(entries,key=lambda item:item['path']):
                files.append(dict(original_root=original,**entry,archive_path=relative+'/'+entry['path']))
        if len(files)>MAX_FILES or sum(item['size_bytes'] for item in files)>MAX_EXPANDED:
            raise ValueError('dependency archive size/count limit exceeded')
        manifest=dict(schema_version=1,index_sha256=hashlib.sha256(_events(root)[0]).hexdigest(),
            roots=roots,files=files,run_ids=sorted({r['run_id'] for r in read_registry(root)}))
        target=Path(archive)
        create_artifact_directory(target.parent)
        with target.open('xb') as stream:
            with tarfile.open(fileobj=stream,mode='w:gz') as tar:
                for item in files:
                    payload=read_verified_artifact(Path(item['original_root']),ArtifactReference(path=item['path'],sha256=item['sha256']),size_bytes=item['size_bytes'])
                    info=tarfile.TarInfo(item['archive_path'])
                    info.size=len(payload)
                    tar.addfile(info,io.BytesIO(payload))
                payload=encoded(manifest)
                info=tarfile.TarInfo('transport_manifest.json')
                info.size=len(payload)
                tar.addfile(info,io.BytesIO(payload))
            stream.flush()
            os.fsync(stream.fileno())
        sha,size=file_digest(target)
        descriptor=dict(schema_version=1,archive_sha256=sha,archive_size_bytes=size,index_sha256=manifest['index_sha256'],
            transport_manifest_sha256=digest(manifest),run_ids=manifest['run_ids'])
        publish_artifact(target.with_name(target.name+'.json'),encoded(descriptor))
        return descriptor


def hydrate_registry(registry, *, archive, descriptor):
    descriptor=json.loads(Path(descriptor).read_text()) if not isinstance(descriptor,dict) else descriptor
    descriptor=TransportDescriptor.model_validate(descriptor).model_dump()
    if file_digest(archive)!=(descriptor['archive_sha256'],descriptor['archive_size_bytes']):
        raise ValueError('archive checksum or size mismatch')
    with ownership(Path(registry)) as root:
        if hashlib.sha256(_events(root)[0]).hexdigest()!=descriptor['index_sha256']:
            raise ValueError('transport belongs to a different registry index')
        with tarfile.open(archive,'r:gz') as tar:
            members=[]
            expanded=0
            for member in tar:
                members.append(member)
                expanded+=member.size
                if len(members)>MAX_FILES+1 or expanded>MAX_EXPANDED:
                    raise ValueError('expanded archive limit exceeded')
            names=[member.name for member in members]
            if len(names)!=len(set(names)) or names.count('transport_manifest.json')!=1:
                raise ValueError('duplicate or missing archive manifest')
            for member in members:
                ArtifactReference(path=member.name,sha256='0'*64)
                if not member.isfile() or member.size<0:
                    raise ValueError('archive contains a link or special entry')
            member=tar.getmember('transport_manifest.json')
            if member.size>16*1024*1024:
                raise ValueError('transport manifest too large')
            manifest=json.loads(tar.extractfile(member).read())
            if digest(manifest)!=descriptor['transport_manifest_sha256'] or manifest['index_sha256']!=descriptor['index_sha256']:
                raise ValueError('transport manifest identity mismatch')
            expected=manifest['files']
            if set(names)!={item['archive_path'] for item in expected}|{'transport_manifest.json'}:
                raise ValueError('archive entries differ from transport manifest')
            if manifest['run_ids']!=descriptor['run_ids'] or manifest['run_ids']!=sorted({r['run_id'] for r in read_registry(root)}):
                raise ValueError('transport run set differs from registry')
            for original,relative in manifest['roots'].items():
                if not Path(original).is_absolute() or relative!='dependencies/'+hashlib.sha256(original.encode()).hexdigest():
                    raise ValueError('invalid exact-root transport mapping')
            for item in expected:
                if item['archive_path']!=manifest['roots'][item['original_root']]+'/'+item['path']:
                    raise ValueError('transport root and file path mismatch')
                member=tar.getmember(item['archive_path'])
                if member.size!=item['size_bytes'] or member.size>256*1024*1024:
                    raise ValueError('transport entry size mismatch')
                payload=tar.extractfile(member).read()
                if hashlib.sha256(payload).hexdigest()!=item['sha256']:
                    raise ValueError('transport entry checksum mismatch')
                destination=root/item['archive_path']
                create_artifact_directory(destination.parent)
                try:
                    publish_artifact(destination,payload)
                except FileExistsError:
                    read_verified_artifact(root,ArtifactReference(path=item['archive_path'],sha256=item['sha256']),size_bytes=item['size_bytes'])
            derived(root/'artifact_roots.json',encoded(dict(schema_version=1,index_sha256=manifest['index_sha256'],roots=manifest['roots'])))
        result=validate_registry(root,require_artifacts=True)
        if result['status']!='passed':
            raise ValueError('rehydrated evidence failed validation: '+'; '.join(result['blockers']))
        return result


def hydrate_declared(root):
    registry=root/'evidence'
    descriptor_path=registry/'source_bundle.json'
    if not descriptor_path.is_file():
        return {'status':'not_applicable','reason':'no external registry bundle declared'}
    document=json.loads(descriptor_path.read_text())
    if set(document)!={'url','descriptor'}:
        raise ValueError('invalid evidence bundle source declaration')
    document['descriptor']=TransportDescriptor.model_validate(document['descriptor']).model_dump()
    url=urllib.parse.urlsplit(document['url'])
    if (url.scheme!='https' or url.netloc!='github.com' or url.query or url.fragment
            or not url.path.startswith('/TimoKruth/EvoNN-Research/releases/download/')):
        raise ValueError('evidence bundle must be a versioned asset of this repository')
    destination=root/'.artifacts'/'evidence-transport'
    destination.mkdir(parents=True,exist_ok=True)
    archive=destination/(document['descriptor']['archive_sha256']+'.tar.gz')
    if not archive.exists():
        partial=archive.with_name('.download_'+uuid.uuid4().hex)
        started=time.monotonic()
        try:
            with urllib.request.urlopen(document['url'],timeout=60) as response,partial.open('xb') as output:
                count=0
                while chunk:=response.read(1024*1024):
                    count+=len(chunk)
                    if count>MAX_ARCHIVE or time.monotonic()-started>600:
                        raise ValueError('download exceeds evidence transport byte/time limit')
                    output.write(chunk)
            if file_digest(partial)!=(document['descriptor']['archive_sha256'],document['descriptor']['archive_size_bytes']):
                raise ValueError('download checksum or size mismatch')
            partial.rename(archive)
        finally:
            partial.unlink(missing_ok=True)
    return hydrate_registry(registry,archive=archive,descriptor=document['descriptor'])

