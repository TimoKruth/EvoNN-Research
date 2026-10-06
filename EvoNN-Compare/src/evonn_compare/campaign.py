"""Pinned, resumable comparison campaigns; planning never fits a model."""
from contextlib import ExitStack, contextmanager
import fcntl
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from typing import Literal

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from evonn_shared._run_io import open_directory, open_regular_at
from evonn_shared.active_catalog import get_benchmark, load_parity_pack
from evonn_shared.artifact_io import create_artifact_directory, publish_artifact, read_verified_artifact
from evonn_shared.datasets import array_digest, shared_root
from evonn_shared.export_reader import read_document, read_export
from evonn_shared.runtime_io import code_identity, source_identity, encode
from evonn_shared.runtime_host import host_fields
from evonn_shared.runtime_budget import execution_budget
from evonn_shared.runtime_journal import load_runtime_checkpoint
from evonn_shared.hierarchy_policy import HierarchyResearchPolicy
from evonn_shared.hierarchy_presets import standard_hierarchy_policy
from evonn_shared.prism_policy import PrismResearchPolicy
from evonn_shared.primordia_policy import PrimordiaResearchPolicy, RESEARCH_DEFAULTS
from evonn_shared.topograph_policy import TopographResearchPolicy
from evonn_shared.telemetry import ArtifactReference
from .audit import artifact_json, benchmark_audit
from .cases import Case, evaluate_case
from .workspace import SYSTEMS, encoded, workspace_report

ROOT = Path(__file__).resolve().parents[3]
MODULES = {"prism": "prism.cli", "topograph": "topograph.cli", "stratograph": "stratograph.cli",
           "primordia": "evonn_primordia.cli", "contenders": "evonn_contenders.cli"}


class CampaignSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    pack: str = "tier_b_core_v2"
    budgets: list[int] = Field(default_factory=lambda: [16], min_length=1, max_length=16)
    seeds: list[int] = Field(default_factory=lambda: [42, 43, 44], min_length=1, max_length=64)
    systems: list[str] = Field(default_factory=lambda: list(SYSTEMS), min_length=1)
    backend: str = "mlx_native"
    epochs: int = Field(default=12, ge=1, le=100)
    stratograph_research: HierarchyResearchPolicy | None = None
    prism_research: PrismResearchPolicy | None = None
    primordia_research: PrimordiaResearchPolicy | None = None
    comparison_scope: Literal["all_engines", "primordia_variants_v1", "topograph_variants_v1"] = "all_engines"
    topograph_variant: Literal["legacy", "mechanics", "training", "archive", "broad", "open", "next"] | None = None
    topograph_research: TopographResearchPolicy | None = None
    contender_pool: Literal["lm_screen_v1_reference", "lm_screen_v1_epochs2", "lm_screen_v1_epochs5",
                            "lm_screen_v1_epochs10", "lm_screen_v1_alpha01", "lm_screen_v1_alpha001"] | None = None
    enhanced: bool = False
    timeout: float = Field(default=300.0, gt=0, le=43200)
    fit_timeout: float = Field(default=90.0, gt=0, le=1800)
    min_free_bytes: int = Field(default=1024**3, ge=0)
    analysis: str = "descriptive_repeated_seed_no_superiority_claim"

    @model_validator(mode="after")
    def valid(self):
        topograph_only = self.comparison_scope == "topograph_variants_v1"
        if topograph_only and (self.systems != ["topograph"] or self.topograph_variant is None
                or self.prism_research is not None or self.primordia_research is not None
                or self.stratograph_research is not None or self.contender_pool is not None or self.enhanced):
            raise ValueError("Topograph variant scope requires only Topograph and an explicit variant")
        primordia_only = self.comparison_scope == "primordia_variants_v1"
        if self.timeout > 1740 and not topograph_only and (not primordia_only or self.timeout <= 1800 or self.timeout > 36000):
            raise ValueError("extended total time requires an explicitly scoped Topograph or segmented Primordia campaign")
        if primordia_only and (self.systems != ["primordia"] or self.primordia_research is None
                or self.prism_research is not None or self.topograph_variant is not None
                or self.topograph_research is not None or self.stratograph_research is not None
                or self.contender_pool is not None or self.enhanced):
            raise ValueError("Primordia variant scope requires only Primordia and an explicit policy")
        if self.topograph_research is not None and self.topograph_variant != "next":
            raise ValueError("Topograph research options require variant next")
        if self.contender_pool is not None:
            if set(self.systems) != set(SYSTEMS) or not self.enhanced:
                raise ValueError("baseline screening requires every engine and enhanced Contenders")
            if self.pack != "language_breadth_v1" or any(b < 16 or b % 16 for b in self.budgets):
                raise ValueError("language baseline screening requires breadth and all four families per task")
        if self.primordia_research is not None and not primordia_only and set(self.systems) != set(SYSTEMS):
            raise ValueError("Primordia research campaigns require every engine and Contenders")
        if self.topograph_variant is not None and not topograph_only and set(self.systems) != set(SYSTEMS):
            raise ValueError("Topograph research campaigns require every engine and Contenders")
        if self.prism_research is not None and set(self.systems) != set(SYSTEMS):
            raise ValueError("Prism research campaigns require every engine and Contenders")
        if self.stratograph_research is not None:
            if set(self.systems) != set(SYSTEMS):
                raise ValueError("hierarchy research campaigns require every engine and Contenders")
            if self.stratograph_research.screen_epochs > self.epochs:
                raise ValueError("hierarchy screening exceeds full epoch allocation")
        if self.backend not in {"mlx_native", "numpy_fallback"}:
            raise ValueError("explicit native or portability backend required")
        if self.analysis != "descriptive_repeated_seed_no_superiority_claim":
            raise ValueError("campaign runner does not pre-authorize scientific superiority")
        if (any(len(values) != len(set(values)) for values in (self.budgets, self.seeds, self.systems))
                or not set(self.systems) <= set(SYSTEMS)):
            raise ValueError("matrix requires unique budgets, seeds and known systems")
        if len(self.budgets) * len(self.seeds) * len(self.systems) > 512:
            raise ValueError("campaign exceeds 512 bounded slots")
        for budget in self.budgets:
            if not 1 <= budget <= 256:
                raise ValueError("campaign does not lift the 256-proposal runtime limit")
            for seed in self.seeds:
                Case(self.pack, budget, seed)
            pack = load_parity_pack(self.pack)
            if "contenders" in self.systems and any(
                    budget // len(pack.benchmarks) < len(get_benchmark(name).required_contenders) for name in pack.benchmarks):
                raise ValueError("campaign budget cannot cover the required contender floor")
        return self


def contender_pool_path(spec):
    """Select only a versioned, repository-owned pool; its bytes are source-bound."""
    name = "pools.yaml" if spec.contender_pool is None else "research_pools/" + spec.contender_pool + ".yaml"
    return "EvoNN-Contenders/src/evonn_contenders/" + name


def sha(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def versions():
    result = {}
    for name in ("numpy", "scipy", "scikit-learn", "pandas", "openml", "mlx", "mlx-metal", "duckdb", "pyarrow",
                 "pydantic", "PyYAML", "torch", "xgboost", "lightgbm", "catboost"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def identity():
    commit, dirty = code_identity()
    if dirty:
        raise ValueError("campaign requires a clean committed source tree")
    if shared_root().absolute() != ROOT / "shared-benchmarks":
        raise ValueError("campaign requires the repository's pinned benchmark root")
    files = sorted(p for p in (ROOT / "shared-benchmarks").rglob("*") if p.is_file() and p.suffix in {".json", ".yaml"})
    files += sorted((ROOT / "EvoNN-Contenders" / "src" / "evonn_contenders").rglob("*.yaml"))
    return {"commit": commit, "source_sha256": source_identity(), "python": sys.executable,
            "prefix": sys.prefix, "host": list(host_fields().values()),
            "versions": versions(),
            "data_files": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}


@contextmanager
def lease(root):
    root = create_artifact_directory(root)
    try:
        publish_artifact(root / ".campaign.lock", b"")
    except FileExistsError:
        pass
    with open_directory(root) as directory, open_regular_at(directory, ".campaign.lock", exclusive=True) as fd:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Do not explicitly LOCK_UN: a surviving inherited child must retain it.
        yield fd


def read_manifest(root):
    value = json.loads(read_document(root, "campaign.json"))
    if set(value) != {"schema_version", "spec", "identity", "cache", "datasets", "workspace", "sha256"}:
        raise ValueError("invalid campaign manifest fields")
    if value["schema_version"] != "evonn.campaign/v1" or sha({k: v for k, v in value.items() if k != "sha256"}) != value["sha256"]:
        raise ValueError("campaign manifest checksum mismatch")
    CampaignSpec.model_validate(value["spec"])
    if value["workspace"] != str(root.absolute()):
        raise ValueError("campaign workspace moved; explicit migration required")
    return value


def slots(spec):
    return [(Case(spec.pack, budget, seed), system) for budget in spec.budgets for seed in spec.seeds for system in spec.systems]


def slot_id(case, system):
    return case.id + "_" + system


def probe_transformer():
    """Report missing/broken mandatory baseline support as a campaign blocker."""
    try:
        result = subprocess.run([sys.executable, "-c", "import torch; from torch import nn; nn.TransformerEncoderLayer(64, 4)"],
                                capture_output=True, timeout=30)
    except subprocess.TimeoutExpired as error:
        detail = (error.stderr or b"").decode(errors="replace")
        raise ValueError("baseline Transformer probe timed out: " + detail) from error
    if result.returncode:
        raise ValueError("baseline screening requires a working Torch Transformer: "
                         + result.stderr.decode(errors="replace").strip())


def preflight(root):
    manifest = read_manifest(root)
    spec = CampaignSpec.model_validate(manifest["spec"])
    if identity() != manifest["identity"]:
        raise ValueError("campaign source, environment, host or catalog drift")
    if spec.contender_pool is not None:
        # This is a mandatory family in this experiment, even though the generic CLI treats it as optional.
        probe_transformer()
    if spec.backend == "mlx_native":
        # Verify availability through Shared backend discovery, without fitting.
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            raise ValueError("native campaign requires qualified Apple Silicon host")
        import mlx.core as mx
        mx.eval(mx.array([1.0]) + 1)
    if shutil.disk_usage(root).free < spec.min_free_bytes:
        raise ValueError("campaign minimum free disk reserve unavailable")
    expected = {(name, seed) for name in load_parity_pack(spec.pack).benchmarks for seed in spec.seeds}
    actual = [(d["benchmark_id"], d["seed"]) for d in manifest["datasets"]]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("campaign data matrix incomplete or duplicated")
    for data in manifest["datasets"]:
        directory = Path(data["cache_directory"])
        if directory.parent.parent != Path(manifest["cache"]) or directory.name != data["split_sha256"]:
            raise ValueError("campaign cache path differs from pinned split")
        arrays = {}
        for item in data["cache_artifacts"]:
            reference = ArtifactReference(path=item["path"], sha256=item["sha256"])
            payload = read_verified_artifact(directory, reference, size_bytes=item["size_bytes"])
            arrays[Path(item["path"]).stem] = np.load(io.BytesIO(payload), allow_pickle=False)
        if set(arrays) != {"x_train", "y_train", "x_validation", "y_validation"} or array_digest(arrays) != data["split_sha256"]:
            raise ValueError("campaign cache content differs from pinned split")
    return {"status": "passed", "slots": len(slots(spec)), "manifest_sha256": manifest["sha256"],
            "maximum_dispatch_seconds": len(slots(spec)) * (spec.timeout + 20), "training_started": False}


def new_plan_defaults(spec):
    """Freeze defaults for new plans without reinterpreting historical manifests."""
    if "stratograph" in spec.systems and "stratograph_research" not in spec.model_fields_set:
        # Omission selects the standard; explicit null remains a legacy control.
        spec = CampaignSpec.model_validate({**spec.model_dump(), "stratograph_research": standard_hierarchy_policy()})
    if "topograph" in spec.systems and spec.topograph_variant is None:
        # Resolve only NEW plans. An absent field in a historical manifest remains legacy.
        spec = CampaignSpec.model_validate({**spec.model_dump(), "topograph_variant": "next",
                                           "topograph_research": TopographResearchPolicy(adapters="mixer")})
    if "primordia" in spec.systems and spec.primordia_research is None:
        # Freeze new defaults explicitly; reading historical manifests stays additive.
        spec = CampaignSpec.model_validate({**spec.model_dump(), "primordia_research": PrimordiaResearchPolicy()})
    return spec


def prepare_plan(root, spec, cache, *, timeout=1800):
    """Prepare/verify all datasets in bounded subprocesses, then freeze the plan."""
    spec = new_plan_defaults(spec)
    if not 0 < timeout <= 1800:
        raise ValueError("planning preparation cap must be at most 1800 seconds")
    root, cache = root.absolute(), cache.absolute()
    pinned = identity()
    deadline = time.monotonic() + timeout
    with lease(root):
        if (root / "campaign.json").exists():
            raise ValueError("campaign already planned; use preflight or a new workspace")
        prepared = create_artifact_directory(root / "preparation")
        datasets = []
        for seed in spec.seeds:
            for name in load_parity_pack(spec.pack).benchmarks:
                output = prepared / f"{name}_{seed}.json"
                if output.exists():
                    raise ValueError("incomplete planning artifacts exist; use a new workspace")
                command = [sys.executable, "-m", "evonn_compare.campaign_worker", "prepare", name, str(seed), str(cache), str(output)]
                _bounded_process(command, deadline - time.monotonic(), prepared / f"{name}_{seed}.log")
                datasets.append(json.loads(read_document(prepared, output.name)))
        if identity() != pinned:
            raise ValueError("source or environment changed during planning")
        value = {"schema_version": "evonn.campaign/v1", "spec": spec.model_dump(mode="json"), "identity": pinned,
                 "cache": str(cache), "datasets": datasets, "workspace": str(root)}
        publish_artifact(root / "campaign.json", encoded({**value, "sha256": sha(value)}))
    return preflight(root)


def _bounded_process(command, timeout, log, *, pass_fds=(), stdout_path=None):
    if timeout <= 0:
        raise ValueError("invocation time budget exhausted before dispatch")
    # File output avoids unbounded PIPE buffers and records diagnostics after death.
    with ExitStack() as stack:
        diagnostics = stack.enter_context(log.open("xb"))
        output = diagnostics if stdout_path is None else stack.enter_context(stdout_path.open("xb"))
        process = subprocess.Popen(command, stdout=output,
                                   stderr=subprocess.STDOUT if stdout_path is None else diagnostics,
                                   start_new_session=True, pass_fds=pass_fds)
        try:
            result = process.wait(timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise
    if result:
        raise ValueError(f"campaign subprocess exited {result}; see {log}")


def events(root, manifest):
    directory = root / "events"
    result, previous = [], "0" * 64
    known = {slot_id(c, s) for c, s in slots(CampaignSpec.model_validate(manifest["spec"]))}
    if not directory.exists():
        return result
    for index, path in enumerate(sorted(p for p in directory.iterdir() if not re.fullmatch(r"\.publish-[0-9a-f]{32}", p.name)), 1):
        if path.name != f"{index:06d}.json":
            raise ValueError("campaign journal gap or unknown file")
        item = json.loads(read_document(directory, path.name))
        if (set(item) != {"sequence", "previous", "manifest", "slot", "kind", "details", "sha256"}
                or item["sequence"] != index or item["previous"] != previous or item["manifest"] != manifest["sha256"]
                or item["slot"] not in known or item["kind"] not in {"dispatch", "complete"}
                or sha({k: v for k, v in item.items() if k != "sha256"}) != item["sha256"]):
            raise ValueError("invalid campaign journal chain")
        if any(old["slot"] == item["slot"] and old["kind"] == "complete" for old in result):
            raise ValueError("completed campaign slot cannot transition again")
        result.append(item)
        previous = item["sha256"]
    return result


def append_event(root, manifest, history, slot, kind, details):
    directory = create_artifact_directory(root / "events")
    item = {"sequence": len(history) + 1, "previous": history[-1]["sha256"] if history else "0" * 64,
            "manifest": manifest["sha256"], "slot": slot, "kind": kind, "details": details}
    item["sha256"] = sha(item)
    publish_artifact(directory / f"{item['sequence']:06d}.json", encoded(item))
    history.append(item)
    return item


def match_config(config, manifest, case, system):
    spec = CampaignSpec.model_validate(manifest["spec"])
    if config["git_commit"] != manifest["identity"]["commit"] or config["code_dirty"]:
        raise ValueError("campaign export producer mismatch")
    if system != "contenders":
        expected = {"system": system, "pack": case.pack, "total": case.budget, "seed": case.seed, "backend": spec.backend,
                    "epochs": spec.epochs, "timeout": spec.timeout, "fit_timeout": spec.fit_timeout,
                    "population_size": 4, "device": "cpu", "source_sha256": manifest["identity"]["source_sha256"],
                    "cache": manifest["cache"], "shared_root": str(ROOT / "shared-benchmarks")}
        if system == "stratograph":
            expected["variant"] = "shared"
            policy = spec.stratograph_research.model_dump(mode="json") if spec.stratograph_research else None
            if config.get("research") != policy:
                raise ValueError("campaign hierarchy research policy mismatch")
        if system == "prism":
            # Historical manifests/exports omitted these additive fields. New
            # exports must match the explicitly frozen experiment or defaults.
            settings = (spec.prism_research or PrismResearchPolicy()).model_dump()
            if spec.prism_research is not None or "variant" in config:
                if any(key not in config or config[key] != value for key, value in settings.items()):
                    raise ValueError("campaign Prism research policy mismatch")
        if system == "topograph":
            expected.update(benchmark_pooling=False, novelty_weight=0.0)
            if config.get("variant", "legacy") != (spec.topograph_variant or "legacy"):
                raise ValueError("campaign Topograph research policy mismatch")
            policy = (spec.topograph_research or TopographResearchPolicy()).model_dump() if spec.topograph_variant == "next" else None
            if config.get("research_options") != policy:
                raise ValueError("campaign Topograph research options mismatch")
        if system == "primordia":
            policy = spec.primordia_research or PrimordiaResearchPolicy()
            settings = {**policy.model_dump(), "training_policy": policy.training_policy}
            if spec.primordia_research is not None or any(key in config for key in settings):
                if any((config[key] if key in config else RESEARCH_DEFAULTS[key] if key in RESEARCH_DEFAULTS else None) != value for key, value in settings.items()):
                    raise ValueError("campaign Primordia research policy mismatch")
        if any(config[key] != value for key, value in expected.items()):
            raise ValueError("campaign export training settings mismatch")
    elif config["fit_timeout_seconds"] != spec.fit_timeout or config["enhanced"] != spec.enhanced:
        raise ValueError("campaign contender settings mismatch")
    if system == "contenders":
        pool_path = contender_pool_path(spec)
        expected_sha = manifest["identity"]["data_files"][pool_path]
        payload = read_verified_artifact(ROOT, ArtifactReference(path=pool_path, sha256=expected_sha))
        if config["pool_sha256"] != expected_sha or config["pools"] != yaml.safe_load(payload):
            raise ValueError("campaign contender pool mismatch")
    expected_versions = {name: manifest["identity"]["versions"][name] for name in ("numpy", "scipy", "scikit-learn", "pandas", "openml")}
    if config["dataset_versions"] != expected_versions:
        raise ValueError("campaign export dependency mismatch")


def adopted(root, manifest, case, system):
    directory = root / "runs" / slot_id(case, system)
    candidates = list(directory.iterdir()) if directory.exists() else []
    if len(candidates) > 1 or any(not p.is_dir() or p.is_symlink() for p in candidates):
        raise ValueError("campaign slot has ambiguous or unsafe run directories")
    if not candidates:
        return None, None
    run = candidates[0]
    if not (run / "symbiosis").exists():
        return run, None
    bundle = read_export(run / "symbiosis")
    spec = CampaignSpec.model_validate(manifest["spec"])
    if bundle.manifest.system.value != system:
        raise ValueError("campaign export system mismatch")
    config = artifact_json(bundle, "config.yaml")
    match_config(config, manifest, case, system)
    host = manifest["identity"]["host"]
    device = host[1].lower() + "_" + host[2] + "_cpu"
    budget = execution_budget(load_parity_pack(case.pack), case.budget, spec.timeout, device)
    if bundle.manifest.budget.model_dump(mode="json") != budget:
        raise ValueError("campaign export budget envelope mismatch")
    host_fields = {"host": host[0], "system": host[1], "machine": host[2], "processor": host[3]}
    host_hash = hashlib.sha256((encoded if system == "contenders" else encode)(host_fields)).hexdigest()
    runtime = bundle.manifest.runtime
    if runtime.host_fingerprint != host_hash or runtime.device_class != device:
        raise ValueError("campaign export host mismatch")
    if system != "contenders":
        version = manifest["identity"]["versions"]["mlx" if spec.backend == "mlx_native" else "numpy"]
        if runtime.backend.value != spec.backend or runtime.backend_version != version:
            raise ValueError("campaign export backend mismatch")
    data = artifact_json(bundle, "dataset_provenance.json")
    expected_data = [d for d in manifest["datasets"] if d["seed"] == case.seed]
    if sorted(data, key=lambda d: d["benchmark_id"]) != sorted(expected_data, key=lambda d: d["benchmark_id"]):
        raise ValueError("campaign export dataset provenance mismatch")
    acceptance = evaluate_case(case, [bundle], no_contenders=system != "contenders")
    if acceptance["blockers"]:
        raise ValueError("campaign export incomplete or invalid: " + "; ".join(acceptance["blockers"]))
    audit = benchmark_audit(case.pack, [bundle], parameter_screening=spec.contender_pool is not None)
    # A single engine has no floor; contender admission itself must be valid.
    if system == "contenders" and audit["blockers"]:
        raise ValueError("campaign contender audit failed: " + "; ".join(audit["blockers"]))
    if system == "contenders" and spec.contender_pool is not None:
        attempts = artifact_json(bundle, "attempts.json")["attempts"]
        for benchmark in load_parity_pack(case.pack).benchmarks:
            for family in ("unigram_lm", "bigram_lm", "trigram_lm", "transformer_lm_tiny"):
                expected = case.budget // 16
                successful = [a for a in attempts if a["benchmark_id"] == benchmark
                              and a["contender_id"] == family and a["status"] == "ok"]
                if len(successful) != expected:
                    raise ValueError("baseline screening family coverage incomplete")
                if family == "transformer_lm_tiny":
                    for attempt in successful:
                        epochs = config["pools"]["models"][family]["parameters"]["epochs"]
                        updates = epochs * ((attempt["training_rows"] + 31) // 32)
                        if (attempt.get("completed_epochs") != epochs or attempt.get("optimizer_updates") != updates
                                or attempt.get("model_selection") != "fixed_final_epoch"):
                            raise ValueError("baseline screening training telemetry mismatch")
    references = [ArtifactReference(path=name, sha256=hashlib.sha256(read_document(bundle.root, name)).hexdigest()).model_dump(mode="json")
                  for name in ("manifest.json", "results.json", "summary.json")]
    return run, {"system": system, "run_id": bundle.manifest.run_id, "export": str(bundle.root.relative_to(root)), "documents": references}


def active_dispatch(root, history, slot):
    dispatches = [e for e in history if e["slot"] == slot and e["kind"] == "dispatch"]
    for event in dispatches:
        path = root / "dispatch" / f"{event['sequence']:06d}.started.json"
        if path.exists():
            value = json.loads(read_document(path.parent, path.name))
            if set(value) != {"dispatch", "pid"} or value["dispatch"] != event["sha256"] or type(value["pid"]) is not int or value["pid"] <= 1:
                raise ValueError("invalid durable dispatch identity")
            try:
                os.killpg(value["pid"], 0)
            except ProcessLookupError:
                continue
            raise ValueError("prior dispatch process group may still be alive; refusing duplicate work")


def run_campaign(root, *, session_timeout=1800, max_runs=None, only_case=None):
    if not 0 < session_timeout <= 1800 or (max_runs is not None and (type(max_runs) is not int or max_runs < 1)):
        raise ValueError("session limit must be at most 1800 seconds; max-runs positive")
    root = root.absolute()
    deadline, launched = time.monotonic() + session_timeout, 0
    with lease(root) as fd:
        preflight(root)
        manifest = read_manifest(root)
        spec = CampaignSpec.model_validate(manifest["spec"])
        segment_timeout = min(spec.timeout, 1740.0)
        history = events(root, manifest)
        selected_slots = slots(spec)
        if only_case is not None:
            selected_slots = [(case, system) for case, system in selected_slots if case == only_case]
            if not selected_slots:
                raise ValueError("requested case is outside the declared campaign matrix")
        for case, system in selected_slots:
            slot = slot_id(case, system)
            active_dispatch(root, history, slot)
            run, reference = adopted(root, manifest, case, system)
            completed = [e for e in history if e["slot"] == slot and e["kind"] == "complete"]
            if completed:
                if reference != completed[0]["details"]:
                    raise ValueError("completed campaign evidence changed or disappeared")
                continue
            if reference is not None:
                append_event(root, manifest, history, slot, "complete", reference)
                continue
            if (max_runs is not None and launched >= max_runs) or deadline - time.monotonic() < segment_timeout + 20:
                break  # Never shrink a later slot's declared budget.
            preflight(root)
            output = create_artifact_directory(root / "runs" / slot)
            command = [sys.executable, "-m", MODULES[system], "run", "--pack", case.pack, "--budget", str(case.budget),
                       "--seed", str(case.seed), "--output", str(output), "--cache", manifest["cache"],
                       "--timeout", str(spec.timeout), "--fit-timeout", str(spec.fit_timeout)]
            if system != "contenders":
                command += ["--backend", spec.backend, "--epochs", str(spec.epochs)]
            elif spec.enhanced:
                command.append("--enhanced")
            if system == "contenders" and spec.contender_pool is not None:
                command += ["--pools", str(ROOT / contender_pool_path(spec))]
            if system == "stratograph":
                # Historical manifests without a policy must never pick up a new CLI default.
                policy = spec.stratograph_research.model_dump(mode="json") if spec.stratograph_research else None
                command += ["--research", json.dumps(policy, sort_keys=True)]
            if system == "topograph":
                command += ["--variant", spec.topograph_variant or "legacy"]
                if spec.topograph_research is not None:
                    command += ["--research-options", json.dumps(spec.topograph_research.model_dump(mode="json"), sort_keys=True)]
            if system == "primordia":
                policy = spec.primordia_research or PrimordiaResearchPolicy()
                for key, value in policy.model_dump().items():
                    command += ["--" + key.replace("_", "-"), str(value)]
            if system == "prism" and spec.prism_research is not None:
                for key, value in spec.prism_research.model_dump().items():
                    if value is not None:
                        command += ["--" + key.replace("_", "-"), json.dumps(value, sort_keys=True) if isinstance(value, dict) else value]
            previous_completed = 0
            if run is not None:
                if system == "contenders":
                    raise ValueError("incomplete Contenders run has no resume contract; retained without restarting")
                match_config(json.loads(read_document(run, "config.yaml")), manifest, case, system)
                _, payload = load_runtime_checkpoint(run / "checkpoints")
                state = json.loads(payload)
                previous_completed = state["completed"]
                if state["completed"] > case.budget or (state["elapsed"] >= spec.timeout and state["completed"] < case.budget):
                    raise ValueError("incomplete slot exhausted its budget; no automatic replacement")
                command += ["--resume", str(run)]
            if deadline - time.monotonic() < segment_timeout + 20:
                break  # Preflight/recovery must not consume the reserved slot budget.
            event = append_event(root, manifest, history, slot, "dispatch", {"command": command})
            dispatch = create_artifact_directory(root / "dispatch")
            description = dispatch / f"{event['sequence']:06d}.json"
            publish_artifact(description, encoded(event))
            _bounded_process([sys.executable, "-m", "evonn_compare.campaign_worker", "dispatch", str(description), str(fd)],
                             segment_timeout + 20, dispatch / f"{event['sequence']:06d}.log", pass_fds=(fd,))
            launched += 1
            current_run, reference = adopted(root, manifest, case, system)
            if reference is None:
                if spec.timeout > 1800 and current_run is not None:
                    _, payload = load_runtime_checkpoint(current_run / "checkpoints")
                    progress = json.loads(payload)
                    if (previous_completed < progress["completed"] < case.budget
                            and progress["elapsed"] < spec.timeout
                            and all(a["status"] == "ok" for a in progress["attempts"])):
                        break
                raise ValueError("run ended without a verified complete export; preserved for resume")
            append_event(root, manifest, history, slot, "complete", reference)
        completed = {e["slot"]: e["details"] for e in history if e["kind"] == "complete"}
        for case in [Case(spec.pack, b, s) for b in spec.budgets for s in spec.seeds]:
            if all(slot_id(case, system) in completed for system in spec.systems):
                report = create_artifact_directory(root / "reports" / case.id)
                document = {"schema_version": "1.0.0", "case": case.as_dict(), "systems": spec.systems,
                            "cohort": "current", "no_contenders": "contenders" not in spec.systems,
                            "runs": [completed[slot_id(case, system)] for system in spec.systems], "failures": []}
                try:
                    publish_artifact(report / "case.json", encoded(document))
                except FileExistsError:
                    if read_document(report, "case.json") != encoded(document):
                        raise ValueError("campaign case evidence changed")
        workspace_report(root)
        return {"status": "complete" if len(completed) == len(slots(spec)) else "paused", "completed": len(completed),
                "total": len(slots(spec)), "new_runs": launched, "scientific_decision": "not_evaluated"}
