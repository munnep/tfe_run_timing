# Run summary

Logs read: 17 file(s), 19434 lines, from 2026-11-02 09:26:16 to 2026-11-02 10:38:40 (UTC).

## Summary

- **Runs with a lifecycle in the logs:** 14

| Status | Runs | % |
|---|---|---|
| applied | 3 | 21.4% |
| errored | 1 | 7.1% |
| plan only (speculative) | 7 | 50.0% |
| planned (waiting for confirmation) | 1 | 7.1% |
| planning (running) | 1 | 7.1% |
| pending (waiting for a previous run or its approval) | 1 | 7.1% |
| **Total** | **14** | **100%** |

## By workflow

| Workflow | Runs | % | applied | errored | plan only | planned | planning | pending |
|---|---|---|---|---|---|---|---|---|
| CLI | 9 | 64.3% | 1 | 1 | 6 | 0 | 1 | 0 |
| API-driven | 1 | 7.1% | 1 | 0 | 0 | 0 | 0 | 0 |
| VCS | 4 | 28.6% | 1 | 0 | 1 | 1 | 0 | 1 |
| **Total** | **14** | **100%** | **3** | **1** | **7** | **1** | **1** | **1** |

Each column is a run status. The workflow is how the run was started: `CLI` = terraform CLI, `VCS` = push or pull request on the connected repository, `API-driven` = an API client uploaded the configuration and TFE created the run, `UI` = started in the web UI.

## Runs

Sorted by the first event. All times UTC. Audit events have whole-second times. For the details of one run use `run_timing.sh <run-id>`.

| Run | Workflow | Workspace | Status | First event | Last event | Duration | Evidence |
|---|---|---|---|---|---|---|---|
| `run-xRZtK5rALE92o2Vd` | VCS | null_resource | applied | 10:04:22 | 10:04:44 | 22s |  |
| `run-npC7321gp2fAqPJR` | VCS | null_resource | plan only (speculative) | 10:08:43 | 10:08:50 | 7s |  |
| `run-8nnNBdkDr7Kg9onE` | VCS | null_resource | planned (waiting for confirmation) | 10:09:36 | 10:09:43 | - | no later event; last event 10:09:43, last log line 10:38:40 (28m 57s later); waiting for a confirm or discard; blocks the pending run `run-UCp6LZHrGY6Qco4D` |
| `run-UCp6LZHrGY6Qco4D` | VCS | null_resource | pending (waiting for a previous run or its approval) | 10:11:57 | 10:11:57 | - | configuration version `cv-CN13y3NamuFRECxV` uploaded at 10:11:57 by a webhook, but no run was queued after it; the workspace is blocked by `run-8nnNBdkDr7Kg9onE` (planned) |
| `run-y1f3q8PYMqh9pKnk` | CLI | test | plan only (speculative) | 10:13:34 | 10:13:46 | 12s |  |
| `run-uwRbGjuLbx1w7dCw` | CLI | test | plan only (speculative) | 10:14:53 | 10:15:04 | 11s |  |
| `run-3RzuH6NgPouVHUYC` | CLI | test | applied | 10:21:19 | 10:21:40 | 21s |  |
| `run-fSmjR4Ge3PnNB3dd` | CLI | test | errored | 10:22:44 | 10:29:00 | 6m 16s | agent interrupted at 10:23:00 (task-worker), run errored at 10:29:00, 6m 00s later |
| `run-579DHY1cXahXBrL4` | API-driven | test3 | applied | 10:30:05 | 10:30:47 | 42s |  |
| `run-4S3jvfd3EaCSNGVz` | CLI | test | plan only (speculative) | 10:31:19 | 10:32:25 | 1m 06s |  |
| `run-TWV4rccxfEXzBbsU` | CLI | test | plan only (speculative) | 10:32:38 | 10:33:45 | 1m 07s |  |
| `run-GvJVJtZwPC8twz1Q` | CLI | test | plan only (speculative) | 10:35:02 | 10:36:10 | 1m 08s |  |
| `run-4EAe3ioe7CvDdown` | CLI | test | plan only (speculative) | 10:35:33 | 10:35:45 | 12s |  |
| `run-Zw2QPeVLYxRh6Ac2` | CLI | test | planning (running) | 10:36:03 | 10:36:05 | - | no later event; last event 10:36:05, last log line 10:38:40 (2m 35s later) |

## Run IDs without a status

These IDs have no create or queue event in the logs, so they are not counted as runs. They are runs from before the logs start, or runs that were only viewed or polled.

| Run | Lines in the logs | Page requests |
|---|---|---|
| `run-VWRc4oK6zNEo847s` | 46 | 2 |
| `run-Yn7hF28bzifJ3snT` | 38 | 1 |
| `run-JHvJy2WYYZ1NAJdV` | 13 | 1 |
| `run-jAF3wQTsUDEZxhNU` | 17 | 0 |
| `run-t6DczdVMuJUimqDR` | 26 | 0 |
| `run-oPfjCrho2rgLgPhB` | 26 | 0 |
| `run-Ks9M6r1awvy4dAem` | 26 | 0 |

## Runs that need attention

Errored, canceled or discarded runs, and runs that are still waiting or running. Errored runs come first.

- `run-fSmjR4Ge3PnNB3dd` is errored: agent interrupted at 10:23:00 (task-worker), run errored at 10:29:00, 6m 00s later
- `run-8nnNBdkDr7Kg9onE` is planned (waiting for confirmation): no later event; last event 10:09:43, last log line 10:38:40 (28m 57s later); waiting for a confirm or discard; blocks the pending run `run-UCp6LZHrGY6Qco4D`
- `run-Zw2QPeVLYxRh6Ac2` is planning (running): no later event; last event 10:36:05, last log line 10:38:40 (2m 35s later)
- `run-UCp6LZHrGY6Qco4D` is pending (waiting for a previous run or its approval): configuration version `cv-CN13y3NamuFRECxV` uploaded at 10:11:57 by a webhook, but no run was queued after it; the workspace is blocked by `run-8nnNBdkDr7Kg9onE` (planned)

## Other observations

- Configuration version `cv-vSXNtmPJNLjM38Ss` errored at 10:03:17: fatal: Authentication failed for 'https://github.com/munnep/null_resource.git/'. Configuration versions are not counted as runs.

_Status is derived from the run audit events (atlas, sidekiq, sidekiq-critical). The workflow is the user agent of the run-create request (CLI = go-tfe, UI = browser); runs without a create event are VCS when a webhook user changed the state, otherwise API-driven. Only runs that were created are counted (a run create or queue event, or for VCS a webhook configuration version that was uploaded without a run being queued: a pending run waiting behind another run)._

_Generated by run_summary.sh from 2537 unique log lines._
