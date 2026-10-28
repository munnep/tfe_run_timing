# Run timing: `run-Yn7hF28bzifJ3snT`

| Item | Value |
|---|---|
| Organization | `test` |
| Project | `Default Project` |
| Workspace | `test` |
| Created by | `admin` |
| Plan ID | `plan-6eRGL5Sz3gFrBoae` |
| Terraform CLI | `1.16.6` |
| Agent version | `1.33.3` |
| Agent pool | `apool-CT6zqa4Q4xmVrUVR` |

## Summary

- **Final run state seen:** `planned` at 09:31:16
- **Total, run create to last run-state/agent event (09:31:17.221):** 2m 09s
- **Before the run was created:** 2s from first call (09:29:06) to run create, 8 calls; configuration version `cv-g7QKUHSogTbb41GT` **confirmed**
- **Total, first call before the run to last run-state/agent event:** 2m 11s
- **Longest agent steps:**
  1. 2m 01s - `terraform: Running terraform plan` (Plan), 94% of the run
  2. 2.2s - `terraform: Running terraform init` (Plan), 2% of the run
  3. 1.6s - `terraform: Generating and uploading provider schemas JSON` (Plan), 1% of the run

## Before the run was created

Calls by `admin` (token `at-w3m1GdmvCV9bkvAz`, IP `62.45.32.200`) up to the run-create request `59dfb072-6cd8-4bb1-b6dd-2b64a93adcac`. Window: last 15 min. Atlas logs whole seconds, so gaps are +/- 1s.

| Time (UTC) | Gap | Request | Status | Took | Audit event | Matched by |
|---|---|---|---|---|---|---|
| 09:29:06 |  | `GET /.well-known/terraform.json` | 200 | 8 ms |  | IP only |
| 09:29:06 | +0s | `GET /api/v2/ping` | 204 | 1 ms |  | IP only |
| 09:29:06 | +0s | `GET /api/v2/organizations/test/entitlement-set` | 200 | 82 ms |  | token |
| 09:29:06 | +0s | `GET /api/v2/organizations/test/workspaces/test` | 200 | 135 ms |  | token |
| 09:29:06 | +0s | `POST /api/v2/workspaces/ws-QgMV89wqE8yGSRMF/configuration-versions` | 201 | 141 ms | `configuration_version create cv-g7QKUHSogTbb41GT` | token |
| 09:29:07 | +1s | `PUT /api/internal/archivist/callback` | 200 | 30 ms | `configuration_version uploaded cv-g7QKUHSogTbb41GT` | config version audit |
| 09:29:07 | +0s | `GET /api/v2/configuration-versions/cv-g7QKUHSogTbb41GT` | 200 | 51 ms | `configuration_version read cv-g7QKUHSogTbb41GT` | token |
| 09:29:08 | +1s | `POST /api/v2/runs` | 201 | 308 ms | `run create run-Yn7hF28bzifJ3snT` | token |

- **First call to run create:** 2s (09:29:06 to 09:29:08)
- **Configuration version:** `cv-g7QKUHSogTbb41GT` - **confirmed**; agent "Downloading Terraform configuration" at 09:29:11.452, archivist "Starting download request" for cv-g7QKUHSogTbb41GT 8 ms later
- **Upload to archivist:** started 09:29:06.965, TFE callback done after 291 ms

## Run state changes

| State entered | Time (UTC) | Time in that state |
|---|---|---|
| `create` | 09:29:08 | 0s |
| `queue` | 09:29:08 | 2s |
| `planning` | 09:29:10 | 2m 06s |
| `finished` | 09:31:16 | 0s |
| `planned` | 09:31:16 | (last seen) |

## Agent time per stage

| Stage | First agent event | Last agent event | Duration |
|---|---|---|---|
| Plan | 09:29:09.868 | 09:31:17.221 | 2m 07s |

## Timeline

All times UTC. _Elapsed_ is counted from run create. _Step took_ is the time until the next agent event of the same stage.

| Time | Elapsed | Step took | Source | Event |
|---|---|---|---|---|
| 09:29:08 | 0s |  | run state | create |
| 09:29:08 | 0s |  | run state | queue |
| 09:29:08.272 | 0.3s |  | task-worker (Plan) | task-worker POST /v1/task/invoke -> HTTP 201 (2.263591ms) |
| 09:29:09.868 | 1.9s | 0.0s | agent (Plan) | agent: Starting: agent_version=1.33.3 os=linux arch=arm64 |
| 09:29:09.893 | 1.9s | 0.2s | agent (Plan) | core: Starting: version=1.33.3 |
| 09:29:10 | 2s |  | audit (Plan) | agent dequeue agent-giELA9Ask1j4z6zB |
| 09:29:10 | 2s |  | run state | planning |
| 09:29:10.054 | 2.1s | 0.0s | agent (Plan) | core: Agent registered successfully with HCP Terraform: agent_id=agent-giELA9Ask1j4z6zB agent_pool_id=apool-CT6zqa4Q4xmVrUVR |
| 09:29:10.057 | 2.1s | 0.4s | agent (Plan) | core: Waiting for next job |
| 09:29:10.457 | 2.5s | 0s | agent (Plan) | core: Job received: job_type=plan job_id=run-Yn7hF28bzifJ3snT |
| 09:29:10.457 | 2.5s | 0.5s | agent (Plan) | terraform: Handling run: run_id=run-Yn7hF28bzifJ3snT run_operation=plan organization_name=test workspace_name=test |
| 09:29:11.000 | 3s | 0.4s | agent (Plan) | terraform: Extracting Terraform from release archive |
| 09:29:11.412 | 3.4s | 0s | agent (Plan) | terraform: Downloading Terraform configuration |
| 09:29:11.412 | 3.4s | 0.1s | agent (Plan) | terraform: Terraform CLI details: version=1.16.6 |
| 09:29:11.478 | 3.5s | 0.0s | agent (Plan) | terraform: Executing hook: hook=pre-plan |
| 09:29:11.482 | 3.5s | 2.2s | agent (Plan) | terraform: Running terraform init |
| 09:29:13.697 | 5.7s | 0s | agent (Plan) | terraform: Checking for eol module versions |
| 09:29:13.697 | 5.7s | 0.0s | agent (Plan) | terraform: Registry artifact usage control feature flag is disabled, skipping approval check |
| 09:29:13.716 | 5.7s | 2m 01s | agent (Plan) | terraform: Running terraform plan |
| 09:31:14.563 | 2m 07s | 0.3s | agent (Plan) | terraform: Generating and uploading plan JSON |
| 09:31:14.891 | 2m 07s | 1.6s | agent (Plan) | terraform: Generating and uploading provider schemas JSON |
| 09:31:16 | 2m 08s |  | run state | finished |
| 09:31:16 | 2m 08s |  | run state | planned |
| 09:31:16.495 | 2m 08s | 0.0s | agent (Plan) | terraform: Generating and uploading redacted plan JSON |
| 09:31:16.540 | 2m 09s | 0.1s | agent (Plan) | terraform: Persisting filesystem to remote storage |
| 09:31:16.656 | 2m 09s | 0.1s | agent (Plan) | terraform: Executing hook: hook=post-plan |
| 09:31:16.779 | 2m 09s | 0.3s | agent (Plan) | terraform: Finished handling run |
| 09:31:17.108 | 2m 09s | 0s | agent (Plan) | agent: Core plugin is shutting down |
| 09:31:17.108 | 2m 09s | 0.1s | agent (Plan) | agent: Shutting down |
| 09:31:17.213 | 2m 09s | 0.0s | agent (Plan) | core: Shutdown complete |
| 09:31:17.220 | 2m 09s | 0.0s | agent (Plan) | plugin: plugin process exited: plugin=/home/tfc-agent/bin/tfc-agent-core id=12 |
| 09:31:17.221 | 2m 09s |  | agent (Plan) | Graceful shutdown complete |

## TFE API calls for this run

Response times as logged by atlas (view/db are part of the total). Sorted by slowest call.

| Request | Calls | Avg | Max | Max DB | Status |
|---|---|---|---|---|---|
| `GET /api/v2/runs/:run` | 6 | 62 ms | 86 ms | 12 ms | 200 |
| `GET /api/v2/runs/:run/apply` | 1 | 66 ms | 66 ms | 11 ms | 200 |
| `GET /api/v2/runs/:run/run-events` | 1 | 44 ms | 44 ms | 5 ms | 200 |

## Log reads (archivist / nginx)

Someone or something reading the plan/apply log while the run was active or afterwards.

| Source | What | Count | First | Last |
|---|---|---|---|---|
| archivist | plan log read | 4 | 2026-10-28 09:29:09.484 | 2026-10-28 09:31:17.953 |
| archivist | apply log read | 12 | 2026-10-28 09:29:12.015 | 2026-10-28 09:32:53.264 |

_Generated by run_timing.sh from 64 unique log lines._
