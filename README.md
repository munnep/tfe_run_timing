# run_timing.sh

Build a timing report for one Terraform Enterprise (TFE) run from the TFE log files.

Give the script a run ID and the logs. It prints a markdown report that shows what happened during the run, when it happened and how long each part took. It also covers the steps before the run existed: the CLI, VCS webhook or API client creating and uploading the configuration version. It is meant for performance investigations ("why did this run take 17 minutes?") and support tickets.

- One bash script, no dependencies besides standard tools: `bash`, `grep`, `sed`, `awk`, `sort`.
- Read-only. It never changes the logs. Temporary files are removed on exit.

## Quick start

```bash
chmod +x run_timing.sh

# point it at the directory with the TFE logs (searched recursively)
./run_timing.sh run-XXXXXXXXXXXXXXXX /path/to/terraform-enterprise > report.md
```

Open `report.md` in any markdown viewer. The report is plain text with tables, so it can also go straight into a ticket.

## Usage

```
./run_timing.sh [-w MINUTES] <run-id> [file-or-dir ...]   > report.md
grep run-XXXX * | ./run_timing.sh run-XXXX                > report.md
```

| Argument | Meaning |
|---|---|
| `<run-id>` | The run to report on, for example `run-t6DczdVMuJUimqDR`. Required. |
| `file-or-dir ...` | Log files and/or directories. Directories are searched in all subdirectories. With no argument and a terminal on stdin, the current directory is searched. |
| `-w MINUTES` | How far back to look for the steps before the run was created. Default 15. Whole number greater than 0. |
| `-h`, `--help` | Show the usage text. |

The report goes to stdout. Errors and warnings go to stderr.

### Input

| Input | Run timeline | "Before the run was created" |
|---|---|---|
| Log files or a directory (recommended) | Yes | Yes |
| Piped, pre-grepped lines (`grep run-XXXX * \| ...`) | Yes | No, the section says why |

The steps before the run was created contain no run ID, so the script has to search the original logs for them. Pass the files or directory, not grep output, to get that section.

Only text logs are read. Compressed files such as `.log.gz` are not decompressed, so unpack rotated logs first. Markdown and shell files (`*.md`, `*.sh`) are skipped, so the report and the script can sit in the same directory.

## Which logs it uses

Normal TFE log files, as found under `/var/log/terraform-enterprise` or in a support bundle:

| Log | What the script takes from it |
|---|---|
| `atlas.log` | Audit log (run state changes, configuration versions), API request lines with duration and DB time |
| `sidekiq.log`, `sidekiq-critical.log` | Audit log entries written by background jobs (for example the run being queued) |
| `task-worker.log` | The agent's steps: init, plan, apply, policy check and so on |
| `archivist.log` | Configuration upload and download, plan/apply log reads |
| `nginx.log` | Access log, used for error responses and log reads |

You do not need all of them, but the more you give it the more complete the report is. If a log is missing, the matching part of the report is empty or says why.

## What the report contains

All times are UTC, as written in the logs.

1. **Header table**: organization, project, workspace, who created the run, plan and apply IDs, Terraform version, agent version and agent pool.
2. **Summary**: the final state, the total time, the time before the run, the policy check duration and the three longest agent steps with their share of the run.
3. **Before the run was created**: the calls leading up to the run. See below.
4. **Run state changes**: each state the run entered (`queue`, `planning`, `planned`, `confirmed`, `applying`, `applied` ...) and how long it stayed there.
5. **Agent time per stage**: first and last agent event, and the duration, for Plan and Apply.
6. **Timeline**: every event in order, with the elapsed time since run create and, for agent steps, how long that step took (the time until the next agent event of the same stage).
7. **TFE API calls for this run**: the API calls that mention the run ID, with count, average, maximum and maximum DB time, slowest first.
8. **Responses with status 400 or higher**: errors seen in atlas and nginx.
9. **Log reads**: plan/apply log fetches through archivist and nginx, which shows whether someone was watching the run.

### How to read it

- **Start with the Summary.** It shows where the time went. A single step that takes most of the run, such as `Running terraform apply` at 89%, is the finding.
- **Elapsed** in the timeline is counted from run create. **Step took** is the time from that agent line to the next agent line of the same stage. A large value on a line means that step was slow. The line itself is only the start marker.
- **Time in that state** in the state table shows waiting. A long `queue`, `pending` or `planned` with no agent activity means the run was waiting for an agent, an approval or a user, not working.
- **Agent time per stage** compares Plan and Apply directly. Remember that init, plugin download and "Extracting Terraform from release archive" are part of the stage.
- **Audit and atlas lines are whole seconds.** Treat durations from them as plus or minus 1 second. Agent and archivist lines have millisecond precision.

### What the logs cannot tell you

The agent logs `Running terraform apply` (or `plan`) as one step. The output of terraform itself, such as resources being created and "Still creating...", is not in the TFE log files. It is stored as the plan/apply log of the run. If one step takes most of the time, get that log from the UI or from `GET /api/v2/applies/<apply-id>/log` (`/plans/<plan-id>/log` for the plan) to see which resource or provider was slow.

## Before the run was created

The calls before a run exists carry no run ID, so the script finds them in a second pass over the original logs. How a run starts decides what is shown. The script detects the type itself:

| Type | How it is recognised | What is shown |
|---|---|---|
| **CLI / API client creating the run** (`terraform apply`, go-tfe, ...) | The run has a run-create audit event | The calls of the same API token from up to `-w` minutes earlier up to `POST /api/v2/runs`: service discovery, ping, workspace lookup, configuration version create and upload, run create |
| **API-driven** (client creates and uploads a configuration version, TFE creates the run) | No run-create event; the run's configuration version was created by an API request | Same listing for the token that created the configuration version, ending when TFE queues the run |
| **VCS-driven** (webhook) | No run-create event; the run's configuration version was created by a background job | The webhook received, the configuration version create, the `vcs-ingress` agent job that clones the repository, the upload to archivist and the moment the run was queued |

How the steps are matched to the run:

1. **Configuration version link (confirmed).** The agent logs `Downloading Terraform configuration` for the run. Within 0.5 seconds the archivist logs `Starting download request` for a configuration version. That is the one this run used. This is the only evidence in the logs that ties a configuration version to a run ID, and the report prints **confirmed** when it finds it. Otherwise it prints **unconfirmed (matched by user and time only)** and tells you why.
2. **Token and time.** For CLI and API runs the calls are those of the API token that made the run-create or configuration-version request, inside the window. The user agent is shown for information but is never used for matching, because it differs per client and run.
3. **Window cut.** The window stops at the previous run (CLI) or configuration version (API) created by the same token, so calls of an earlier run are not mixed in. If more than one was created inside the window the report shows a warning.
4. **Calls without a token.** `/.well-known/terraform.json` and `/api/v2/ping` have no token. They are included only from the same IP and only up to 5 seconds before the first token call. They are marked "IP only".
5. **Webhook (VCS).** No log line holds both the webhook and the configuration version. The webhook is the last one received up to 5 seconds before the configuration version was created, and the report says it is matched by time only. Other webhooks in the window are listed as a warning.

The "Matched by" column in the CLI and API table shows for each row whether it was matched by `token`, by `config version audit` (the archivist callback of the same configuration version) or `IP only`.

If the section cannot be built, it says "Not available" and gives the reason, for example a missing agent log or input from a pipe. The rest of the report is not affected.

## Example reports

The [`example_reports/`](example_reports/) directory has full reports, one for each way a run can start. They were made with this script from the logs of a test system. Open them next to the explanation in [Before the run was created](#before-the-run-was-created) to see what each type looks like.

| File | Run started by | What is special about "Before the run was created" |
|---|---|---|
| [`cli-driven.md`](example_reports/cli-driven.md) | The Terraform CLI (`terraform plan`/`apply`) | A table of the token's calls up to `POST /api/v2/runs`: service discovery, ping, workspace lookup, configuration version create and upload, run create. Configuration version **confirmed**. |
| [`api-driven.md`](example_reports/api-driven.md) | An API client that creates and uploads a configuration version, after which TFE creates the run | The same table for the token that created the configuration version, ending with the row `TFE queues the run`. There is no run-create request. |
| [`vcs-driven.md`](example_reports/vcs-driven.md) | A push to the connected repository (webhook) | Steps instead of API calls: webhook received, configuration version created, the `vcs-ingress` agent job cloning the repository, the upload and the run queued. The webhook is matched by time only. |

The other sections (summary, state changes, agent time per stage, timeline, API calls, errors and log reads) have the same layout in all three.

### Short example

A trimmed report for a CLI run (values are from a test system):

```
## Summary

- Final run state seen: `applied` at 09:07:43
- Total, run create to last run-state/agent event (09:07:43.450): 2m 31s
- Before the run was created: 2s from first call (09:05:10) to run create, 8 calls; configuration version `cv-UbuaEEjeaVrZKZwr` confirmed
- Total, first call before the run to last run-state/agent event: 2m 33s
- Longest agent steps:
  1. 2m 01s - `terraform: Running terraform plan` (Plan), 80% of the run
  2. 7.1s - `terraform: Running terraform init` (Plan), 5% of the run

## Before the run was created

| Time (UTC) | Gap | Request | Status | Took | Audit event | Matched by |
|---|---|---|---|---|---|---|
| 09:05:10 |  | `GET /.well-known/terraform.json` | 200 | 5 ms |  | IP only |
| 09:05:11 | +1s | `GET /api/v2/ping` | 204 | 1 ms |  | IP only |
| 09:05:11 | +0s | `POST /api/v2/workspaces/ws-.../configuration-versions` | 201 | 67 ms | `configuration_version create cv-...` | token |
| 09:05:12 | +1s | `POST /api/v2/runs` | 201 | 325 ms | `run create run-...` | token |
```

## Limitations

- It reports what is in the logs. Anything TFE does not log, such as the content of the terraform plan/apply output, is not in the report.
- Matching by token and time is strong but not proof. Only the configuration version link is proof, which is why the report says confirmed or unconfirmed.
- If the same token is used by several clients at the same moment, their calls can end up in the same window. The warning lists other runs or configuration versions created by that token.
- Runs without an API token (for example created from the UI with a session) cannot be matched to earlier calls. The section says so.
- Several log files with the same name in the input (for example copies of a backup) can add duplicate lines. The script removes exact duplicates, but give it one set of logs per run.

## Troubleshooting

| Message | Cause |
|---|---|
| `error: no lines containing 'run-...' were found` | The run ID is not in the given files, or the logs are compressed. Check the ID and unpack `.gz` files. |
| `error: -w needs a whole number of minutes` | `-w` must be a positive integer. |
| `Not available: ... read from stdin` | The pre-run section needs files or a directory, not piped input. |
| `Not available: ... agent line "Downloading Terraform configuration" ... not in the logs` | `task-worker.log` is missing or does not cover the run. |
| `warning: '...' does not look like a run ID` | The first argument should look like `run-` followed by 16 characters. |
