# 12 — Security, Privacy, and Software/Model Supply Chain

## 1. Threat model

EvoNN is local-first but processes potentially hostile datasets, archives, model files, URLs, plugins, and metadata. The local user is trusted to administer the product; imported content and candidate code are not implicitly trusted.

## 2. Network policy

Network access is controlled by phase:

- dataset acquisition;
- model/asset acquisition;
- dependency preparation;
- job execution;
- publication.

SEC-001: Job worker network access defaults to denied.  
SEC-002: Allowed destinations MUST be explicit and auditable.  
SEC-003: Undeclared requests MUST be denied and recorded.  
SEC-004: No dataset, prompt, model, usage telemetry, or metadata may be uploaded without explicit user action and visible destination.  
SEC-005: Credentials MUST use protected references and MUST NOT appear in URLs, configs, logs, events, or exports.

## 3. Hostile downloads and archives

The acquisition pipeline MUST validate TLS, redirects, sizes, MIME, checksums, signatures where available, archive safety, filenames, extraction paths, and quotas. It MUST quarantine mismatches and never execute dataset-supplied code, macros, notebooks, setup hooks, pickle payloads, or shell scripts.

## 4. Safe serialization

- Safetensors SHOULD be used for tensor weights.
- Skops or declarative reconstruction SHOULD be used for compatible scikit-learn models.
- Pickle-family loading is forbidden for untrusted artifacts.
- Hugging Face models SHOULD prefer safe tensor files and exact revisions.
- `trust_remote_code` or equivalent arbitrary remote code execution is disabled by default and requires explicit approval plus isolated execution.

## 5. Filesystem safety

All user and imported paths MUST be normalized and checked against allowed roots. Artifact manifests use relative paths. Symlinks, hardlinks, special files, case/Unicode collisions, path traversal, and overwrite conflicts MUST be validated.

Temporary directories MUST be private. Model/data bundles MUST not expose home-directory paths or usernames.

## 6. Worker isolation

Ray is not a security boundary. Worker processes follow ADR-0007 trust classes and MUST use qualified OS-level controls appropriate to the host. Built-in workers receive no acquisition credentials and consume only pre-materialized immutable inputs. Candidate-supplied executable code is outside normal v1 scope; experimental enablement requires a stronger qualified sandbox and cannot silently retain decision-grade status.

## 7. Local Web security

- Bind to loopback by default.
- Use a random session secret and authenticated local session.
- Require explicit opt-in and strong authentication before non-loopback binding.
- Enforce origin/host checks, CSRF protection for state changes, restrictive CORS, secure cookies where applicable, CSP, clickjacking protections, request size limits, and rate limits for sensitive actions.
- File downloads MUST resolve authorized artifact IDs, not arbitrary paths.
- WebSocket/SSE clients MUST authenticate and authorize project access.

## 8. Secrets

Secrets MUST be stored through OS keychain/keyring or environment/file references with restrictive permissions. Secret values MUST never enter content digests, provenance exports, diagnostics, or model bundles.

## 9. Privacy

Dataset descriptors MUST classify personal/sensitive data, jurisdiction/location constraints, retention, permitted use, and preview policy. Unknown privacy classification is treated as restrictive.

Raw sensitive values MUST be excluded from logs, previews, reports, and diagnostics by default. Deletion/takedown MUST propagate through caches and derived artifacts according to lineage and legal hold.

## 10. Dependency supply chain

Releases MUST use locked dependencies and record exact package hashes where tooling permits. CI MUST perform:

- vulnerability scanning;
- license inventory;
- SBOM generation;
- dependency provenance checks;
- secret scanning;
- static analysis;
- signed release artifact verification.

Permissive licenses are preferred. Dependency-specific commercial wording or ambiguity MUST receive documented legal review rather than assumption.

## 11. Model/data supply chain

External assets MUST record source, resolved immutable revision, file hashes, license, publisher, acquisition event, and verification status. A checksum proves equality, not publisher authenticity.

Decision-grade authenticity requires at least one of: a verified publisher signature/attestation; retrieval from an allowlisted publisher endpoint with pinned immutable revision plus independently published hashes; or a user/org-approved local source with a recorded custody event. Unsigned assets that meet only byte-integrity requirements may be used operationally only with `authenticity: unverified` and cannot support provenance-sensitive benchmark claims. Signature failure, publisher mismatch, or unknown origin fails closed.

## 12. Signing and OCI

Release and model artifacts SHOULD support Sigstore-compatible signing. OCI/ORAS MAY attach signatures, SBOMs, provenance, and related artifacts. Offline verification requirements MUST be defined; signing services MUST not become mandatory for local model creation.

## 13. Security failure semantics

Integrity mismatch, unsafe archive, forbidden serialization, unknown license/privacy status, unauthorized network access, secret exposure, or signature failure MUST block decision-grade use and generate a stable security reason code.
