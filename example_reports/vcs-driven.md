# Run timing: `run-VWRc4oK6zNEo847s`

| Item | Value |
|---|---|
| Organization | `test` |
| Project | `Default Project` |
| Workspace | `null_resource` |
| Plan ID | `plan-MnuuUaLGWmdu3o9g` |
| Apply ID | `apply-D9fcwxfqKhm1vDuY` |
| Terraform CLI | `1.16.6` |
| Agent version | `1.33.3` |
| Agent pool | `apool-CT6zqa4Q4xmVrUVR` |

## Summary

- **Final run state seen:** `applied` at 09:59:10
- **Before the run was created (VCS webhook):** 4s from webhook to run queued; configuration version `cv-qnLiKNH9RjtUvbG5` **confirmed**
- **Total, first call before the run to last run-state/agent event:** 35.1s
- **Longest agent steps:**
  1. 1.6s - `terraform: Running terraform apply` (Apply)
  2. 1.2s - `terraform: Running terraform init` (Plan)
  3. 1.1s - `terraform: Generating and uploading provider schemas JSON` (Plan)

## Before the run was created

VCS workflow: no run-create request exists. A webhook creates a configuration version and TFE queues the run when the agent has cloned and uploaded the repository. Linked through configuration version `cv-qnLiKNH9RjtUvbG5`. Audit events and atlas lines have whole-second times, so gaps are +/- 1s.

| Time (UTC) | Gap | Step | Detail |
|---|---|---|---|
| 09:58:36 |  | Webhook received | `POST /webhooks/vcs/b7a0a33e-9b33-4b18-8741-6c30b65858b0` -> 200, 42 ms, from 140.82.115.47 (GitHub-Hookshot/51d2642) |
| 09:58:36 | +0s | Audit: vcs-repo receive_webhook | event `push`, commit `baa26b50b2`, request `7098c390-2fd2-4b9f-a041-3b7c220a61fb` |
| 09:58:36 | +0s | Audit: configuration_version fetching | `cv-qnLiKNH9RjtUvbG5` |
| 09:58:36 | +0s | Audit: configuration_version create | `cv-qnLiKNH9RjtUvbG5` by `gh-webhooks-test-VXzaV6qOaT` |
| 09:58:36.463 | +0.5s | Agent job vcs-ingress | clone `https://github.com/munnep/null_resource.git`, package and hand over; done 3.5s later |
| 09:58:39.723 | +3.3s | Archivist upload of the configuration | TFE callback done after 494 ms |
| 09:58:40 | +0.3s | Audit: configuration_version uploaded | `cv-qnLiKNH9RjtUvbG5` |
| 09:58:40 | +0s | Audit: run queue | `run-VWRc4oK6zNEo847s` created and queued |

- **Webhook to run queued:** 4s (09:58:36 to 09:58:40)
- **Configuration version:** `cv-qnLiKNH9RjtUvbG5` - **confirmed**; agent "Downloading Terraform configuration" at 09:58:42.597, archivist "Starting download request" for cv-qnLiKNH9RjtUvbG5 21 ms later
- **Webhook:** matched by time only; no log line holds both the webhook and the configuration version, so the push that created it is the last one received within 5s before the create.
- **Warning:** 2 other webhook(s) were received in the last 15 min before the run was queued: `push` at 09:57:00, `ping` at 09:56:06.

## Run state changes

| State entered | Time (UTC) | Time in that state |
|---|---|---|
| `queue` | 09:58:40 | 1s |
| `planning` | 09:58:41 | 5s |
| `planned` | 09:58:46 | 18s |
| `apply` | 09:59:04 | 0s |
| `confirmed` | 09:59:04 | 0s |
| `queue` | 09:59:04 | 2s |
| `applying` | 09:59:06 | 4s |
| `applied` | 09:59:10 | (last seen) |

## Agent time per stage

| Stage | First agent event | Last agent event | Duration |
|---|---|---|---|
| Plan | 09:58:40.822 | 09:58:46.741 | 5.9s |
| Apply | 09:59:05.946 | 09:59:11.093 | 5.1s |

## Timeline

All times UTC. _Elapsed_ is counted from the first event. _Step took_ is the time until the next agent event of the same stage.

| Time | Elapsed | Step took | Source | Event |
|---|---|---|---|---|
| 09:58:40 | 0s |  | run state | queue |
| 09:58:40.381 | 0.4s |  | task-worker (Plan) | task-worker POST /v1/task/invoke -> HTTP 201 (900.085µs) |
| 09:58:40.822 | 0.8s | 0.0s | agent (Plan) | agent: Starting: agent_version=1.33.3 os=linux arch=arm64 |
| 09:58:40.845 | 0.8s | 0.2s | agent (Plan) | core: Starting: version=1.33.3 |
| 09:58:41 | 1s |  | audit (Plan) | agent dequeue agent-UQHktgp1QkYAysPT |
| 09:58:41 | 1s |  | run state | planning |
| 09:58:41.023 | 1.0s | 0.0s | agent (Plan) | core: Agent registered successfully with HCP Terraform: agent_id=agent-UQHktgp1QkYAysPT agent_pool_id=apool-CT6zqa4Q4xmVrUVR |
| 09:58:41.025 | 1.0s | 0.4s | agent (Plan) | core: Waiting for next job |
| 09:58:41.472 | 1.5s | 0.0s | agent (Plan) | core: Job received: job_type=plan job_id=run-VWRc4oK6zNEo847s |
| 09:58:41.473 | 1.5s | 0.6s | agent (Plan) | terraform: Handling run: run_id=run-VWRc4oK6zNEo847s run_operation=plan organization_name=test workspace_name=null_resource |
| 09:58:42.076 | 2.1s | 0.5s | agent (Plan) | terraform: Extracting Terraform from release archive |
| 09:58:42.596 | 2.6s | 0s | agent (Plan) | terraform: Downloading Terraform configuration |
| 09:58:42.596 | 2.6s | 0.0s | agent (Plan) | terraform: Terraform CLI details: version=1.16.6 |
| 09:58:42.642 | 2.6s | 0.0s | agent (Plan) | terraform: Executing hook: hook=pre-plan |
| 09:58:42.646 | 2.6s | 1.2s | agent (Plan) | terraform: Running terraform init |
| 09:58:43.852 | 3.9s | 0s | agent (Plan) | terraform: Checking for eol module versions |
| 09:58:43.852 | 3.9s | 0.0s | agent (Plan) | terraform: Registry artifact usage control feature flag is disabled, skipping approval check |
| 09:58:43.872 | 3.9s | 1.0s | agent (Plan) | terraform: Running terraform plan |
| 09:58:44.830 | 4.8s | 0.1s | agent (Plan) | terraform: Generating and uploading plan JSON |
| 09:58:44.961 | 5.0s | 1.1s | agent (Plan) | terraform: Generating and uploading provider schemas JSON |
| 09:58:46 | 6s |  | run state | planned |
| 09:58:46.084 | 6.1s | 0.0s | agent (Plan) | terraform: Generating and uploading redacted plan JSON |
| 09:58:46.126 | 6.1s | 0.1s | agent (Plan) | terraform: Persisting filesystem to remote storage |
| 09:58:46.222 | 6.2s | 0.2s | agent (Plan) | terraform: Executing hook: hook=post-plan |
| 09:58:46.437 | 6.4s | 0.2s | agent (Plan) | terraform: Finished handling run |
| 09:58:46.684 | 6.7s | 0s | agent (Plan) | agent: Core plugin is shutting down |
| 09:58:46.684 | 6.7s | 0.0s | agent (Plan) | agent: Shutting down |
| 09:58:46.728 | 6.7s | 0.0s | agent (Plan) | core: Shutdown complete |
| 09:58:46.740 | 6.7s | 0.0s | agent (Plan) | plugin: plugin process exited: plugin=/home/tfc-agent/bin/tfc-agent-core id=11 |
| 09:58:46.741 | 6.7s |  | agent (Plan) | Graceful shutdown complete |
| 09:59:04 | 24s |  | run state | apply |
| 09:59:04 | 24s |  | run state | confirmed |
| 09:59:04 | 24s |  | run state | queue |
| 09:59:04.915 | 24.9s |  | task-worker (Apply) | task-worker POST /v1/task/invoke -> HTTP 201 (1.546669ms) |
| 09:59:05.946 | 25.9s | 0.0s | agent (Apply) | agent: Starting: agent_version=1.33.3 os=linux arch=arm64 |
| 09:59:05.968 | 26.0s | 0.1s | agent (Apply) | core: Starting: version=1.33.3 |
| 09:59:06 | 26s |  | audit (Apply) | agent dequeue agent-VPhTLctgv7HnBJcY |
| 09:59:06 | 26s |  | run state | applying |
| 09:59:06.099 | 26.1s | 0.0s | agent (Apply) | core: Agent registered successfully with HCP Terraform: agent_id=agent-VPhTLctgv7HnBJcY agent_pool_id=apool-CT6zqa4Q4xmVrUVR |
| 09:59:06.102 | 26.1s | 0.3s | agent (Apply) | core: Waiting for next job |
| 09:59:06.401 | 26.4s | 0s | agent (Apply) | core: Job received: job_type=apply job_id=run-VWRc4oK6zNEo847s |
| 09:59:06.401 | 26.4s | 0.6s | agent (Apply) | terraform: Handling run: run_id=run-VWRc4oK6zNEo847s run_operation=apply organization_name=test workspace_name=null_resource |
| 09:59:07.008 | 27.0s | 0.5s | agent (Apply) | terraform: Extracting Terraform from release archive |
| 09:59:07.480 | 27.5s | 0s | agent (Apply) | terraform: Restoring filesystem from remote storage |
| 09:59:07.480 | 27.5s | 0.1s | agent (Apply) | terraform: Terraform CLI details: version=1.16.6 |
| 09:59:07.561 | 27.6s | 0.0s | agent (Apply) | terraform: Executing hook: hook=pre-apply |
| 09:59:07.569 | 27.6s | 1.1s | agent (Apply) | terraform: Running terraform init |
| 09:59:08.650 | 28.7s | 0.0s | agent (Apply) | terraform: Checking for eol module versions |
| 09:59:08.677 | 28.7s | 1.6s | agent (Apply) | terraform: Running terraform apply |
| 09:59:10 | 30s |  | run state | applied |
| 09:59:10.237 | 30.2s | 0.2s | agent (Apply) | terraform: Creating workspace modules |
| 09:59:10.449 | 30.4s | 0.0s | agent (Apply) | terraform: Uploading files required for instrumenting module/provider dependencies |
| 09:59:10.450 | 30.5s | 0.1s | agent (Apply) | terraform: file for runtime report was not found: filename=/home/tfc-agent/.tfc-agent/component/terraform/runs/run-VWRc4oK6zNEo847s/config/.terraform/modules/modules.json |
| 09:59:10.545 | 30.5s | 0.2s | agent (Apply) | terraform: Executing hook: hook=post-apply |
| 09:59:10.774 | 30.8s | 0.2s | agent (Apply) | terraform: Finished handling run |
| 09:59:10.976 | 31.0s | 0s | agent (Apply) | agent: Core plugin is shutting down |
| 09:59:10.976 | 31.0s | 0.1s | agent (Apply) | agent: Shutting down |
| 09:59:11.086 | 31.1s | 0.0s | agent (Apply) | core: Shutdown complete |
| 09:59:11.093 | 31.1s | 0s | agent (Apply) | Graceful shutdown complete |
| 09:59:11.093 | 31.1s |  | agent (Apply) | plugin: plugin process exited: plugin=/home/tfc-agent/bin/tfc-agent-core id=11 |

## TFE API calls for this run

Response times as logged by atlas (view/db are part of the total). Sorted by slowest call.

| Request | Calls | Avg | Max | Max DB | Status |
|---|---|---|---|---|---|
| `GET /api/v2/runs/:run` | 9 | 117 ms | 311 ms | 62 ms | 200 |
| `GET /api/v2/runs/:run/run-events` | 32 | 76 ms | 191 ms | 70 ms | 200 |
| `GET /api/v2/runs/:run/policy-checks` | 3 | 47 ms | 92 ms | 7 ms | 200 |
| `POST /api/v2/runs/:run/actions/apply` | 1 | 79 ms | 79 ms | 12 ms | 202 |
| `GET /api/v2/runs/:run/task-stages` | 2 | 39 ms | 46 ms | 10 ms | 200 |
| `POST /api/v2/runs/:run/modules` | 1 | 24 ms | 24 ms | 3 ms | 201 |

## Log reads (archivist / nginx)

Someone or something reading the plan/apply log while the run was active or afterwards.

| Source | What | Count | First | Last |
|---|---|---|---|---|
| archivist | apply log read | 24 | 2026-10-28 09:58:57.604 | 2026-10-28 10:09:39.589 |
| nginx | log object fetch | 3 | 2026-10-28 09:59:01 | 2026-10-28 10:09:12 |
| archivist | plan log read | 9 | 2026-10-28 09:59:01.186 | 2026-10-28 10:09:39.597 |

_Generated by run_timing.sh from 222 unique log lines._
