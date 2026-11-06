# Reliability Evaluation Post-Mortem

## Overview & Scope
During the 20-run reliability benchmark evaluating untrusted code submissions across fresh Celesto microVM sandboxes, 18 of 20 runs achieved complete end-to-end verification and clean lifecycle termination, yielding an overall **success rate of 90.0%** (18/20). Two runs (`sbx-evalrun0007` and `sbx-evalrun0014`) failed during tool execution within the guest environment.

## Incident Analysis of Failed Runs

### Run 1: `sbx-evalrun0007` (Wall-clock: 4.70s, Step: Dependency Resolution)
- **Symptom**: `DependencyConflictError` encountered during `pip install --no-cache-dir` within the guest VM.
- **Root Cause**: The untrusted submission contained a pinned transitive dependency (`protobuf==3.20.0`) that conflicted directly with the assessment harness runtime (`grpcio>=1.50.0`). The pip resolver stalled in backtracking before tripping the 4.0-second guest execution budget.
- **MicroVM Containment Behavior**: The failure remained entirely confined to the guest's virtual disk layer (`/opt/venv`). The Celesto lifecycle cleanup handler trapped the exception, issued a microVM destroy signal, and safely terminated the guest within 120ms without leaving dangling processes or orphaned disk overlays on the host.
- **Mitigation & Recovery**: For future runs, pre-installed wheel caches and isolated wheel mirrors will be provided via CelestoFS shared read-only mounts to eliminate runtime dependency network fetching and resolution thrashing.

### Run 2: `sbx-evalrun0014` (Wall-clock: 5.70s, Step: Recursive Integration Test)
- **Symptom**: `MemoryError / OOMKilled` triggered during recursive algorithmic validation in test suite 4.
- **Root Cause**: The untrusted candidate submission implemented an unbounded memoization cache that exhausted the 2GB microVM memory allotment under heavy load, triggering the Linux guest OOM killer which terminated the Python worker process.
- **MicroVM Containment Behavior**: Celesto's hardware-level microVM boundary prevented the guest kernel panic from leaking into the host control plane or sibling microVMs. The control plane received the non-zero exit code over the vsock channel, recorded the failure in the Postgres ledger, and cleanly destroyed the sandbox.
- **Mitigation & Recovery**: Implement an adaptive memory watchdog in the agent loop that monitors cgroup memory pressure within the guest and issues early graceful step aborts before the guest kernel terminates the test runner.

## Statistical Summary
- **Total Fresh Runs**: 20
- **Success Rate**: 90.0%
- **Median Wall-Clock Time**: 5.20s
- **P90 Wall-Clock Time**: 6.80s
- **Median Boot-to-Ready Time**: 0.53s
- **Total Compute Cost**: $0.0070 USD
- **Lifecycle Cleanup Efficacy**: 100% (20/20 sandboxes deleted without orphan retention)
