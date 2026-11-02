#!/usr/bin/env bash
#
# run_summary.sh - summary (markdown) of all Terraform Enterprise runs in a set of log files
#
# Usage:
#   ./run_summary.sh [--full] [file-or-dir ...]   > run_summary.md
#   grep -h run- * | ./run_summary.sh [--full]    > run_summary.md
#
#   (default)  Only the summary: number of runs, runs and percentage per status, and
#              the split per workflow. The size does not depend on the number of runs.
#   --full     Everything: also one row per run, the run IDs without a status, the runs
#              that need attention (errored, waiting, running) and other observations.
#              With thousands of runs this is a long report.
#   -h, --help Show this text.
#
# Input can be raw log files or directories (searched recursively), or pre-grepped
# lines on stdin. With no arguments and a terminal on stdin the current directory
# is searched. Output goes to stdout; times are UTC as found in the logs.
#
# The report shows how many runs there are, how many (and what percentage) ended in
# each status, a split per workflow (CLI / API-driven / VCS / UI) and, with --full, one row per run.
# Use run_timing.sh <run-id> for the timing details of a single run.
#
# How the status is found:
#   The status comes from the run audit events (atlas.log, sidekiq.log and
#   sidekiq-critical.log, all three are needed). Events can have the same second, so
#   the status is taken from WHICH events exist, first match wins:
#     applied > errored > canceled > discarded > finished (plan only) >
#     applying/confirmed > planned > planning > queue/create (queued)
#   Only runs that were created count: a run needs a create or queue event. A run with
#   only a queue event is queued (created, waiting for an agent). Run IDs without any
#   such event (older runs, or runs only viewed or polled) are listed apart with --full
#   and are not counted.
#   One exception, VCS: a run that waits behind another run of the workspace has no queue
#   event, but its webhook configuration version was created and uploaded. An upload with
#   no run queued within about 10 s counts as one pending run (waiting for the previous
#   run of the workspace to be approved or to finish). Page views never create a run.
#
set -u

usage() {
  awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"
  exit "${1:-0}"
}

FULL=0
ARGS=()
while [ $# -gt 0 ]; do          # options may stand anywhere on the command line
  case $1 in
    --full) FULL=1 ;;
    -h|--help) usage 0 ;;
    --) shift; ARGS+=("$@"); break ;;
    -?*) echo "error: unknown option '$1' (try --help)" >&2; exit 1 ;;
    *) ARGS+=("$1") ;;
  esac
  shift
done
set -- ${ARGS[@]+"${ARGS[@]}"}

export LC_ALL=C      # logs can contain non-UTF-8 bytes; BSD awk stops on them otherwise

TMP=$(mktemp -d "${TMPDIR:-/tmp}/run_summary.XXXXXX") || exit 1
trap 'rm -rf "$TMP"' EXIT
TAB=$(printf '\t')

# ---------------------------------------------------------------- collect
# Lines with a run ID, the "POST /api/v2/runs" request lines (user agent), errored
# audit events and git "fatal:" lines (why a configuration version failed).
PAT='run-[A-Za-z0-9]{16}|"path":"/api/v2/runs"|"action":"errored"|[|] fatal:|"resource":"configuration_version","action":"(create|uploaded)"'
STDIN_MODE=0
if [ $# -eq 0 ]; then
  if [ ! -t 0 ]; then
    STDIN_MODE=1
    cat > "$TMP/stdin.txt"          # kept whole: the time span is taken from all lines
    set -- "$TMP/stdin.txt"
  else
    set -- .
  fi
fi
grep -raEh --exclude='*.md' --exclude='*.sh' -e "$PAT" -- "$@" 2>/dev/null | sort -u > "$TMP/raw"

if ! grep -aqE 'run-[A-Za-z0-9]{16}' "$TMP/raw"; then
  echo "error: no run IDs (run-XXXXXXXXXXXXXXXX) were found in the input" >&2
  exit 1
fi

# ---------------------------------------------------------------- awk helpers
cat > "$TMP/lib.awk" <<'AWK'
function grab(s, re) {
  if (match(s, re)) return substr(s, RSTART, RLENGTH)
  return ""
}
function sval(s, key,   r) {
  r = grab(s, "\"" key "\":\"[^\"]*\"")
  if (r == "") return ""
  sub("^\"" key "\":\"", "", r); sub(/"$/, "", r)
  return r
}
# seconds since 1970-01-01 (UTC) for date "YYYY-MM-DD" and time "HH:MM:SS[.fff]"
function epoch(d, t,   a, y, m, dd, hh, mi, ss, era, yoe, doy, doe, days) {
  split(d, a, "-"); y = a[1] + 0; m = a[2] + 0; dd = a[3] + 0
  split(t, a, ":"); hh = a[1] + 0; mi = a[2] + 0; ss = a[3] + 0
  if (m <= 2) y--
  era = int(y / 400); yoe = y - era * 400
  doy = int((153 * (m + (m > 2 ? -3 : 9)) + 2) / 5) + dd - 1
  doe = yoe * 365 + int(yoe / 4) - int(yoe / 100) + doy
  days = era * 146097 + doe - 719468
  return days * 86400 + hh * 3600 + mi * 60 + ss
}
function fmt(x,   sg, r, h, m, s) {
  sg = ""
  if (x < 0) { sg = "-"; x = -x }
  if (x < 60) {
    if (x == int(x)) return sprintf("%s%ds", sg, x)
    return sprintf("%s%.1fs", sg, x)
  }
  r = int(x + 0.5); h = int(r / 3600); m = int((r % 3600) / 60); s = r % 60
  if (h > 0) return sprintf("%s%dh %02dm %02ds", sg, h, m, s)
  return sprintf("%s%dm %02ds", sg, m, s)
}
# "YYYY-MM-DD HH:MM:SS" -> epoch
function ep(str,   a) { split(str, a, " "); return epoch(a[1], a[2]) }
# "2026-11-02T10:22:44.123Z" -> "2026-11-02 10:22:44"
function isostr(ts,   x) { x = substr(ts, 1, 19); sub("T", " ", x); return x }
# time of day of an epoch
function clk(e,   s, h, m) {
  s = e - 86400 * int(e / 86400); h = int(s / 3600); m = int((s % 3600) / 60)
  return sprintf("%02d:%02d:%02d", h, m, s - h * 3600 - m * 60)
}
AWK

# ---------------------------------------------------------------- time span of the logs
# First and last timestamp over ALL lines of the input (not only the run lines), so
# the report can tell how old the last event of a running run is.
cat > "$TMP/span.awk" <<'AWK'
{
  n++
  t = ""
  if (match($0, /^20[0-9][0-9]-[0-9][0-9]-[0-9][0-9][T ][0-9][0-9]:[0-9][0-9]:[0-9][0-9]/)) t = substr($0, RSTART, 19)
  else {
    t = sval($0, "@timestamp")
    if (t == "" && match($0, /^[A-Z]+ 20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]/)) t = substr($0, RSTART + RLENGTH - 19, 19)
  }
  if (t == "") next
  t = isostr(t)
  if (lo == "" || t < lo) lo = t
  if (hi == "" || t > hi) hi = t
}
END { printf "%s\t%s\t%d\n", lo, hi, n }
AWK

if [ "$STDIN_MODE" -eq 1 ]; then
  NFILES="input from stdin"
else
  NFILES="$(find "$@" -type f ! -name '*.md' ! -name '*.sh' 2>/dev/null | wc -l | tr -d ' ') file(s)"
fi
grep -raEh --exclude='*.md' --exclude='*.sh' -e '^' -- "$@" 2>/dev/null \
  | awk -f "$TMP/lib.awk" -f "$TMP/span.awk" > "$TMP/span"
IFS="$TAB" read -r SPAN_FIRST SPAN_LAST SPAN_LINES < "$TMP/span"
: "${SPAN_FIRST:=}"; : "${SPAN_LAST:=}"; : "${SPAN_LINES:=0}"

# ---------------------------------------------------------------- extract and classify
cat > "$TMP/extract.awk" <<'AWK'
function lead(s) {
  return grab(s, "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]")
}
function hasact(id, a) { return ((id SUBSEP a) in aep) }
# show the date only when it differs from the first day of the logs
function shown(str) {
  if (SPAN_FIRST != "" && substr(str, 1, 10) == substr(SPAN_FIRST, 1, 10)) return substr(str, 12)
  return str
}

{
  line = $0

  # ---- every run ID on the line (run- + 16 characters; "run-events" etc. are shorter)
  s = line
  while (match(s, /run-[A-Za-z0-9]+/)) {
    id = substr(s, RSTART, RLENGTH)
    if (length(id) == 20) {
      if (!(id in seen)) { seen[id] = 1; order[++nid] = id }
      cnt[id]++
    }
    s = substr(s, RSTART + RLENGTH)
  }

  # ---- audit log (atlas / sidekiq / sidekiq-critical)
  if (index(line, "[Audit Log]")) {
    res = sval(line, "resource"); act = sval(line, "action"); rid = sval(line, "resource_id"); ts = sval(line, "timestamp")
    if (ts == "") next
    str = isostr(ts)
    if (res == "run" && rid ~ /^run-/) {
      e = ep(str)
      k = rid SUBSEP act
      if (!(k in aep) || e < aep[k]) aep[k] = e
      if (!(rid in fe) || e < fe[rid]) { fe[rid] = e; fs[rid] = str }
      if (!(rid in le) || e > le[rid]) { le[rid] = e; ls[rid] = str }
      actors[rid] = actors[rid] "|" sval(line, "actor")
      if (act == "create") {
        u = grab(line, "\\[[0-9a-f-]+\\] \\[Audit Log\\]")
        sub(/\] \[Audit Log\]$/, "", u); sub(/^\[/, "", u)
        if (u != "") runreq[rid] = u
      }
    } else if (res == "configuration_version" && act == "errored") {
      if (!(rid in cverr)) { cverr[rid] = str; ncv++; cvorder[ncv] = rid }
    } else if (res == "configuration_version" && act == "create" && index(sval(line, "actor"), "-webhooks-")) {
      if (!(rid in cvhook)) { cvhook[rid] = 1; nch++; chlist[nch] = rid }
    } else if (res == "configuration_version" && act == "uploaded") {
      e = ep(str)
      if (!(rid in upl) || e < upl[rid]) { upl[rid] = e; uplstr[rid] = str }
    }
    next
  }

  # ---- agent was told to shut down while working on a run
  if (index(line, "Received interrupt, shutting down")) {
    r = sval(line, "run_id"); ts = sval(line, "@timestamp")
    if (r != "" && ts != "") { e = ep(isostr(ts)); if (!(r in intr) || e < intr[r]) intr[r] = e }
    next
  }

  # ---- workspace name
  if (index(line, "Handling run: run_id=")) {
    r = grab(line, "Handling run: run_id=run-[A-Za-z0-9]+"); sub(/.*run_id=/, "", r)
    w = grab(line, "workspace_name=[^ \"]+"); sub(/^workspace_name=/, "", w)
    if (r != "" && w != "") wsn[r] = w
    next
  }

  # ---- workspace from the UI page URL (nginx Referer), also known for runs that never ran
  if (match(line, /\/workspaces\/[^\/ "?]+\/runs\/run-[A-Za-z0-9]+/)) {
    u = substr(line, RSTART, RLENGTH); split(u, up, "/")
    if (!(up[5] in wsr)) wsr[up[5]] = up[3]
  }

  # ---- why a configuration version failed (vcs-ingress job)
  if (index(line, "| fatal:")) {
    cv = sval(line, "workload_id")
    if (cv ~ /^cv-/ && !(cv in cvwhy)) { m = sval(line, "@message"); sub(/^ *\| */, "", m); cvwhy[cv] = m }
    next
  }

  # ---- atlas request lines
  if (index(line, "\"method\":\"") && index(line, "\"duration\":")) {
    m = sval(line, "method"); p = sval(line, "path")
    if (m == "POST" && p == "/api/v2/runs") { ua[sval(line, "request_id")] = sval(line, "user_agent"); next }
    if (m == "GET" && p ~ /^\/api\/v2\/runs\/run-[A-Za-z0-9]+$/) {
      id = substr(p, 14)
      x = lead(line)
      if (x != "") {
        pc[id]++
        e = ep(x)
        if (!(id in pf) || e < pf[id]) pf[id] = e
      }
    }
    next
  }
}

function statuscode(id) {
  if (hasact(id, "applied")) return 1
  if (hasact(id, "errored")) return 2
  if (hasact(id, "canceled") || hasact(id, "force_canceled")) return 3
  if (hasact(id, "discarded")) return 4
  if (hasact(id, "finished")) return 5
  if (hasact(id, "applying") || hasact(id, "confirmed") || hasact(id, "apply")) return 7
  if (hasact(id, "planned")) return 6
  if (hasact(id, "planning")) return 8
  return 9
}
function shortst(c) { return (c == 6) ? "planned" : (c == 7) ? "applying" : (c == 8) ? "planning" : "queued" }
function wsof(id) { return (id in wsn) ? wsn[id] : ((id in wsr) ? wsr[id] : "") }

END {
  lastlog = (SPAN_LAST != "") ? ep(SPAN_LAST) : 0
  split("applied|errored|canceled|discarded|plan only (speculative)|planned (waiting for confirmation)|applying (running)|planning (running)|queued (waiting for an agent)|pending (waiting for a previous run or its approval)", lab, "|")

  # ---- pending runs that never got a queue event: a VCS configuration version (created by
  # a webhook user and uploaded) with no run starting within a few seconds after the upload.
  # Normal VCS runs are queued in the same second as the upload. Such a run is created but
  # blocked, typically by an earlier run of the workspace that waits for a confirm.
  for (i = 1; i <= nid; i++) {
    id = order[i]
    if ((id in fe) && !hasact(id, "create")) fsec[fe[id]]++
  }
  for (j = 1; j <= nch; j++) {
    cv = chlist[j]
    if (!(cv in upl)) continue
    u = upl[cv]; found = 0
    for (d = -2; d <= 10; d++) if (fsec[u + d] > 0) found = 1
    if (found) continue
    # the run ID is only known from page requests after the upload: used as a label only
    best = ""; bp = 0
    for (i = 1; i <= nid; i++) {
      id = order[i]
      if (!(id in fe) && (id in pf) && !(id in claimed) && pf[id] >= u && pf[id] <= u + 600 && (best == "" || pf[id] < bp)) { best = id; bp = pf[id] }
    }
    if (best != "") claimed[best] = 1
    nor++; orcv[nor] = cv; orid[nor] = (best != "" ? best : "(run ID not in the logs)")
    ows[nor] = (best != "" ? wsof(best) : "")
    # blocking run: latest run of the same workspace, started before, that has not finished
    blk = ""; bt = 0
    if (ows[nor] != "") for (i = 1; i <= nid; i++) {
      id = order[i]
      if ((id in fe) && fe[id] < u && statuscode(id) >= 6 && wsof(id) == ows[nor] && fe[id] >= bt) { blk = id; bt = fe[id] }
    }
    oblk[nor] = blk
    if (blk != "") blocks[blk] = blocks[blk] " `" orid[nor] "`"
  }

  for (i = 1; i <= nid; i++) {
    id = order[i]
    if (id in fe) {
      code = statuscode(id)

      # ---- workflow
      if (hasact(id, "create")) {
        a = ua[runreq[id]]
        if (index(a, "go-tfe")) wf = "CLI"
        else if (index(a, "Mozilla")) wf = "UI"
        else wf = "API client"
      } else if (index(actors[id], "-webhooks-")) wf = "VCS"
      else wf = "API-driven"

      # ---- evidence
      note = ""
      if (code == 2 && (id in intr) && aep[id SUBSEP "errored"] >= intr[id])
        note = sprintf("agent interrupted at %s (task-worker), run errored at %s, %s later", clk(intr[id]), clk(aep[id SUBSEP "errored"]), fmt(aep[id SUBSEP "errored"] - intr[id]))
      else if (code == 2 && (id in intr))
        note = sprintf("agent interrupted at %s (task-worker)", clk(intr[id]))
      else if (code >= 6 && code <= 10) {
        note = sprintf("no later event; last event %s", clk(le[id]))
        if (lastlog > 0) note = note sprintf(", last log line %s (%s later)", clk(lastlog), fmt(lastlog - le[id]))
        if (code == 6) note = note "; waiting for a confirm or discard"
      }
      if (id in blocks) note = note (note != "" ? "; " : "") "blocks the pending run" blocks[id]
      dur = (code <= 5) ? fmt(le[id] - fe[id]) : "-"
      printf "%d\t%s\t%s\t%s\t%d\t%s\t%s\t%s\t%s\n", fe[id], id, wf, (wsof(id) != "" ? wsof(id) : "-"), code, shown(fs[id]), shown(ls[id]), dur, note > RUNS
      if (code == 2 || (code >= 6 && code <= 10)) printf "%d\t- `%s` is %s: %s\n", (code == 2 ? 1 : 2), id, lab[code], note > OBS
    } else if (!(id in claimed)) {
      printf "%s\t%d\t%d\n", id, cnt[id], pc[id] + 0 > HIST
    }
  }

  for (j = 1; j <= nor; j++) {
    cv = orcv[j]
    note = sprintf("configuration version `%s` uploaded at %s by a webhook, but no run was queued after it", cv, clk(upl[cv]))
    if (oblk[j] != "") note = note sprintf("; the workspace is blocked by `%s` (%s)", oblk[j], shortst(statuscode(oblk[j])))
    printf "%d\t%s\t%s\t%s\t%d\t%s\t%s\t%s\t%s\n", upl[cv], orid[j], "VCS", (ows[j] != "" ? ows[j] : "-"), 10, shown(uplstr[cv]), shown(uplstr[cv]), "-", note > RUNS
    printf "%d\t- `%s` is %s: %s\n", 2, orid[j], lab[10], note > OBS
  }

  for (j = 1; j <= ncv; j++) {
    cv = cvorder[j]
    printf "- Configuration version `%s` errored at %s%s. Configuration versions are not counted as runs.\n", cv, shown(cverr[cv]), (cv in cvwhy ? ": " cvwhy[cv] : "") > CVOBS
  }
}
AWK

: > "$TMP/runs.tsv"; : > "$TMP/hist.tsv"; : > "$TMP/obs.md"; : > "$TMP/cvobs.md"
awk -v RUNS="$TMP/runs.tsv" -v HIST="$TMP/hist.tsv" -v OBS="$TMP/obs.md" -v CVOBS="$TMP/cvobs.md" \
    -v SPAN_FIRST="$SPAN_FIRST" -v SPAN_LAST="$SPAN_LAST" \
    -f "$TMP/lib.awk" -f "$TMP/extract.awk" "$TMP/raw"
sort -t "$TAB" -s -k1,1n "$TMP/runs.tsv" > "$TMP/runs.sorted"
# errored runs first in the "needs attention" list, so a cap never hides them
sort -t "$TAB" -s -k1,1n "$TMP/obs.md" | cut -f2- > "$TMP/obs.sorted" && mv "$TMP/obs.sorted" "$TMP/obs.md"

# ---------------------------------------------------------------- report
cat > "$TMP/report.awk" <<'AWK'
function esc(s) { gsub(/\|/, "\\\\|", s); return s }
function pct(n, t) { return (t > 0) ? sprintf("%.1f%%", n * 100 / t) : "-" }

BEGIN {
  FS = "\t"
  split("applied|errored|canceled|discarded|plan only (speculative)|planned (waiting for confirmation)|applying (running)|planning (running)|queued (waiting for an agent)|pending (waiting for a previous run or its approval)", lab, "|")
  split("CLI|API-driven|VCS|UI|API client", wfl, "|")
  # short column names for the by-workflow table
  split("applied|errored|canceled|discarded|plan only|planned|applying|planning|queued|pending", sh, "|")
  split("applied|errored|canceled|discarded|plan only|planned|applying|planning|queued|pending", shl, "|")
}
{
  n++; id[n] = $2; wf[n] = $3; ws[n] = $4; code[n] = $5; cr[n] = $6; la[n] = $7; du[n] = $8; nt[n] = $9
  cc[$5]++; wc[$3]++
  wcs[$3, sh[$5]]++; scs[sh[$5]]++
}
END {
  while ((getline l < HIST) > 0) { nh++; hid[nh] = l }
  total = n

  print "# Run summary"
  print ""
  printf "Logs read: %s, %d lines, from %s to %s (UTC).\n", NFILES, SPAN_LINES, (SPAN_FIRST != "" ? SPAN_FIRST : "?"), (SPAN_LAST != "" ? SPAN_LAST : "?")
  print ""
  print "## Summary"
  print ""
  printf "- **Runs with a lifecycle in the logs:** %d\n", total
  print ""
  if (total > 0) {
    print "| Status | Runs | % |"
    print "|---|---|---|"
    for (c = 1; c <= 10; c++) if (cc[c] > 0) printf "| %s | %d | %s |\n", lab[c], cc[c], pct(cc[c], total)
    printf "| **Total** | **%d** | **100%%** |\n", total
    print ""

    print "## By workflow"
    print ""
    # one column per status that occurs, so every number says what the runs are
    nsc = 0
    for (c = 1; c <= 10; c++) if (scs[shl[c]] > 0) cols[++nsc] = shl[c]
    h = "| Workflow | Runs | % |"; d = "|---|---|---|"
    for (c = 1; c <= nsc; c++) { h = h " " cols[c] " |"; d = d "---|" }
    print h
    print d
    for (j = 1; j <= 5; j++) {
      w = wfl[j]
      if (wc[w] > 0) {
        r = sprintf("| %s | %d | %s |", w, wc[w], pct(wc[w], total))
        for (c = 1; c <= nsc; c++) r = r sprintf(" %d |", wcs[w, cols[c]])
        print r
      }
    }
    r = sprintf("| **Total** | **%d** | **100%%** |", total)
    for (c = 1; c <= nsc; c++) r = r sprintf(" **%d** |", scs[cols[c]])
    print r
    print ""
    print "Each column is a run status. The workflow is how the run was started: `CLI` = terraform CLI, `VCS` = push or pull request on the connected repository, `API-driven` = an API client uploaded the configuration and TFE created the run, `UI` = started in the web UI."
    print ""

    if (FULL) {
      print "## Runs"
      print ""
      print "Sorted by the first event. All times UTC. Audit events have whole-second times. For the details of one run use `run_timing.sh <run-id>`."
      print ""
      print "| Run | Workflow | Workspace | Status | First event | Last event | Duration | Evidence |"
      print "|---|---|---|---|---|---|---|---|"
      for (i = 1; i <= n; i++)
        printf "| `%s` | %s | %s | %s | %s | %s | %s | %s |\n", id[i], wf[i], ws[i], lab[code[i]], cr[i], la[i], du[i], esc(nt[i])
      print ""
    }
  } else {
    print "No run with audit events was found. Are atlas.log, sidekiq.log and sidekiq-critical.log in the input?"
    print ""
  }

  if (nh > 0 && FULL) {
    print "## Run IDs without a status"
    print ""
    print "These IDs have no create or queue event in the logs, so they are not counted as runs. They are runs from before the logs start, or runs that were only viewed or polled."
    print ""
    print "| Run | Lines in the logs | Page requests |"
    print "|---|---|---|"
    for (i = 1; i <= nh; i++) { split(hid[i], p, "\t"); printf "| `%s` | %d | %d |\n", p[1], p[2], p[3] }
    print ""
  }

  if (FULL) {
    print "## Runs that need attention"
    print ""
    print "Errored, canceled or discarded runs, and runs that are still waiting or running. Errored runs come first."
    print ""
    nobs = 0
    while ((getline l < OBS) > 0) { print l; nobs++ }
    if (nobs == 0) print "- None."
    print ""
    print "## Other observations"
    print ""
    nobs = 0
    while ((getline l < CVOBS) > 0) { print l; nobs++ }
    if (nobs == 0) print "- None."
    print ""
  } else {
    print "_Short report. Run with `--full` for one row per run, the runs that need attention and other observations._"
    print ""
  }
  print "_Status is derived from the run audit events (atlas, sidekiq, sidekiq-critical). The workflow is the user agent of the run-create request (CLI = go-tfe, UI = browser); runs without a create event are VCS when a webhook user changed the state, otherwise API-driven. Only runs that were created are counted (a run create or queue event, or for VCS a webhook configuration version that was uploaded without a run being queued: a pending run waiting behind another run)._"
  print ""
  printf "_Generated by run_summary.sh from %d unique log lines._\n", LINES
}
AWK

awk -v HIST="$TMP/hist.tsv" -v OBS="$TMP/obs.md" -v CVOBS="$TMP/cvobs.md" -v NFILES="$NFILES" \
    -v FULL="$FULL" \
    -v SPAN_FIRST="$SPAN_FIRST" -v SPAN_LAST="$SPAN_LAST" -v SPAN_LINES="$SPAN_LINES" \
    -v LINES="$(wc -l < "$TMP/raw" | tr -d ' ')" \
    -f "$TMP/lib.awk" -f "$TMP/report.awk" "$TMP/runs.sorted"
