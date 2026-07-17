# ADR-0007 — Worker Trust Classes and Platform Isolation

**Status:** Provisional — platform mechanisms must pass security acceptance tests

## Context

Ray resource declarations provide scheduling admission control, not a security boundary. macOS and Linux offer different process, network, and filesystem isolation primitives. V1 excludes arbitrary user plugins but still handles hostile data/model artifacts.

## Decision

V1 defines three trust classes:

1. **Built-in trusted code:** code shipped and integrity-verified with EvoNN. It may process untrusted bytes only through hardened loaders.
2. **Acquired declarative artifact:** weights/data/config with no executable code. Safe formats and schema validation are mandatory.
3. **Untrusted executable code:** out of normal v1 scope. It may run only in an explicitly enabled stronger sandbox profile and cannot produce decision-grade evidence unless that profile is qualified.

All workers run as separate process groups with private workspaces, minimal environment, no inherited secrets or database handles, resource limits, and controlled artifact publication.

Linux decision-grade isolation MUST use qualified OS mechanisms for filesystem confinement, cgroup/resource limits, process limits, and network policy (for example rootless namespaces/container primitives plus seccomp where supported).

macOS decision-grade isolation MUST use a qualified mechanism that enforces the declared filesystem/resource/network policy. Until that mechanism passes acceptance tests, workers are limited to built-in trusted code, receive no credentials, perform no acquisition, and use only pre-materialized immutable inputs; any unenforceable network restriction is surfaced as a capability limitation rather than claimed as enforced.

## Consequences

- Ray remains replaceable scheduling infrastructure only.
- Arbitrary remote model code is disabled by default.
- Host capability manifests include isolation level.
- Jobs requiring stronger isolation fail preflight on unqualified hosts.
- Security acceptance includes attempted filesystem escape, subprocess escape, network access, secret access, and resource exhaustion on each host class.
