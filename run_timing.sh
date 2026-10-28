#!/usr/bin/env bash
#
# run_timing.sh - build a timing report (markdown) for one Terraform Enterprise run
#
# Usage:
#   ./run_timing.sh [-w MINUTES] <run-id> [file-or-dir ...]   > result.md
#   grep run-XXXX * | ./run_timing.sh run-XXXX                > result.md
#
# Input can be:
#   - pre-grepped output  (lines like "atlas.log:2026-10-26 18:54:09 ...")
#   - raw log files or directories (searched recursively for the run ID)
#   - stdin (when no file/dir is given and stdin is a pipe)
# With no arguments at all and a terminal on stdin, the current directory is searched.
#
# Understood log types: atlas (audit log, API calls), sidekiq (audit log),
# task-worker (agent steps), archivist (log reads) and nginx (access log).
# Output goes to stdout; times are UTC as found in the logs.
#
# Section "Before the run was created" (the CLI verifying the workspace, creating
# and uploading the configuration version, creating the run) has no run ID in the
# logs. It needs the raw log files or directory (not stdin / pre-grepped lines):
#   1. The run-create request is found through the audit event of the run
#      (same request ID). That gives the user, IP and API token.
#   2. That token's earlier calls are listed, looking back -w MINUTES (default 15),
#      but not further back than the previous run created with the same token.
#   3. The last configuration version created in that window is checked against the
#      agent: "Downloading Terraform configuration" for this run, followed within
#      0.5s by an archivist download of that configuration version = confirmed.
#      Otherwise the result is "unconfirmed (matched by user and time only)".
#
# VCS runs (webhook) have no run-create request. If the run has no "create" audit
# event, the configuration version is found through the agent's "Downloading
# Terraform configuration" line and the archivist download after it. The report
# then shows the webhook, the clone by the vcs-ingress agent job, the upload and
# the moment the run was queued. The webhook is matched by time only.
#
# API-driven runs have no run-create request either: the client creates and uploads
# a configuration version and TFE creates and queues the run itself. When the
# configuration version found for the run was created by an API request, the
# token of that request is used as in the first case, and the sequence ends when
# TFE queues the run. The user agent is shown but never used for matching.
#
set -u

usage() {
  awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"
  exit "${1:-0}"
}

case "${1:-}" in --help) usage 0 ;; esac

WIN=15
while getopts ':w:h' opt; do
  case $opt in
    w) WIN=$OPTARG ;;
    h) usage 0 ;;
    *) usage 1 ;;
  esac
done
shift $((OPTIND - 1))

case "$WIN" in
  ''|*[!0-9]*|0) echo "error: -w needs a whole number of minutes (got '$WIN')" >&2; exit 1 ;;
esac

[ $# -ge 1 ] || usage 1

RUN_ID=$1
shift

case "$RUN_ID" in
  run-*) ;;
  *) echo "warning: '$RUN_ID' does not look like a run ID (run-XXXXXXXXXXXXXXXX)" >&2 ;;
esac

TMP=$(mktemp -d "${TMPDIR:-/tmp}/run_timing.XXXXXX") || exit 1
trap 'rm -rf "$TMP"' EXIT
TAB=$(printf '\t')

# ---------------------------------------------------------------- collect
# Pull every line that mentions the run ID, remove the "file.log:" prefix that
# a plain `grep` adds, and drop exact duplicate lines.
collect() {
  if [ $# -gt 0 ]; then
    grep -raF --exclude='*.md' --exclude='*.sh' -r -- "$RUN_ID" "$@" 2>/dev/null
  elif [ ! -t 0 ]; then
    grep -aF -- "$RUN_ID"
  else
    grep -raF --exclude='*.md' --exclude='*.sh' -r -- "$RUN_ID" . 2>/dev/null
  fi
}

# `grep -h` is not combined above because -r with one file would omit the prefix
# anyway; strip any prefix of the form "path/name.log:" or "name.txt:".
collect "$@" \
  | sed -E 's#^(\./)?([A-Za-z0-9_./-]+/)?[A-Za-z0-9_.-]+\.(log|txt)(\.[0-9]+)?:##' \
  | sort -u > "$TMP/raw"

if [ ! -s "$TMP/raw" ]; then
  echo "error: no lines containing '$RUN_ID' were found" >&2
  exit 1
fi

: > "$TMP/ev.tsv"; : > "$TMP/api.tsv"; : > "$TMP/err.tsv"
: > "$TMP/arch.tsv"; : > "$TMP/meta.tsv"
: > "$TMP/pre.md"; : > "$TMP/pre.sum"; : > "$TMP/pre.start"

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
function nval(s, key,   r) {
  r = grab(s, "\"" key "\":[0-9.]+")
  if (r == "") return ""
  sub("^\"" key "\":", "", r)
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
AWK

# ---------------------------------------------------------------- extract
cat > "$TMP/extract.awk" <<'AWK'
function lead(s) {
  return grab(s, "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]")
}
function emit(d, t, kind, stage, desc) {
  t = substr(t, 1, 12)
  gsub(/\t/, " ", desc)
  printf "%.3f\t%s\t%s\t%s\t%s\t%s\n", epoch(d, t), d, t, kind, stage, desc >> EV
}
function meta(k, v) { if (v != "") printf "%s\t%s\n", k, v >> META }
function side(file, d, t, src, a, b) {
  t = substr(t, 1, 12)
  printf "%.3f\t%s\t%s\t%s\t%s\t%s\n", epoch(d, t), d, t, src, a, b >> file
}

{
  line = $0

  # ---- generic facts (any log type)
  w = grab(line, "workspace_name=[^ \"]+");   if (w != "") { sub(/^workspace_name=/, "", w); meta("Workspace", w) }
  w = grab(line, "\"workspace\":\\{\"id\":\"ws-[A-Za-z0-9]+\",\"name\":\"[^\"]*\"")
  if (w != "") { sub(/.*"name":"/, "", w); sub(/"$/, "", w); meta("Workspace", w) }
  w = grab(line, "agent_version=[0-9A-Za-z.-]+"); if (w != "") { sub(/^agent_version=/, "", w); meta("Agent version", w) }
  w = grab(line, "agent_pool_id=apool-[A-Za-z0-9]+"); if (w != "") { sub(/^agent_pool_id=/, "", w); meta("Agent pool", w) }
  w = grab(line, "Terraform CLI details: version=[0-9A-Za-z.-]+"); if (w != "") { sub(/.*version=/, "", w); meta("Terraform CLI", w) }
  w = grab(line, "polchk-[A-Za-z0-9]+");     meta("Policy check", w)
  meta("Organization", sval(line, "organization_name"))
  meta("Project", sval(line, "project_name"))

  # ---- audit log (atlas / sidekiq)
  if (index(line, "[Audit Log]")) {
    res = sval(line, "resource"); act = sval(line, "action"); ts = sval(line, "timestamp")
    if (res != "" && ts != "") {
      d = substr(ts, 1, 10); t = substr(ts, 12); sub(/Z$/, "", t)
      rid = sval(line, "resource_id")
      if (res == "run") {
        emit(d, t, "STATE", "", act)
        if (act == "create") meta("Created by", sval(line, "actor"))
      } else if (res == "agent") {
        emit(d, t, "AUD", sval(line, "run_stage"), "agent " act " " rid)
      } else {
        emit(d, t, "AUD", "", res " " act " " rid)
      }
      meta("Organization", sval(line, "organization"))
      if (index(line, "\"run\":{\"id\":\"")) meta("Run message", sval(line, "message"))
    }
    next
  }

  # ---- task-worker (agent steps and task invocation)
  if (index(line, "\"@module\":\"task-worker")) {
    stage = sval(line, "workload_type")
    mod = sval(line, "@module"); msg = sval(line, "@message"); ts = sval(line, "@timestamp")
    if (stage != "") meta(stage " ID", sval(line, "workload_id"))
    if (mod == "task-worker.router") {
      d = substr(ts, 1, 10); t = substr(ts, 12); sub(/Z$/, "", t)
      emit(d, t, "RTR", stage, "task-worker " sval(line, "method") " " sval(line, "path") " -> HTTP " nval(line, "status_code") " (" sval(line, "duration") ")")
    } else {
      rest = msg
      if (match(msg, /^[0-9]+-[0-9]+-[0-9]+T[0-9:.]+Z /)) {
        ts = substr(msg, 1, RLENGTH - 1); rest = substr(msg, RLENGTH + 1)
      }
      d = substr(ts, 1, 10); t = substr(ts, 12); sub(/Z$/, "", t)
      lvl = grab(rest, "^\\[[A-Z]+\\]")
      sub(/^\[[A-Z]+\] +/, "", rest)
      if (lvl == "[WARN]" || lvl == "[ERROR]") rest = lvl " " rest
      emit(d, t, "TW", stage, rest)
    }
    next
  }

  # ---- policy check result line
  if (index(line, "Finished policy check")) {
    ts = lead(line); split(ts, a, " ")
    emit(a[1], a[2], "POL", "", grab(line, "Finished policy check.*"))
    next
  }

  # ---- archivist (log object reads)
  if (index(line, "\"@module\":\"archivist")) {
    key = sval(line, "obj.key"); ts = sval(line, "@timestamp")
    sub(/^terraform\/logs\//, "", key); sub(/-.*/, "", key)
    d = substr(ts, 1, 10); t = substr(ts, 12); sub(/Z$/, "", t)
    side(ARCH, d, t, "archivist", key " log read", "")
    next
  }

  # ---- atlas API request lines
  if (index(line, "\"method\":\"") && index(line, "\"duration\":")) {
    m = sval(line, "method"); p = sval(line, "path"); st = nval(line, "status")
    du = nval(line, "duration"); db = nval(line, "db")
    sub(/\?.*/, "", p); gsub(RID, ":run", p)
    printf "%s %s\t%s\t%s\t%s\n", m, p, st, du, db >> API
    if (st + 0 >= 400) {
      ts = lead(line); split(ts, a, " ")
      if (ts != "") side(ERR, a[1], a[2], "atlas", st, m " " p)
    }
    next
  }

  # ---- nginx access log
  if (match(line, /"[A-Z]+ [^ ]+ HTTP\/[0-9.]+" [0-9]+/)) {
    seg = substr(line, RSTART, RLENGTH); gsub(/"/, "", seg); split(seg, sp, " ")
    meth = sp[1]; path = sp[2]; stat = sp[4]
    nt = grab(line, "\\[[0-9][0-9]/[A-Za-z][A-Za-z][A-Za-z]/[0-9][0-9][0-9][0-9]:[0-9][0-9]:[0-9][0-9]:[0-9][0-9]")
    if (nt != "") {
      mi = (index("JanFebMarAprMayJunJulAugSepOctNovDec", substr(nt, 5, 3)) + 2) / 3
      nd = sprintf("%s-%02d-%s", substr(nt, 9, 4), mi, substr(nt, 2, 2))
      nh = substr(nt, 14, 8)
      sub(/\?.*/, "", path)
      if (path ~ /^\/_archivist\//) {
        side(ARCH, nd, nh, "nginx", "log object fetch", "")
        path = "/_archivist/v1/object/<blob>"
      }
      gsub(RID, ":run", path)
      if (stat + 0 >= 400) side(ERR, nd, nh, "nginx", stat, meth " " substr(path, 1, 100))
    }
    next
  }
}
AWK

awk -v RID="$RUN_ID" -v EV="$TMP/ev.tsv" -v API="$TMP/api.tsv" -v ERR="$TMP/err.tsv" \
    -v ARCH="$TMP/arch.tsv" -v META="$TMP/meta.tsv" \
    -f "$TMP/lib.awk" -f "$TMP/extract.awk" "$TMP/raw"

sort -u "$TMP/ev.tsv" | sort -t "$TAB" -s -k1,1n > "$TMP/ev.sorted"
if [ ! -s "$TMP/ev.sorted" ]; then
  echo "error: lines were found for '$RUN_ID' but none could be parsed as run events" >&2
  exit 1
fi

# ---------------------------------------------------------------- before the run
# A second pass over the original logs: the calls before the run exists do not
# contain the run ID.
cat > "$TMP/pre.awk" <<'AWK'
function isodt(ts,   d, t) {
  d = substr(ts, 1, 10); t = substr(ts, 12); sub(/Z$/, "", t)
  return epoch(d, t)
}
function hms(e,   s, h, m) {
  s = e - 86400 * int(e / 86400); h = int(s / 3600); m = int((s % 3600) / 60)
  return sprintf("%02d:%02d:%06.3f", h, m, s - h * 3600 - m * 60)
}

{
  line = $0

  # ---- audit events: remember them by request ID
  if (index(line, "[Audit Log]")) {
    res = sval(line, "resource"); act = sval(line, "action")
    u = grab(line, "\\[[0-9a-f-]+\\] \\[Audit Log\\]")
    sub(/\] \[Audit Log\]$/, "", u); sub(/^\[/, "", u)
    if (u == "") next
    rid = sval(line, "resource_id")
    if (res == "configuration_version") {
      evt[u] = res " " act " " rid; cvof[u] = rid
      if (act == "create") cvc[u] = rid
    } else if (res == "run" && act == "create") {
      evt[u] = "run create " rid; runc[u] = rid
    }
    next
  }

  # ---- agent: configuration download for this run
  if (index(line, "Downloading Terraform configuration") && index(line, "\"run_id\":\"" RUN "\"")) {
    if (dl == "") dl = isodt(sval(line, "@timestamp"))
    next
  }

  # ---- archivist: configuration version slugs
  if (index(line, "\"@module\":\"archivist")) {
    key = sval(line, "obj.key")
    if (key !~ /^terraform\/slugs\/cv-/) next
    cv = key; sub(/^terraform\/slugs\//, "", cv); sub(/\/.*/, "", cv)
    mod = sval(line, "@module"); msg = sval(line, "@message"); e = isodt(sval(line, "@timestamp"))
    if (mod == "archivist.server.http.download" && msg == "Starting download request") { nd++; dle[nd] = e; dlcv[nd] = cv }
    if (mod == "archivist.server.http.upload" && msg == "Starting upload request" && !(cv in ups)) ups[cv] = e
    if (index(mod, "send-callback") && msg == "success") upc[cv] = e
    next
  }

  # ---- atlas request lines
  if (index(line, "\"method\":\"") && index(line, "\"duration\":")) {
    x = grab(line, "^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]")
    u = sval(line, "request_id")
    if (x == "" || u == "" || (u in idx)) next
    split(x, a, " ")
    n++; idx[u] = n; ruid[n] = u
    rd[n] = a[1]; rt[n] = a[2]; rep[n] = epoch(a[1], a[2])
    meth[n] = sval(line, "method"); pth[n] = sval(line, "path"); sub(/\?.*/, "", pth[n])
    sta[n] = nval(line, "status"); dur[n] = nval(line, "duration")
    tok[n] = sval(line, "token_external_id"); rip[n] = sval(line, "remote_ip"); uas[n] = sval(line, "user_agent")
  }
}

# another run (CLI flow) or configuration version (API flow) made with the same token in the window
function other(u, id,   i) {
  if (u == UUID || !(u in idx)) return
  i = idx[u]
  if (tok[i] != TOKEN || rep[i] > ET || rep[i] < lo) return
  np++; prid[np] = id; prep[np] = rep[i]; prt[np] = rt[i]; prevrow[i] = 1
  if (rep[i] <= CE && rep[i] > cut) cut = rep[i]
}

END {
  if (!(UUID in idx)) { print "the request " UUID " that started the run was not found in the log files" > REASON; exit }
  # CLI flow: UUID is the run-create request and the sequence ends there.
  # API flow:  UUID is the configuration-version create request and the sequence
  #            ends when TFE queues the run itself (QE).
  api = (MODE == "api")
  c = idx[UUID]; CE = rep[c]; lo = CE - WIN * 60
  ET = (api && QE + 0 > CE) ? QE + 0 : CE
  ETS = (ET == CE) ? rt[c] : substr(hms(ET), 1, 8)

  cut = 0
  if (api) { for (u in cvc) other(u, cvc[u]) }
  else     { for (u in runc) other(u, runc[u]) }
  start = (cut > lo) ? cut : lo

  # last configuration version created by this token before the run create
  CV = ""; bep = -1; bi = 0
  if (api) CV = cvc[UUID]
  else for (u in cvc) {
    if (!(u in idx)) continue
    i = idx[u]
    if (tok[i] != TOKEN || rep[i] < start || rep[i] > CE) continue
    if (rep[i] == CE && i > c) continue
    if (rep[i] > bep || (rep[i] == bep && i > bi)) { bep = rep[i]; bi = i; CV = cvc[u] }
  }

  # rows that belong to the pre-run sequence
  for (i = 1; i <= n; i++) {
    if (rep[i] < start || rep[i] > ET || (!api && rep[i] == CE && i > c) || prevrow[i]) continue
    if (tok[i] == TOKEN) {
      if (pth[i] ~ /\/(runs|plans|applies|policy-checks|comments|task-stages|run-events|cost-estimates)\//) continue
      p = grab(pth[i], "cv-[A-Za-z0-9]+")
      if (p != "" && CV != "" && p != CV) continue
      b = "token"
    } else if (CV != "" && cvof[ruid[i]] == CV) {
      b = "config version audit"
    } else if (tok[i] == "" && rip[i] == IP && (pth[i] == "/.well-known/terraform.json" || pth[i] == "/api/v2/ping")) {
      b = "IP only"
    } else continue
    ns++; sel[ns] = i; by[i] = b
  }
  # calls without a token (.well-known, ping) are only kept up to 5s before the first token call
  ft = -1
  for (j = 1; j <= ns; j++) if (by[sel[j]] != "IP only" && (ft < 0 || rep[sel[j]] < ft)) ft = rep[sel[j]]
  m = 0
  for (j = 1; j <= ns; j++) if (by[sel[j]] != "IP only" || (ft >= 0 && rep[sel[j]] >= ft - 5)) sel[++m] = sel[j]
  ns = m
  for (j = 2; j <= ns; j++) {            # order by time, then by file order
    v = sel[j]
    for (k = j - 1; k >= 1 && (rep[sel[k]] > rep[v] || (rep[sel[k]] == rep[v] && sel[k] > v)); k--) sel[k + 1] = sel[k]
    sel[k + 1] = v
  }
  if (ns == 0) { print "no calls found for this token before the run create" > REASON; exit }
  first = rep[sel[1]]; total = ET - first
  endword = api ? "run queued" : "run create"

  # does the agent confirm the configuration version?
  conf = "unconfirmed (matched by user and time only)"
  why = ""
  if (CV == "") {
    why = "no configuration version create by this token was found in the window"
  } else if (dl == "") {
    why = "the agent line \"Downloading Terraform configuration\" for this run is not in the logs"
  } else {
    bk = 0
    for (k = 1; k <= nd; k++) {
      dt = dle[k] - dl
      if (dt >= 0 && dt <= 0.5 && (!bk || dt < bd)) { bk = k; bd = dt }
    }
    if (!bk) why = "no archivist download followed the agent's download line"
    else if (dlcv[bk] == CV) { conf = "confirmed"; why = sprintf("agent \"Downloading Terraform configuration\" at %s, archivist \"Starting download request\" for %s %.0f ms later", hms(dl), CV, bd * 1000) }
    else why = "the agent downloaded " dlcv[bk] " at " hms(dle[bk]) " instead"
  }

  # ---- markdown section
  print "## Before the run was created" > OUT
  print "" > OUT
  if (api) {
    printf "API-driven workflow: there is no run-create request. The client created and uploaded a configuration version and TFE then created and queued the run itself. " > OUT
    printf "Calls by `%s` (token `%s`, IP `%s`, user agent `%s`; the user agent is not used for matching) up to the moment TFE queued the run. ", ACTOR, TOKEN, IP, uas[c] > OUT
  } else printf "Calls by `%s` (token `%s`, IP `%s`) up to the run-create request `%s`. ", ACTOR, TOKEN, IP, UUID > OUT
  if (cut > lo) printf "Window: %d min, cut at the previous %s `%s` (%s) by the same token. ", WIN, (api ? "configuration version" : "run create"), prid[1], prt[1] > OUT
  else printf "Window: last %d min. ", WIN > OUT
  print "Atlas logs whole seconds, so gaps are +/- 1s." > OUT
  print "" > OUT
  print "| Time (UTC) | Gap | Request | Status | Took | Audit event | Matched by |" > OUT
  print "|---|---|---|---|---|---|---|" > OUT
  for (j = 1; j <= ns; j++) {
    i = sel[j]
    printf "| %s | %s | `%s %s` | %s | %.0f ms | %s | %s |\n", (rd[i] != rd[c] ? rd[i] " " : "") rt[i], (j > 1 ? "+" fmt(rep[i] - rep[sel[j - 1]]) : ""), meth[i], pth[i], sta[i], dur[i], (ruid[i] in evt ? "`" evt[ruid[i]] "`" : ""), by[i] > OUT
  }
  if (api) printf "| %s | +%s | (TFE queues the run) | | | `run queue %s` | audit |\n", ETS, fmt(ET - rep[sel[ns]]), RUN > OUT
  print "" > OUT
  printf "- **First call to %s:** %s (%s to %s)\n", endword, fmt(total), rt[sel[1]], ETS > OUT
  if (CV != "") printf "- **Configuration version:** `%s` - **%s**; %s\n", CV, conf, (why != "" ? why : "") > OUT
  else printf "- **Configuration version:** none found - **%s**; %s\n", conf, why > OUT

  if (CV != "" && (CV in ups) && (CV in upc))
    printf "- **Upload to archivist:** started %s, TFE callback done after %.0f ms\n", hms(ups[CV]), (upc[CV] - ups[CV]) * 1000 > OUT
  if (np > 0) {
    printf "- **Warning:** %d other %s(s) were created with this token in the last %d min:", np, (api ? "configuration version" : "run"), WIN > OUT
    for (j = 1; j <= np; j++) printf " `%s` at %s%s", prid[j], prt[j], (j < np ? "," : "") > OUT
    print ". Calls before the latest of them are not listed." > OUT
  }
  print "" > OUT

  # ---- summary line and start time
  printf "- **Before the run was created%s:** %s from first call (%s) to %s, %d calls; configuration version%s **%s**\n", (api ? " (API-driven)" : ""), fmt(total), rt[sel[1]], endword, ns, (CV != "" ? " `" CV "`" : ""), conf > SUM
  printf "%d", first > STARTF
}
AWK

# VCS workflow: there is no run-create request. A webhook creates a configuration
# version, the agent clones the repository (vcs-ingress job) and TFE then queues
# the run. The run is linked to its configuration version through the agent's
# "Downloading Terraform configuration" line and the archivist download after it.
cat > "$TMP/vcs.awk" <<'AWK'
function isodt(ts,   d, t) {
  d = substr(ts, 1, 10); t = substr(ts, 12); sub(/Z$/, "", t)
  return epoch(d, t)
}
function hms(e,   s, h, m) {
  s = e - 86400 * int(e / 86400); h = int(s / 3600); m = int((s % 3600) / 60)
  return sprintf("%02d:%02d:%06.3f", h, m, s - h * 3600 - m * 60)
}
function clk(e, prec) { return prec ? hms(e) : substr(hms(e), 1, 8) }
function add(e, prec, step, detail) { nr++; re[nr] = e; rp[nr] = prec; rs[nr] = step; rdt[nr] = detail }

{
  line = $0

  if (index(line, "[Audit Log]")) {
    res = sval(line, "resource"); act = sval(line, "action"); rid = sval(line, "resource_id")
    e = isodt(sval(line, "timestamp"))
    if (res == "configuration_version") {
      k = rid SUBSEP act
      if (!(k in ae)) { ae[k] = e; aa[k] = sval(line, "actor") }
      if (act == "create") {
        rq = grab(line, "\\[[0-9a-f-]+\\] \\[Audit Log\\]")
        sub(/\] \[Audit Log\]$/, "", rq); sub(/^\[/, "", rq)
        if (rq != "") cvreq[rid] = rq
      }
    } else if (res == "vcs-repo" && act == "receive_webhook") {
      r = sval(line, "request_id")
      if (!(r in wi)) { nw++; wi[r] = nw; we[nw] = e; wr[nw] = r; wev[nw] = sval(line, "event"); wsha[nw] = substr(sval(line, "sha"), 1, 10) }
    } else if (res == "run" && rid == RUN && act == "queue" && (!qe || e < qe)) qe = e
    next
  }

  if (index(line, "Downloading Terraform configuration") && index(line, "\"run_id\":\"" RUN "\"")) {
    e = isodt(sval(line, "@timestamp")); if (!dl || e < dl) dl = e
    next
  }

  if (index(line, "\"name\":\"vcs-ingress\"") && index(line, "\"@module\":\"task-worker")) {
    cv = sval(line, "workload_id"); msg = sval(line, "@message"); ts = sval(line, "@timestamp")
    if (match(msg, /^[0-9]+-[0-9]+-[0-9]+T[0-9:.]+Z /)) ts = substr(msg, 1, RLENGTH - 1)
    e = isodt(ts)
    if (!(cv in gmin) || e < gmin[cv]) gmin[cv] = e
    if (!(cv in gmax) || e > gmax[cv]) gmax[cv] = e
    if (index(msg, "clone_url=")) { cl = grab(msg, "clone_url=[^ ]+"); sub(/^clone_url=/, "", cl); clone[cv] = cl }
    next
  }

  if (index(line, "\"@module\":\"archivist")) {
    key = sval(line, "obj.key")
    if (key !~ /^terraform\/slugs\/cv-/) next
    cv = key; sub(/^terraform\/slugs\//, "", cv); sub(/\/.*/, "", cv)
    mod = sval(line, "@module"); msg = sval(line, "@message"); e = isodt(sval(line, "@timestamp"))
    if (mod == "archivist.server.http.download" && msg == "Starting download request") { nd++; dle[nd] = e; dlcv[nd] = cv }
    if (mod == "archivist.server.http.upload" && msg == "Starting upload request" && !(cv in ups)) ups[cv] = e
    if (index(mod, "send-callback") && msg == "success") upc[cv] = e
    next
  }

  if (index(line, "\"path\":\"/webhooks/vcs/") && index(line, "\"duration\":")) {
    x = grab(line, "^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]")
    r = sval(line, "request_id")
    if (x == "" || r == "") next
    split(x, a, " ")
    hx[r] = epoch(a[1], a[2]); hp[r] = sval(line, "path"); hs[r] = nval(line, "status")
    hd[r] = nval(line, "duration"); hip[r] = sval(line, "remote_ip"); hua[r] = sval(line, "user_agent")
  }
}

END {
  if (!dl) { print "no run-create event, and the agent line \"Downloading Terraform configuration\" for this run is not in the logs (needed to find the VCS configuration version)" > REASON; exit }
  bk = 0
  for (k = 1; k <= nd; k++) {
    dt = dle[k] - dl
    if (dt >= 0 && dt <= 0.5 && (!bk || dt < bd)) { bk = k; bd = dt }
  }
  if (!bk) { print "no run-create event, and no archivist download of a configuration version followed the agent's download line" > REASON; exit }
  CV = dlcv[bk]
  if (!((CV SUBSEP "create") in ae)) { print "no run-create event, and no create event for configuration version " CV " was found" > REASON; exit }
  cve = ae[CV SUBSEP "create"]; actor = aa[CV SUBSEP "create"]

  # A webhook creates the configuration version in a background job (no request ID).
  # A configuration version created by an API request means an API-driven run: hand
  # over to the token-based report, together with the moment TFE queued the run.
  if (CV in cvreq) { printf "%s\t%s\t%d\n", CV, cvreq[CV], qe > APIF; exit }

  # webhook: the last one received up to 5s before the configuration version was created
  bw = 0
  for (i = 1; i <= nw; i++) if (we[i] <= cve && we[i] >= cve - 5 && (!bw || we[i] > we[bw])) bw = i
  lo = (qe ? qe : cve) - WIN * 60
  for (i = 1; i <= nw; i++) if (i != bw && we[i] >= lo && we[i] <= (qe ? qe : cve)) { no++; oe[no] = we[i]; oev[no] = wev[i] }

  if (bw) {
    r = wr[bw]
    if (r in hx) add(hx[r], 0, "Webhook received", sprintf("`POST %s` -> %s, %.0f ms, from %s (%s)", hp[r], hs[r], hd[r], hip[r], hua[r]))
    add(we[bw], 0, "Audit: vcs-repo receive_webhook", sprintf("event `%s`, commit `%s`, request `%s`", wev[bw], wsha[bw], r))
  }
  if ((CV SUBSEP "fetching") in ae) add(ae[CV SUBSEP "fetching"], 0, "Audit: configuration_version fetching", "`" CV "`")
  add(cve, 0, "Audit: configuration_version create", sprintf("`%s` by `%s`", CV, actor))
  if (CV in gmin) add(gmin[CV], 1, "Agent job vcs-ingress", sprintf("clone `%s`, package and hand over; done %.1fs later", (CV in clone ? clone[CV] : "?"), gmax[CV] - gmin[CV]))
  if (CV in ups) add(ups[CV], 1, "Archivist upload of the configuration", (CV in upc) ? sprintf("TFE callback done after %.0f ms", (upc[CV] - ups[CV]) * 1000) : "")
  if ((CV SUBSEP "uploaded") in ae) add(ae[CV SUBSEP "uploaded"], 0, "Audit: configuration_version uploaded", "`" CV "`")
  if (qe) add(qe, 0, "Audit: run queue", "`" RUN "` created and queued")

  for (j = 2; j <= nr; j++) {
    v = re[j]; vp = rp[j]; vs = rs[j]; vd = rdt[j]
    for (k = j - 1; k >= 1 && re[k] > v; k--) { re[k + 1] = re[k]; rp[k + 1] = rp[k]; rs[k + 1] = rs[k]; rdt[k + 1] = rdt[k] }
    re[k + 1] = v; rp[k + 1] = vp; rs[k + 1] = vs; rdt[k + 1] = vd
  }
  first = re[1]; total = re[nr] - first

  print "## Before the run was created" > OUT
  print "" > OUT
  print "VCS workflow: no run-create request exists. A webhook creates a configuration version and TFE queues the run when the agent has cloned and uploaded the repository. Linked through configuration version `" CV "`. Audit events and atlas lines have whole-second times, so gaps are +/- 1s." > OUT
  print "" > OUT
  print "| Time (UTC) | Gap | Step | Detail |" > OUT
  print "|---|---|---|---|" > OUT
  for (j = 1; j <= nr; j++) printf "| %s | %s | %s | %s |\n", clk(re[j], rp[j]), (j > 1 ? "+" fmt(re[j] - re[j - 1]) : ""), rs[j], rdt[j] > OUT
  print "" > OUT
  printf "- **%s to %s:** %s (%s to %s)\n", (bw ? "Webhook" : "First event"), (qe ? "run queued" : "last event"), fmt(total), clk(re[1], rp[1]), clk(re[nr], rp[nr]) > OUT
  printf "- **Configuration version:** `%s` - **confirmed**; agent \"Downloading Terraform configuration\" at %s, archivist \"Starting download request\" for %s %.0f ms later\n", CV, hms(dl), CV, bd * 1000 > OUT
  if (bw) print "- **Webhook:** matched by time only; no log line holds both the webhook and the configuration version, so the push that created it is the last one received within 5s before the create." > OUT
  else print "- **Webhook:** none found in the 5s before the configuration version was created (is the VCS actor's create from a manual run or a different trigger?)." > OUT
  if (no > 0) {
    printf "- **Warning:** %d other webhook(s) were received in the last %d min before the run was queued:", no, WIN > OUT
    for (j = 1; j <= no; j++) printf " `%s` at %s%s", oev[j], clk(oe[j], 0), (j < no ? "," : "") > OUT
    print "." > OUT
  }
  print "" > OUT

  printf "- **Before the run was created (VCS webhook):** %s from %s to %s; configuration version `%s` **confirmed**\n", fmt(total), (bw ? "webhook" : "first event"), (qe ? "run queued" : "last event"), CV > SUM
  printf "%d", first > STARTF
}
AWK

SKIP_REASON=""
if [ $# -eq 0 ] && [ ! -t 0 ]; then
  SKIP_REASON="the input was read from stdin; run the script on the raw log files or directory to get this section"
else
  [ $# -gt 0 ] || set -- .
  GREP_SRC() { grep -raFh --exclude='*.md' --exclude='*.sh' -r "$@" 2>/dev/null; }
  RE_UUID='[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
  UUID=$(grep -F '"resource":"run","action":"create"' "$TMP/raw" | grep -F "$RUN_ID" \
           | sed -nE "s/.*\[($RE_UUID)\] \[Audit Log\].*/\1/p" | head -1)
  MODE=cli; QE=0
  if [ -z "$UUID" ]; then
    # no run-create event: a VCS (webhook) run or an API-driven run
    GREP_SRC -e "$RUN_ID" -e '"resource":"configuration_version"' -e '"action":"receive_webhook"' \
             -e 'Downloading Terraform configuration' -e 'Starting download request' \
             -e 'Starting upload request' -e 'send-callback' -e '"name":"vcs-ingress"' \
             -e '"path":"/webhooks/vcs/' -- "$@" > "$TMP/pre.raw"
    awk -v RUN="$RUN_ID" -v WIN="$WIN" -v OUT="$TMP/pre.md" -v SUM="$TMP/pre.sum" -v STARTF="$TMP/pre.start" \
        -v REASON="$TMP/pre.reason" -v APIF="$TMP/api.cv" -f "$TMP/lib.awk" -f "$TMP/vcs.awk" "$TMP/pre.raw"
    [ -s "$TMP/pre.reason" ] && SKIP_REASON=$(cat "$TMP/pre.reason")
    if [ -s "$TMP/api.cv" ]; then
      IFS="$TAB" read -r _ UUID QE < "$TMP/api.cv"
      MODE=api
    fi
  fi
  if [ -n "$UUID" ]; then
    REQLINE=$(GREP_SRC -e "$UUID" -- "$@" | grep -F '"duration":' | head -1)
    TOKEN=$(printf '%s\n' "$REQLINE" | sed -nE 's/.*"token_external_id":"([^"]+)".*/\1/p')
    IP=$(printf '%s\n' "$REQLINE" | sed -nE 's/.*"remote_ip":"([^"]+)".*/\1/p')
    ACTOR=$(printf '%s\n' "$REQLINE" | sed -nE 's/.*"user":"([^"]+)".*/\1/p')
    if [ -z "$TOKEN" ]; then
      SKIP_REASON="the request that started the run (ID $UUID) was not found in the input, or it was made without an API token"
    else
      GREP_SRC -e "$TOKEN" -e "\"remote_ip\":\"$IP\"" \
               -e '"resource":"configuration_version"' -e '"resource":"run","action":"create"' \
               -e 'Downloading Terraform configuration' -e 'Starting download request' \
               -e 'Starting upload request' -e 'send-callback' -- "$@" > "$TMP/pre.raw"
      awk -v RUN="$RUN_ID" -v UUID="$UUID" -v TOKEN="$TOKEN" -v IP="$IP" -v ACTOR="${ACTOR:-unknown}" -v MODE="$MODE" -v QE="$QE" \
          -v WIN="$WIN" -v OUT="$TMP/pre.md" -v SUM="$TMP/pre.sum" -v STARTF="$TMP/pre.start" \
          -v REASON="$TMP/pre.reason" -f "$TMP/lib.awk" -f "$TMP/pre.awk" "$TMP/pre.raw"
      [ -s "$TMP/pre.reason" ] && SKIP_REASON=$(cat "$TMP/pre.reason")
    fi
  fi
fi
if [ -n "$SKIP_REASON" ]; then
  {
    echo "## Before the run was created"
    echo
    echo "_Not available: ${SKIP_REASON}._"
    echo
  } > "$TMP/pre.md"
fi

# ---------------------------------------------------------------- report
cat > "$TMP/report.awk" <<'AWK'
function esc(s) { gsub(/\|/, "\\\\|", s); return s }
function srcname(i,   s) {
  s = (kind[i] == "STATE") ? "run state" : (kind[i] == "AUD") ? "audit" : (kind[i] == "TW") ? "agent" : (kind[i] == "POL") ? "policy check" : "task-worker"
  if (st[i] != "") s = s " (" st[i] ")"
  return s
}
function tdisp(i) { return (dt[i] != dt[1]) ? dt[i] " " tm[i] : tm[i] }

BEGIN { FS = "\t" }
{ n++; ep[n] = $1 + 0; dt[n] = $2; tm[n] = $3; kind[n] = $4; st[n] = $5; desc[n] = $6 }

END {
  start = ep[1]; havecreate = 0
  for (i = 1; i <= n; i++) if (kind[i] == "STATE" && desc[i] == "create") { start = ep[i]; havecreate = 1; break }

  endep = start
  for (i = 1; i <= n; i++) if ((kind[i] == "STATE" || kind[i] == "TW") && ep[i] > endep) { endep = ep[i]; endtm = tm[i] }
  for (i = 1; i <= n; i++) if (kind[i] == "STATE") {
    ns++; sn[ns] = desc[i]; se[ns] = ep[i]; sd[ns] = dt[i]; stm[ns] = tm[i]
  }

  # time until the next agent step of the same stage
  for (i = n; i >= 1; i--) if (kind[i] == "TW") {
    if (st[i] in nxt) { dur[i] = ep[nxt[st[i]]] - ep[i]; has[i] = 1 }
    nxt[st[i]] = i
  }

  # agent time per stage
  for (i = 1; i <= n; i++) if (kind[i] == "TW") {
    s = st[i]
    if (!(s in smin)) { stages[++nst] = s; smin[s] = ep[i]; smint[s] = tm[i] }
    smax[s] = ep[i]; smaxt[s] = tm[i]
  }

  # policy check
  for (i = 1; i <= n; i++) {
    if (!pq && kind[i] == "AUD" && desc[i] ~ /^policy_check queued/) pq = i
    if (!pf && kind[i] == "POL") pf = i
  }

  print "## Summary"
  print ""
  if (ns > 0) {
    printf "- **Final run state seen:** `%s` at %s\n", sn[ns], stm[ns]
    if (havecreate) printf "- **Total, run create to last run-state/agent event (%s):** %s\n", endtm, fmt(endep - start)
  }
  while ((getline l < PRESUM) > 0) print l
  if (PRE_START != "") printf "- **Total, first call before the run to last run-state/agent event:** %s\n", fmt(endep - PRE_START)
  if (pf) {
    r = desc[pf]; if (match(r, /Result: .*/)) r = substr(r, RSTART)
    if (pq) printf "- **Policy check:** %s from queued to finished (%s)\n", fmt(ep[pf] - ep[pq]), r
    else    printf "- **Policy check finished** at %s (%s)\n", tm[pf], r
  }
  total = havecreate ? endep - start : 0
  for (k = 1; k <= 3; k++) {
    best = 0; bi = 0
    for (i = 1; i <= n; i++) if (has[i] && !used[i] && dur[i] > best) { best = dur[i]; bi = i }
    if (!bi) break
    used[bi] = 1
    if (k == 1) print "- **Longest agent steps:**"
    pct = (total > 0) ? sprintf(", %.0f%% of the run", best * 100 / total) : ""
    printf "  %d. %s - `%s` (%s)%s\n", k, fmt(best), esc(desc[bi]), (st[bi] == "" ? "agent" : st[bi]), pct
  }
  print ""

  while ((getline l < PREMD) > 0) print l

  if (ns > 0) {
    print "## Run state changes"
    print ""
    print "| State entered | Time (UTC) | Time in that state |"
    print "|---|---|---|"
    for (j = 1; j <= ns; j++) {
      printf "| `%s` | %s | %s |\n", sn[j], (sd[j] != dt[1] ? sd[j] " " : "") stm[j], (j < ns ? fmt(se[j + 1] - se[j]) : "(last seen)")
    }
    print ""
  }

  if (nst > 0) {
    print "## Agent time per stage"
    print ""
    print "| Stage | First agent event | Last agent event | Duration |"
    print "|---|---|---|---|"
    for (j = 1; j <= nst; j++) {
      s = stages[j]
      printf "| %s | %s | %s | %s |\n", (s == "" ? "(unknown)" : s), smint[s], smaxt[s], fmt(smax[s] - smin[s])
    }
    print ""
  }

  print "## Timeline"
  print ""
  printf "All times UTC. _Elapsed_ is counted from %s. _Step took_ is the time until the next agent event of the same stage.\n", (havecreate ? "run create" : "the first event")
  print ""
  print "| Time | Elapsed | Step took | Source | Event |"
  print "|---|---|---|---|---|"
  for (i = 1; i <= n; i++)
    printf "| %s | %s | %s | %s | %s |\n", tdisp(i), fmt(ep[i] - start), (has[i] ? fmt(dur[i]) : ""), srcname(i), esc(desc[i])
  print ""
}
AWK

{
  echo "# Run timing: \`$RUN_ID\`"
  echo
  awk -F'\t' '
    { if (!($1 in v)) v[$1] = $2 }
    END {
      split("Organization|Project|Workspace|Created by|Run message|Plan ID|Apply ID|Policy check|Terraform CLI|Agent version|Agent pool", o, "|")
      print "| Item | Value |"; print "|---|---|"
      for (i = 1; i <= 11; i++) if (o[i] in v) { x = v[o[i]]; gsub(/\|/, "\\\\|", x); printf "| %s | `%s` |\n", o[i], x }
    }' "$TMP/meta.tsv"
  echo

  awk -v PRESUM="$TMP/pre.sum" -v PREMD="$TMP/pre.md" -v PRE_START="$(cat "$TMP/pre.start")" \
      -f "$TMP/lib.awk" -f "$TMP/report.awk" "$TMP/ev.sorted"

  if [ -s "$TMP/api.tsv" ]; then
    echo "## TFE API calls for this run"
    echo
    echo "Response times as logged by atlas (view/db are part of the total). Sorted by slowest call."
    echo
    echo "| Request | Calls | Avg | Max | Max DB | Status |"
    echo "|---|---|---|---|---|---|"
    awk -F'\t' '
      { k = $1; c[k]++; s[k] += $3; if ($3 + 0 > m[k]) m[k] = $3 + 0; if ($4 + 0 > dm[k]) dm[k] = $4 + 0
        if (index(sts[k], $2) == 0) sts[k] = sts[k] (sts[k] == "" ? "" : ", ") $2 }
      END { for (k in c) printf "%012.2f\t| `%s` | %d | %.0f ms | %.0f ms | %.0f ms | %s |\n", m[k], k, c[k], s[k] / c[k], m[k], dm[k], sts[k] }
    ' "$TMP/api.tsv" | sort -r | cut -f2-
    echo
  fi

  if [ -s "$TMP/err.tsv" ]; then
    echo "## Responses with status 400 or higher"
    echo
    echo "| Time (UTC) | Source | Status | Request |"
    echo "|---|---|---|---|"
    sort -u "$TMP/err.tsv" | sort -t "$TAB" -s -k1,1n \
      | awk -F'\t' '{ printf "| %s %s | %s | %s | `%s` |\n", $2, $3, $4, $5, $6 }'
    echo
  fi

  if [ -s "$TMP/arch.tsv" ]; then
    echo "## Log reads (archivist / nginx)"
    echo
    echo "Someone or something reading the plan/apply log while the run was active or afterwards."
    echo
    echo "| Source | What | Count | First | Last |"
    echo "|---|---|---|---|---|"
    sort -u "$TMP/arch.tsv" | sort -t "$TAB" -s -k1,1n \
      | awk -F'\t' '
          { k = $4 "\t" $5; if (!(k in c)) { order[++no] = k; first[k] = $2 " " $3 } c[k]++; last[k] = $2 " " $3 }
          END { for (j = 1; j <= no; j++) { k = order[j]; split(k, p, "\t"); printf "| %s | %s | %d | %s | %s |\n", p[1], p[2], c[k], first[k], last[k] } }'
    echo
  fi

  echo "_Generated by run_timing.sh from $(wc -l < "$TMP/raw" | tr -d ' ') unique log lines._"
}
