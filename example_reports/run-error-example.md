# Run timing: `run-fSmjR4Ge3PnNB3dd`

| Item | Value |
|---|---|
| Organization | `test` |
| Project | `Default Project` |
| Workspace | `test` |
| Created by | `admin` |
| Plan ID | `plan-BF7zzrBwYBQ5mJzk` |
| Terraform CLI | `1.16.6` |
| Agent version | `1.33.3` |
| Agent pool | `apool-CT6zqa4Q4xmVrUVR` |

## Summary

- **Final run state seen:** `errored` at 10:29:00
- **Total, run create to last run-state/agent event (10:29:00):** 6m 16s
- **Before the run was created:** 1m 25s from first call (10:21:19) to run create, 20 calls; configuration version `cv-XYTRACo6hC22cKiP` **unconfirmed (matched by user and time only)**
- **Total, first call before the run to last run-state/agent event:** 7m 41s
- **Longest agent steps:**
  1. 10.0s - `terraform: Running terraform plan` (Plan), 3% of the run
  2. 2.1s - `terraform: Running terraform init` (Plan), 1% of the run
  3. 0.7s - `terraform: Handling run: run_id=run-fSmjR4Ge3PnNB3dd run_operation=plan organization_name=test workspace_name=test` (Plan), 0% of the run

## Before the run was created

Calls by `admin` (token `at-w3m1GdmvCV9bkvAz`, IP `62.45.32.200`) up to the run-create request `d5c2fdb1-f1fb-43b9-82e3-72bedd2e7a1f`. Window: 15 min, cut at the previous run create `run-3RzuH6NgPouVHUYC` (10:21:19) by the same token. Atlas logs whole seconds, so gaps are +/- 1s.

| Time (UTC) | Gap | Request | Status | Took | Audit event | Matched by |
|---|---|---|---|---|---|---|
| 10:21:19 |  | `GET /api/v2/organizations/test/workspaces/test` | 200 | 24 ms |  | token |
| 10:21:19 | +0s | `POST /api/v2/workspaces/ws-QgMV89wqE8yGSRMF/configuration-versions` | 201 | 33 ms | `configuration_version create cv-8wtENE52Shv2UZYZ` | token |
| 10:21:22 | +3s | `GET /.well-known/terraform.json` | 200 | 1 ms |  | IP only |
| 10:21:22 | +0s | `GET /api/v2/ping` | 204 | 0 ms |  | IP only |
| 10:21:24 | +2s | `GET /.well-known/terraform.json` | 200 | 1 ms |  | IP only |
| 10:21:24 | +0s | `GET /api/v2/ping` | 204 | 0 ms |  | IP only |
| 10:21:31 | +7s | `GET /.well-known/terraform.json` | 200 | 1 ms |  | IP only |
| 10:21:31 | +0s | `GET /api/v2/ping` | 204 | 0 ms |  | IP only |
| 10:21:35 | +4s | `GET /.well-known/terraform.json` | 200 | 1 ms |  | IP only |
| 10:21:35 | +0s | `GET /api/v2/ping` | 204 | 0 ms |  | IP only |
| 10:21:37 | +2s | `GET /.well-known/terraform.json` | 200 | 1 ms |  | IP only |
| 10:21:37 | +0s | `GET /api/v2/ping` | 204 | 0 ms |  | IP only |
| 10:22:43 | +1m 06s | `GET /.well-known/terraform.json` | 200 | 2 ms |  | IP only |
| 10:22:43 | +0s | `GET /api/v2/ping` | 204 | 1 ms |  | IP only |
| 10:22:43 | +0s | `GET /api/v2/organizations/test/entitlement-set` | 200 | 9 ms |  | token |
| 10:22:43 | +0s | `GET /api/v2/organizations/test/workspaces/test` | 200 | 24 ms |  | token |
| 10:22:43 | +0s | `POST /api/v2/workspaces/ws-QgMV89wqE8yGSRMF/configuration-versions` | 201 | 35 ms | `configuration_version create cv-XYTRACo6hC22cKiP` | token |
| 10:22:43 | +0s | `PUT /api/internal/archivist/callback` | 200 | 11 ms | `configuration_version uploaded cv-XYTRACo6hC22cKiP` | config version audit |
| 10:22:44 | +1s | `GET /api/v2/configuration-versions/cv-XYTRACo6hC22cKiP` | 200 | 15 ms | `configuration_version read cv-XYTRACo6hC22cKiP` | token |
| 10:22:44 | +0s | `POST /api/v2/runs` | 201 | 139 ms | `run create run-fSmjR4Ge3PnNB3dd` | token |

- **First call to run create:** 1m 25s (10:21:19 to 10:22:44)
- **Configuration version:** `cv-XYTRACo6hC22cKiP` - **unconfirmed (matched by user and time only)**; no archivist download followed the agent's download line
- **Upload to archivist:** started 10:22:43.731, TFE callback done after 122 ms
- **Warning:** 3 other run(s) were created with this token in the last 15 min: `run-y1f3q8PYMqh9pKnk` at 10:13:34, `run-uwRbGjuLbx1w7dCw` at 10:14:53, `run-3RzuH6NgPouVHUYC` at 10:21:19. Calls before the latest of them are not listed.

## Run state changes

| State entered | Time (UTC) | Time in that state |
|---|---|---|
| `create` | 10:22:44 | 0s |
| `queue` | 10:22:44 | 3s |
| `planning` | 10:22:47 | 6m 13s |
| `errored` | 10:29:00 | (last seen) |

## Agent time per stage

| Stage | First agent event | Last agent event | Duration |
|---|---|---|---|
| Plan | 10:22:46.977 | 10:23:00.603 | 13.6s |

## Timeline

All times UTC. _Elapsed_ is counted from run create. _Step took_ is the time until the next agent event of the same stage.

| Time | Elapsed | Step took | Source | Event |
|---|---|---|---|---|
| 10:22:44 | 0s |  | run state | create |
| 10:22:44 | 0s |  | run state | queue |
| 10:22:44.521 | 0.5s |  | task-worker (Plan) | task-worker POST /v1/task/invoke -> HTTP 201 (618.334µs) |
| 10:22:46.977 | 3.0s | 0.0s | agent (Plan) | agent: Starting: agent_version=1.33.3 os=linux arch=arm64 |
| 10:22:46.984 | 3.0s | 0.1s | agent (Plan) | core: Starting: version=1.33.3 |
| 10:22:47 | 3s |  | audit (Plan) | agent dequeue agent-dEBjc2ZpWxnsX3BK |
| 10:22:47 | 3s |  | run state | planning |
| 10:22:47.131 | 3.1s | 0s | agent (Plan) | core: Agent registered successfully with HCP Terraform: agent_id=agent-dEBjc2ZpWxnsX3BK agent_pool_id=apool-CT6zqa4Q4xmVrUVR |
| 10:22:47.131 | 3.1s | 0.3s | agent (Plan) | core: Waiting for next job |
| 10:22:47.392 | 3.4s | 0s | agent (Plan) | core: Job received: job_type=plan job_id=run-fSmjR4Ge3PnNB3dd |
| 10:22:47.392 | 3.4s | 0.7s | agent (Plan) | terraform: Handling run: run_id=run-fSmjR4Ge3PnNB3dd run_operation=plan organization_name=test workspace_name=test |
| 10:22:48.109 | 4.1s | 0.3s | agent (Plan) | terraform: Extracting Terraform from release archive |
| 10:22:48.446 | 4.4s | 0s | agent (Plan) | terraform: Downloading Terraform configuration |
| 10:22:48.446 | 4.4s | 0.1s | agent (Plan) | terraform: Terraform CLI details: version=1.16.6 |
| 10:22:48.514 | 4.5s | 0.0s | agent (Plan) | terraform: Executing hook: hook=pre-plan |
| 10:22:48.515 | 4.5s | 2.1s | agent (Plan) | terraform: Running terraform init |
| 10:22:50.635 | 6.6s | 0s | agent (Plan) | terraform: Checking for eol module versions |
| 10:22:50.635 | 6.6s | 0.0s | agent (Plan) | terraform: Registry artifact usage control feature flag is disabled, skipping approval check |
| 10:22:50.649 | 6.6s | 10.0s | agent (Plan) | terraform: Running terraform plan |
| 10:23:00.602 | 16.6s | 0s | agent (Plan) | Received interrupt, shutting down |
| 10:23:00.602 | 16.6s | 0s | agent (Plan) | agent: Core plugin is shutting down |
| 10:23:00.602 | 16.6s | 0.0s | agent (Plan) | agent: Shutting down |
| 10:23:00.603 | 16.6s |  | agent (Plan) | Graceful shutdown may be aborted after 1s |
| 10:29:00 | 6m 16s |  | run state | errored |

## TFE API calls for this run

Response times as logged by atlas (view/db are part of the total). Sorted by slowest call.

| Request | Calls | Avg | Max | Max DB | Status |
|---|---|---|---|---|---|
| `GET /api/v2/runs/:run` | 46 | 42 ms | 54 ms | 12 ms | 200 |
| `GET /api/v2/runs/:run/run-events` | 40 | 15 ms | 28 ms | 22 ms | 200 |
| `GET /api/v2/runs/:run/task-stages` | 3 | 11 ms | 11 ms | 3 ms | 200 |
| `GET /api/v2/runs/:run/policy-checks` | 3 | 11 ms | 11 ms | 3 ms | 200 |

## Log reads (archivist / nginx)

Someone or something reading the plan/apply log while the run was active or afterwards.

| Source | What | Count | First | Last |
|---|---|---|---|---|
| archivist | plan log read | 60 | 2026-11-02 10:22:45.671 | 2026-11-02 10:31:49.939 |
| archivist | apply log read | 62 | 2026-11-02 10:23:49.591 | 2026-11-02 10:36:09.605 |
| nginx | log object fetch | 27 | 2026-11-02 10:23:51 | 2026-11-02 10:31:50 |

_Generated by run_timing.sh from 434 unique log lines._
