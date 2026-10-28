# Run timing: `run-JHvJy2WYYZ1NAJdV`

| Item | Value |
|---|---|
| Organization | `test` |
| Project | `Default Project` |
| Workspace | `test3` |
| Plan ID | `plan-JXdSyWMPyqVoFNSk` |
| Apply ID | `apply-UqvnjqFz76y2m5Jw` |
| Terraform CLI | `1.16.6` |
| Agent version | `1.33.3` |
| Agent pool | `apool-CT6zqa4Q4xmVrUVR` |

## Summary

- **Final run state seen:** `applied` at 10:24:11
- **Before the run was created (API-driven):** 1s from first call (10:23:42) to run queued, 3 calls; configuration version `cv-HQbR2CYhptJLCBmJ` **confirmed**
- **Total, first call before the run to last run-state/agent event:** 29.2s
- **Longest agent steps:**
  1. 1.3s - `terraform: Running terraform init` (Apply)
  2. 1.3s - `terraform: Running terraform init` (Plan)
  3. 1.0s - `terraform: Generating and uploading provider schemas JSON` (Plan)

## Before the run was created

API-driven workflow: there is no run-create request. The client created and uploaded a configuration version and TFE then created and queued the run itself. Calls by `admin` (token `at-cDjTpMLTRJsd4a2v`, IP `62.45.32.200`, user agent `python-requests/2.34.2`; the user agent is not used for matching) up to the moment TFE queued the run. Window: last 15 min. Atlas logs whole seconds, so gaps are +/- 1s.

| Time (UTC) | Gap | Request | Status | Took | Audit event | Matched by |
|---|---|---|---|---|---|---|
| 10:23:42 |  | `GET /api/v2/organizations/test/workspaces/test3` | 200 | 180 ms |  | token |
| 10:23:42 | +0s | `POST /api/v2/workspaces/ws-B5uifJJJKNis8SNm/configuration-versions` | 201 | 108 ms | `configuration_version create cv-HQbR2CYhptJLCBmJ` | token |
| 10:23:43 | +1s | `PUT /api/internal/archivist/callback` | 200 | 336 ms | `configuration_version uploaded cv-HQbR2CYhptJLCBmJ` | config version audit |
| 10:23:43 | +0s | (TFE queues the run) | | | `run queue run-JHvJy2WYYZ1NAJdV` | audit |

- **First call to run queued:** 1s (10:23:42 to 10:23:43)
- **Configuration version:** `cv-HQbR2CYhptJLCBmJ` - **confirmed**; agent "Downloading Terraform configuration" at 10:23:46.500, archivist "Starting download request" for cv-HQbR2CYhptJLCBmJ 35 ms later
- **Upload to archivist:** started 10:23:43.162, TFE callback done after 505 ms

## Run state changes

| State entered | Time (UTC) | Time in that state |
|---|---|---|
| `queue` | 10:23:43 | 2s |
| `planning` | 10:23:45 | 4s |
| `planned` | 10:23:49 | 15s |
| `apply` | 10:24:04 | 0s |
| `confirmed` | 10:24:04 | 0s |
| `queue` | 10:24:04 | 2s |
| `applying` | 10:24:06 | 5s |
| `applied` | 10:24:11 | (last seen) |

## Agent time per stage

| Stage | First agent event | Last agent event | Duration |
|---|---|---|---|
| Plan | 10:23:44.703 | 10:23:50.170 | 5.5s |
| Apply | 10:24:06.373 | 10:24:11.217 | 4.8s |

## Timeline

All times UTC. _Elapsed_ is counted from the first event. _Step took_ is the time until the next agent event of the same stage.

| Time | Elapsed | Step took | Source | Event |
|---|---|---|---|---|
| 10:23:43 | 0s |  | run state | queue |
| 10:23:43.974 | 1.0s |  | task-worker (Plan) | task-worker POST /v1/task/invoke -> HTTP 201 (3.092217ms) |
| 10:23:44.703 | 1.7s | 0.0s | agent (Plan) | agent: Starting: agent_version=1.33.3 os=linux arch=arm64 |
| 10:23:44.727 | 1.7s | 0.2s | agent (Plan) | core: Starting: version=1.33.3 |
| 10:23:44.912 | 1.9s | 0.0s | agent (Plan) | core: Agent registered successfully with HCP Terraform: agent_id=agent-jiXGBmNwRxC445vu agent_pool_id=apool-CT6zqa4Q4xmVrUVR |
| 10:23:44.915 | 1.9s | 0.5s | agent (Plan) | core: Waiting for next job |
| 10:23:45 | 2s |  | audit (Plan) | agent dequeue agent-jiXGBmNwRxC445vu |
| 10:23:45 | 2s |  | run state | planning |
| 10:23:45.395 | 2.4s | 0.0s | agent (Plan) | core: Job received: job_type=plan job_id=run-JHvJy2WYYZ1NAJdV |
| 10:23:45.396 | 2.4s | 0.6s | agent (Plan) | terraform: Handling run: run_id=run-JHvJy2WYYZ1NAJdV run_operation=plan organization_name=test workspace_name=test3 |
| 10:23:45.979 | 3.0s | 0.5s | agent (Plan) | terraform: Extracting Terraform from release archive |
| 10:23:46.498 | 3.5s | 0s | agent (Plan) | terraform: Downloading Terraform configuration |
| 10:23:46.498 | 3.5s | 0.1s | agent (Plan) | terraform: Terraform CLI details: version=1.16.6 |
| 10:23:46.564 | 3.6s | 0.0s | agent (Plan) | terraform: Executing hook: hook=pre-plan |
| 10:23:46.569 | 3.6s | 1.3s | agent (Plan) | terraform: Running terraform init |
| 10:23:47.822 | 4.8s | 0s | agent (Plan) | terraform: Checking for eol module versions |
| 10:23:47.822 | 4.8s | 0.0s | agent (Plan) | terraform: Registry artifact usage control feature flag is disabled, skipping approval check |
| 10:23:47.848 | 4.8s | 0.6s | agent (Plan) | terraform: Running terraform plan |
| 10:23:48.458 | 5.5s | 0.1s | agent (Plan) | terraform: Generating and uploading plan JSON |
| 10:23:48.580 | 5.6s | 1.0s | agent (Plan) | terraform: Generating and uploading provider schemas JSON |
| 10:23:49 | 6s |  | run state | planned |
| 10:23:49.579 | 6.6s | 0.1s | agent (Plan) | terraform: Generating and uploading redacted plan JSON |
| 10:23:49.677 | 6.7s | 0.0s | agent (Plan) | terraform: Persisting filesystem to remote storage |
| 10:23:49.727 | 6.7s | 0.1s | agent (Plan) | terraform: Executing hook: hook=post-plan |
| 10:23:49.862 | 6.9s | 0.2s | agent (Plan) | terraform: Finished handling run |
| 10:23:50.069 | 7.1s | 0s | agent (Plan) | agent: Core plugin is shutting down |
| 10:23:50.069 | 7.1s | 0.1s | agent (Plan) | agent: Shutting down |
| 10:23:50.164 | 7.2s | 0.0s | agent (Plan) | core: Shutdown complete |
| 10:23:50.170 | 7.2s | 0s | agent (Plan) | Graceful shutdown complete |
| 10:23:50.170 | 7.2s |  | agent (Plan) | plugin: plugin process exited: plugin=/home/tfc-agent/bin/tfc-agent-core id=11 |
| 10:24:04 | 21s |  | run state | apply |
| 10:24:04 | 21s |  | run state | confirmed |
| 10:24:04 | 21s |  | run state | queue |
| 10:24:04.532 | 21.5s |  | task-worker (Apply) | task-worker POST /v1/task/invoke -> HTTP 201 (1.338379ms) |
| 10:24:06 | 23s |  | audit (Apply) | agent dequeue agent-aYhqNYnC8AmSB3jG |
| 10:24:06 | 23s |  | run state | applying |
| 10:24:06.373 | 23.4s | 0.0s | agent (Apply) | agent: Starting: agent_version=1.33.3 os=linux arch=arm64 |
| 10:24:06.395 | 23.4s | 0.2s | agent (Apply) | core: Starting: version=1.33.3 |
| 10:24:06.550 | 23.5s | 0.0s | agent (Apply) | core: Agent registered successfully with HCP Terraform: agent_id=agent-aYhqNYnC8AmSB3jG agent_pool_id=apool-CT6zqa4Q4xmVrUVR |
| 10:24:06.553 | 23.6s | 0.7s | agent (Apply) | core: Waiting for next job |
| 10:24:07.204 | 24.2s | 0s | agent (Apply) | core: Job received: job_type=apply job_id=run-JHvJy2WYYZ1NAJdV |
| 10:24:07.204 | 24.2s | 0.5s | agent (Apply) | terraform: Handling run: run_id=run-JHvJy2WYYZ1NAJdV run_operation=apply organization_name=test workspace_name=test3 |
| 10:24:07.744 | 24.7s | 0.5s | agent (Apply) | terraform: Extracting Terraform from release archive |
| 10:24:08.208 | 25.2s | 0s | agent (Apply) | terraform: Restoring filesystem from remote storage |
| 10:24:08.208 | 25.2s | 0.1s | agent (Apply) | terraform: Terraform CLI details: version=1.16.6 |
| 10:24:08.262 | 25.3s | 0.0s | agent (Apply) | terraform: Executing hook: hook=pre-apply |
| 10:24:08.270 | 25.3s | 1.3s | agent (Apply) | terraform: Running terraform init |
| 10:24:09.546 | 26.5s | 0.0s | agent (Apply) | terraform: Checking for eol module versions |
| 10:24:09.565 | 26.6s | 0.9s | agent (Apply) | terraform: Running terraform apply |
| 10:24:10.513 | 27.5s | 0.1s | agent (Apply) | terraform: Creating workspace modules |
| 10:24:10.653 | 27.7s | 0s | agent (Apply) | terraform: Uploading files required for instrumenting module/provider dependencies |
| 10:24:10.653 | 27.7s | 0.1s | agent (Apply) | terraform: file for runtime report was not found: filename=/home/tfc-agent/.tfc-agent/component/terraform/runs/run-JHvJy2WYYZ1NAJdV/config/.terraform/modules/modules.json |
| 10:24:10.726 | 27.7s | 0.2s | agent (Apply) | terraform: Executing hook: hook=post-apply |
| 10:24:10.886 | 27.9s | 0.3s | agent (Apply) | terraform: Finished handling run |
| 10:24:11 | 28s |  | run state | applied |
| 10:24:11.142 | 28.1s | 0s | agent (Apply) | agent: Core plugin is shutting down |
| 10:24:11.142 | 28.1s | 0.1s | agent (Apply) | agent: Shutting down |
| 10:24:11.210 | 28.2s | 0.0s | agent (Apply) | core: Shutdown complete |
| 10:24:11.216 | 28.2s | 0.0s | agent (Apply) | plugin: plugin process exited: plugin=/home/tfc-agent/bin/tfc-agent-core id=12 |
| 10:24:11.217 | 28.2s |  | agent (Apply) | Graceful shutdown complete |

## TFE API calls for this run

Response times as logged by atlas (view/db are part of the total). Sorted by slowest call.

| Request | Calls | Avg | Max | Max DB | Status |
|---|---|---|---|---|---|
| `GET /api/v2/runs/:run` | 4 | 127 ms | 217 ms | 32 ms | 200 |
| `GET /api/v2/runs/:run/plan` | 1 | 99 ms | 99 ms | 17 ms | 200 |
| `GET /api/v2/runs/:run/run-events` | 4 | 63 ms | 87 ms | 14 ms | 200 |
| `POST /api/v2/runs/:run/actions/apply` | 1 | 69 ms | 69 ms | 14 ms | 202 |
| `GET /api/v2/runs/:run/task-stages` | 1 | 62 ms | 62 ms | 8 ms | 200 |
| `GET /api/v2/runs/:run/policy-checks` | 2 | 32 ms | 36 ms | 7 ms | 200 |
| `POST /api/v2/runs/:run/modules` | 1 | 30 ms | 30 ms | 4 ms | 201 |

## Log reads (archivist / nginx)

Someone or something reading the plan/apply log while the run was active or afterwards.

| Source | What | Count | First | Last |
|---|---|---|---|---|
| archivist | apply log read | 11 | 2026-10-28 10:23:51.301 | 2026-10-28 10:24:11.129 |
| archivist | plan log read | 4 | 2026-10-28 10:23:51.429 | 2026-10-28 10:24:05.865 |
| nginx | log object fetch | 1 | 2026-10-28 10:24:00 | 2026-10-28 10:24:00 |

_Generated by run_timing.sh from 112 unique log lines._
