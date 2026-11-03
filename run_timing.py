#!/usr/bin/env python3
#
# run_timing.py - build a timing report (markdown) for one Terraform Enterprise run
#
# Python version of run_timing.sh. It gives the same report (byte for byte) and needs
# only Python 3 and its standard library.
#
# Usage:
#   ./run_timing.py [-w MINUTES] <run-id> [file-or-dir ...]   > result.md
#   grep run-XXXX * | ./run_timing.py run-XXXX                > result.md
#
# Input can be:
#   - pre-grepped output  (lines like "atlas.log:2026-10-26 18:54:09 ...")
#   - raw log files or directories (searched recursively for the run ID)
#   - stdin (when no file/dir is given and stdin is a pipe)
# With no arguments at all and a terminal on stdin, the current directory is searched.
# Files ending in .md, .sh or .py are skipped.
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
import fnmatch
import io
import os
import re
import sys

SKIP_NAMES = ("*.md", "*.sh", "*.py")     # reports and scripts can sit next to the logs


def usage(code=0):
    with open(__file__, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    for ln in lines[1:]:
        if not ln.startswith("#"):
            break
        print(re.sub(r"^# ?", "", ln))
    sys.exit(code)


# ---------------------------------------------------------------- awk-like helpers
# Lines are handled as latin-1 text: one character per byte, so the logs may contain any
# bytes and the output has the same bytes.
_sval_rx = {}
_nval_rx = {}


def sval(s, key):
    rx = _sval_rx.get(key)
    if rx is None:
        rx = _sval_rx[key] = re.compile('"' + key + '":"([^"]*)"')
    m = rx.search(s)
    return m.group(1) if m else ""


def nval(s, key):
    rx = _nval_rx.get(key)
    if rx is None:
        rx = _nval_rx[key] = re.compile('"' + key + '":([0-9.]+)')
    m = rx.search(s)
    return m.group(1) if m else ""


_NUM = re.compile(r"[ \t]*[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


def num(s):
    """awk's string to number: the leading numeric part, else 0."""
    m = _NUM.match(s)
    if not m:
        return 0
    t = m.group(0).strip()
    try:
        return int(t)
    except ValueError:
        return float(t)


def part(lst, i):
    return lst[i - 1] if 0 < i <= len(lst) else ""


def epoch(d, t):
    """seconds since 1970-01-01 (UTC) for date YYYY-MM-DD and time HH:MM:SS[.fff]"""
    a = d.split("-")
    y = num(part(a, 1))
    m = num(part(a, 2))
    dd = num(part(a, 3))
    b = t.split(":")
    hh = num(part(b, 1))
    mi = num(part(b, 2))
    ss = num(part(b, 3))
    if m <= 2:
        y -= 1
    era = int(y / 400)
    yoe = y - era * 400
    doy = int((153 * (m + (-3 if m > 2 else 9)) + 2) / 5) + dd - 1
    doe = yoe * 365 + int(yoe / 4) - int(yoe / 100) + doy
    days = era * 146097 + doe - 719468
    return days * 86400 + hh * 3600 + mi * 60 + ss


def fmt(x):
    sg = ""
    if x < 0:
        sg = "-"
        x = -x
    if x < 60:
        if x == int(x):
            return "%s%ds" % (sg, x)
        return "%s%.1fs" % (sg, x)
    r = int(x + 0.5)
    h = int(r / 3600)
    m = int((r % 3600) / 60)
    s = r % 60
    if h > 0:
        return "%s%dh %02dm %02ds" % (sg, h, m, s)
    return "%s%dm %02ds" % (sg, m, s)


def hms(e):
    s = e - 86400 * int(e / 86400)
    h = int(s / 3600)
    m = int((s % 3600) / 60)
    return "%02d:%02d:%06.3f" % (h, m, s - h * 3600 - m * 60)


def isodt(ts):
    d = ts[:10]
    t = ts[11:]
    if t.endswith("Z"):
        t = t[:-1]
    return epoch(d, t)


def esc(s):
    return s.replace("|", "\\|")


def uuid_of(line):
    """request ID of an audit line: the [uuid] in front of [Audit Log]"""
    m = re.search(r"\[([0-9a-f-]+)\] \[Audit Log\]", line)
    return m.group(1) if m else ""


RE_LEAD = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")
RE_LEAD_START = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")
RE_PREFIX = re.compile(r"^(\./)?([A-Za-z0-9_./-]+/)?[A-Za-z0-9_.-]+\.(log|txt)(\.[0-9]+)?:")


# ---------------------------------------------------------------- input
def skipped(path):
    name = os.path.basename(path)
    return any(fnmatch.fnmatchcase(name, p) for p in SKIP_NAMES)


def input_files(args):
    """Regular files below the arguments, like grep -r (symlinks met on the way are skipped)."""
    for a in args:
        if os.path.isdir(a):
            for dirpath, dirnames, filenames in os.walk(a):
                dirnames.sort()
                for f in sorted(filenames):
                    p = os.path.join(dirpath, f)
                    if not os.path.islink(p) and os.path.isfile(p) and not skipped(p):
                        yield p
        elif os.path.isfile(a) and not skipped(a):
            yield a


def file_lines(fh):
    for b in fh:
        if b.endswith(b"\n"):
            b = b[:-1]
        yield b.decode("latin-1")


def source_lines(args, needles):
    """Lines of all input files that contain at least one of the fixed strings (grep -F -e ...)."""
    for p in input_files(args):
        try:
            with open(p, "rb") as fh:
                for line in file_lines(fh):
                    for nd in needles:
                        if nd in line:
                            yield line
                            break
        except OSError:
            continue


# ---------------------------------------------------------------- extract
def extract(raw, RID):
    """One pass over the lines that mention the run: events, API calls, errors, log reads, facts."""
    ev = []          # run events (tab separated rows)
    api = []         # (request, status, duration, db)
    err = []         # rows of responses with status 400 or higher
    arch = []        # rows of log reads
    meta = {}        # first value per key

    def setmeta(k, v):
        if v != "" and k not in meta:
            meta[k] = v

    def emit(d, t, kind, stage, desc):
        t = t[:12]
        desc = desc.replace("\t", " ")
        ev.append("%.3f\t%s\t%s\t%s\t%s\t%s" % (epoch(d, t), d, t, kind, stage, desc))

    def side(rows, d, t, src, a, b):
        t = t[:12]
        rows.append("%.3f\t%s\t%s\t%s\t%s\t%s" % (epoch(d, t), d, t, src, a, b))

    def dt_of(ts):
        t = ts[11:]
        if t.endswith("Z"):
            t = t[:-1]
        return ts[:10], t

    for line in raw:
        # ---- generic facts (any log type)
        m = re.search(r'workspace_name=[^ "]+', line)
        if m:
            setmeta("Workspace", m.group(0)[len("workspace_name="):])
        m = re.search(r'"workspace":\{"id":"ws-[A-Za-z0-9]+","name":"[^"]*"', line)
        if m:
            w = re.sub(r'.*"name":"', "", m.group(0), count=1)
            setmeta("Workspace", re.sub(r'"$', "", w, count=1))
        m = re.search(r"agent_version=[0-9A-Za-z.-]+", line)
        if m:
            setmeta("Agent version", m.group(0)[len("agent_version="):])
        m = re.search(r"agent_pool_id=apool-[A-Za-z0-9]+", line)
        if m:
            setmeta("Agent pool", m.group(0)[len("agent_pool_id="):])
        m = re.search(r"Terraform CLI details: version=[0-9A-Za-z.-]+", line)
        if m:
            setmeta("Terraform CLI", re.sub(r".*version=", "", m.group(0), count=1))
        m = re.search(r"polchk-[A-Za-z0-9]+", line)
        setmeta("Policy check", m.group(0) if m else "")
        setmeta("Organization", sval(line, "organization_name"))
        setmeta("Project", sval(line, "project_name"))

        # ---- audit log (atlas / sidekiq)
        if "[Audit Log]" in line:
            res = sval(line, "resource")
            act = sval(line, "action")
            ts = sval(line, "timestamp")
            if res != "" and ts != "":
                d, t = dt_of(ts)
                rid = sval(line, "resource_id")
                if res == "run":
                    emit(d, t, "STATE", "", act)
                    if act == "create":
                        setmeta("Created by", sval(line, "actor"))
                elif res == "agent":
                    emit(d, t, "AUD", sval(line, "run_stage"), "agent " + act + " " + rid)
                else:
                    emit(d, t, "AUD", "", res + " " + act + " " + rid)
                setmeta("Organization", sval(line, "organization"))
                if '"run":{"id":"' in line:
                    setmeta("Run message", sval(line, "message"))
            continue

        # ---- task-worker (agent steps and task invocation)
        if '"@module":"task-worker' in line:
            stage = sval(line, "workload_type")
            mod = sval(line, "@module")
            msg = sval(line, "@message")
            ts = sval(line, "@timestamp")
            if stage != "":
                setmeta(stage + " ID", sval(line, "workload_id"))
            if mod == "task-worker.router":
                d, t = dt_of(ts)
                emit(d, t, "RTR", stage, "task-worker " + sval(line, "method") + " " + sval(line, "path")
                     + " -> HTTP " + nval(line, "status_code") + " (" + sval(line, "duration") + ")")
            else:
                rest = msg
                m = re.match(r"[0-9]+-[0-9]+-[0-9]+T[0-9:.]+Z ", msg)
                if m:
                    ts = msg[:m.end() - 1]
                    rest = msg[m.end():]
                d, t = dt_of(ts)
                m = re.match(r"\[[A-Z]+\]", rest)
                lvl = m.group(0) if m else ""
                rest = re.sub(r"^\[[A-Z]+\] +", "", rest, count=1)
                if lvl == "[WARN]" or lvl == "[ERROR]":
                    rest = lvl + " " + rest
                emit(d, t, "TW", stage, rest)
            continue

        # ---- policy check result line
        if "Finished policy check" in line:
            m = RE_LEAD.search(line)
            a = (m.group(0) if m else "").split()
            m2 = re.search(r"Finished policy check.*", line)
            emit(part(a, 1), part(a, 2), "POL", "", m2.group(0) if m2 else "")
            continue

        # ---- archivist (log object reads)
        if '"@module":"archivist' in line:
            key = sval(line, "obj.key")
            ts = sval(line, "@timestamp")
            key = re.sub(r"^terraform/logs/", "", key, count=1)
            key = re.sub(r"-.*", "", key, count=1)
            d, t = dt_of(ts)
            side(arch, d, t, "archivist", key + " log read", "")
            continue

        # ---- atlas API request lines
        if '"method":"' in line and '"duration":' in line:
            meth = sval(line, "method")
            p = sval(line, "path")
            st = nval(line, "status")
            du = nval(line, "duration")
            db = nval(line, "db")
            p = re.sub(r"\?.*", "", p, count=1).replace(RID, ":run")
            api.append((meth + " " + p, st, du, db))
            if num(st) >= 400:
                m = RE_LEAD.search(line)
                if m:
                    a = m.group(0).split()
                    side(err, a[0], a[1], "atlas", st, meth + " " + p)
            continue

        # ---- nginx access log
        m = re.search(r'"[A-Z]+ [^ ]+ HTTP/[0-9.]+" [0-9]+', line)
        if m:
            sp = m.group(0).replace('"', "").split(" ")
            meth = part(sp, 1)
            path = part(sp, 2)
            stat = part(sp, 4)
            m = re.search(r"\[[0-9][0-9]/[A-Za-z][A-Za-z][A-Za-z]/[0-9][0-9][0-9][0-9]:[0-9][0-9]:[0-9][0-9]:[0-9][0-9]", line)
            if m:
                nt = m.group(0)
                mi = ("JanFebMarAprMayJunJulAugSepOctNovDec".find(nt[4:7]) + 1 + 2) / 3
                nd = "%s-%02d-%s" % (nt[8:12], mi, nt[1:3])
                nh = nt[13:21]
                path = re.sub(r"\?.*", "", path, count=1)
                if path.startswith("/_archivist/"):
                    side(arch, nd, nh, "nginx", "log object fetch", "")
                    path = "/_archivist/v1/object/<blob>"
                path = path.replace(RID, ":run")
                if num(stat) >= 400:
                    side(err, nd, nh, "nginx", stat, meth + " " + path[:100])
            continue

    return ev, api, err, arch, meta


def sorted_rows(rows):
    """sort -u, then a stable numeric sort on the first field"""
    return sorted(sorted(set(rows)), key=lambda r: num(r.split("\t", 1)[0]))


# ---------------------------------------------------------------- before the run: CLI and API flow
def pre_token_flow(args, RUN, UUID, TOKEN, IP, ACTOR, MODE, QE, WIN):
    """Returns (markdown lines, summary line, start epoch, reason)."""
    needles = [TOKEN, '"remote_ip":"%s"' % IP, '"resource":"configuration_version"',
               '"resource":"run","action":"create"', "Downloading Terraform configuration",
               "Starting download request", "Starting upload request", "send-callback"]
    evt = {}
    cvof = {}
    cvc = {}
    runc = {}
    dl = None
    dle = [None]
    dlcv = [None]
    ups = {}
    upc = {}
    idx = {}
    ruid = [None]; rd = [None]; rt = [None]; rep = [None]; meth = [None]; pth = [None]
    sta = [None]; dur = [None]; tok = [None]; rip = [None]; uas = [None]

    for line in source_lines(args, needles):
        # ---- audit events: remember them by request ID
        if "[Audit Log]" in line:
            res = sval(line, "resource")
            act = sval(line, "action")
            u = uuid_of(line)
            if u == "":
                continue
            rid = sval(line, "resource_id")
            if res == "configuration_version":
                evt[u] = res + " " + act + " " + rid
                cvof[u] = rid
                if act == "create":
                    cvc[u] = rid
            elif res == "run" and act == "create":
                evt[u] = "run create " + rid
                runc[u] = rid
            continue

        # ---- agent: configuration download for this run
        if "Downloading Terraform configuration" in line and '"run_id":"%s"' % RUN in line:
            if dl is None:
                dl = isodt(sval(line, "@timestamp"))
            continue

        # ---- archivist: configuration version slugs
        if '"@module":"archivist' in line:
            key = sval(line, "obj.key")
            if not key.startswith("terraform/slugs/cv-"):
                continue
            cv = re.sub(r"/.*", "", key[len("terraform/slugs/"):], count=1)
            mod = sval(line, "@module")
            msg = sval(line, "@message")
            e = isodt(sval(line, "@timestamp"))
            if mod == "archivist.server.http.download" and msg == "Starting download request":
                dle.append(e)
                dlcv.append(cv)
            if mod == "archivist.server.http.upload" and msg == "Starting upload request" and cv not in ups:
                ups[cv] = e
            if "send-callback" in mod and msg == "success":
                upc[cv] = e
            continue

        # ---- atlas request lines
        if '"method":"' in line and '"duration":' in line:
            m = RE_LEAD_START.match(line)
            x = m.group(0) if m else ""
            u = sval(line, "request_id")
            if x == "" or u == "" or u in idx:
                continue
            a = x.split()
            idx[u] = len(ruid)
            ruid.append(u)
            rd.append(a[0])
            rt.append(a[1])
            rep.append(epoch(a[0], a[1]))
            meth.append(sval(line, "method"))
            pth.append(re.sub(r"\?.*", "", sval(line, "path"), count=1))
            sta.append(nval(line, "status"))
            dur.append(nval(line, "duration"))
            tok.append(sval(line, "token_external_id"))
            rip.append(sval(line, "remote_ip"))
            uas.append(sval(line, "user_agent"))

    n = len(ruid) - 1
    if UUID not in idx:
        return None, None, None, "the request %s that started the run was not found in the log files" % UUID

    # CLI flow: UUID is the run-create request and the sequence ends there.
    # API flow:  UUID is the configuration-version create request and the sequence
    #            ends when TFE queues the run itself (QE).
    api = (MODE == "api")
    c = idx[UUID]
    CE = rep[c]
    lo = CE - WIN * 60
    ET = QE if (api and QE > CE) else CE
    ETS = rt[c] if ET == CE else hms(ET)[:8]

    cut = 0
    cutid = ""
    cutt = ""
    others = []                  # (id, epoch, time) of other runs / configuration versions with this token
    prevrow = set()
    created = cvc if api else runc
    for i in range(1, n + 1):    # in file order
        u = ruid[i]
        if u not in created or u == UUID:
            continue
        if tok[i] != TOKEN or rep[i] > ET or rep[i] < lo:
            continue
        others.append((created[u], rep[i], rt[i]))
        prevrow.add(i)
        if rep[i] <= CE and rep[i] > cut:
            cut = rep[i]
            cutid = created[u]
            cutt = rt[i]
    others.sort(key=lambda o: o[1])      # list the other runs by time (stable)
    start = cut if cut > lo else lo

    # last configuration version created by this token before the run create
    CV = ""
    bep = -1
    bi = 0
    if api:
        CV = cvc.get(UUID, "")
    else:
        for u in cvc:
            if u not in idx:
                continue
            i = idx[u]
            if tok[i] != TOKEN or rep[i] < start or rep[i] > CE:
                continue
            if rep[i] == CE and i > c:
                continue
            if rep[i] > bep or (rep[i] == bep and i > bi):
                bep = rep[i]
                bi = i
                CV = cvc[u]

    # rows that belong to the pre-run sequence
    sel = []
    by = {}
    rx_other = re.compile(r"/(runs|plans|applies|policy-checks|comments|task-stages|run-events|cost-estimates)/")
    for i in range(1, n + 1):
        if rep[i] < start or rep[i] > ET or (not api and rep[i] == CE and i > c) or i in prevrow:
            continue
        if tok[i] == TOKEN:
            if rx_other.search(pth[i]):
                continue
            m = re.search(r"cv-[A-Za-z0-9]+", pth[i])
            p = m.group(0) if m else ""
            if p != "" and CV != "" and p != CV:
                continue
            b = "token"
        elif CV != "" and cvof.get(ruid[i]) == CV:
            b = "config version audit"
        elif tok[i] == "" and rip[i] == IP and (pth[i] == "/.well-known/terraform.json" or pth[i] == "/api/v2/ping"):
            b = "IP only"
        else:
            continue
        sel.append(i)
        by[i] = b
    # calls without a token (.well-known, ping) are only kept up to 5s before the first token call
    ft = -1
    for i in sel:
        if by[i] != "IP only" and (ft < 0 or rep[i] < ft):
            ft = rep[i]
    sel = [i for i in sel if by[i] != "IP only" or (ft >= 0 and rep[i] >= ft - 5)]
    sel.sort(key=lambda i: (rep[i], i))          # by time, then by file order
    ns = len(sel)
    if ns == 0:
        return None, None, None, "no calls found for this token before the run create"
    first = rep[sel[0]]
    total = ET - first
    endword = "run queued" if api else "run create"

    # does the agent confirm the configuration version?
    conf = "unconfirmed (matched by user and time only)"
    why = ""
    if CV == "":
        why = "no configuration version create by this token was found in the window"
    elif dl is None:
        why = 'the agent line "Downloading Terraform configuration" for this run is not in the logs'
    else:
        bk = 0
        bd = 0
        for k in range(1, len(dle)):
            dt = dle[k] - dl
            if 0 <= dt <= 0.5 and (not bk or dt < bd):
                bk = k
                bd = dt
        if not bk:
            why = "no archivist download followed the agent's download line"
        elif dlcv[bk] == CV:
            conf = "confirmed"
            why = 'agent "Downloading Terraform configuration" at %s, archivist "Starting download request" for %s %.0f ms later' % (
                hms(dl), CV, bd * 1000)
        else:
            why = "the agent downloaded " + dlcv[bk] + " at " + hms(dle[bk]) + " instead"

    # ---- markdown section
    out = []
    out.append("## Before the run was created")
    out.append("")
    head = ""
    if api:
        head += "API-driven workflow: there is no run-create request. The client created and uploaded a configuration version and TFE then created and queued the run itself. "
        head += "Calls by `%s` (token `%s`, IP `%s`, user agent `%s`; the user agent is not used for matching) up to the moment TFE queued the run. " % (
            ACTOR, TOKEN, IP, uas[c])
    else:
        head += "Calls by `%s` (token `%s`, IP `%s`) up to the run-create request `%s`. " % (ACTOR, TOKEN, IP, UUID)
    if cut > lo:
        head += "Window: %d min, cut at the previous %s `%s` (%s) by the same token. " % (
            WIN, "configuration version" if api else "run create", cutid, cutt)
    else:
        head += "Window: last %d min. " % WIN
    head += "Atlas logs whole seconds, so gaps are +/- 1s."
    out.append(head)
    out.append("")
    out.append("| Time (UTC) | Gap | Request | Status | Took | Audit event | Matched by |")
    out.append("|---|---|---|---|---|---|---|")
    for j, i in enumerate(sel):
        out.append("| %s | %s | `%s %s` | %s | %.0f ms | %s | %s |" % (
            (rd[i] + " " if rd[i] != rd[c] else "") + rt[i],
            ("+" + fmt(rep[i] - rep[sel[j - 1]])) if j > 0 else "",
            meth[i], pth[i], sta[i], num(dur[i]),
            ("`" + evt[ruid[i]] + "`") if ruid[i] in evt else "", by[i]))
    if api:
        out.append("| %s | +%s | (TFE queues the run) | | | `run queue %s` | audit |" % (
            ETS, fmt(ET - rep[sel[-1]]), RUN))
    out.append("")
    out.append("- **First call to %s:** %s (%s to %s)" % (endword, fmt(total), rt[sel[0]], ETS))
    if CV != "":
        out.append("- **Configuration version:** `%s` - **%s**; %s" % (CV, conf, why))
    else:
        out.append("- **Configuration version:** none found - **%s**; %s" % (conf, why))
    if CV != "" and CV in ups and CV in upc:
        out.append("- **Upload to archivist:** started %s, TFE callback done after %.0f ms" % (
            hms(ups[CV]), (upc[CV] - ups[CV]) * 1000))
    if others:
        w = "- **Warning:** %d other %s(s) were created with this token in the last %d min:" % (
            len(others), "configuration version" if api else "run", WIN)
        for j, (oid, _oe, ot) in enumerate(others):
            w += " `%s` at %s%s" % (oid, ot, "," if j < len(others) - 1 else "")
        w += ". Calls before the latest of them are not listed."
        out.append(w)
    out.append("")

    # ---- summary line and start time
    summ = "- **Before the run was created%s:** %s from first call (%s) to %s, %d calls; configuration version%s **%s**" % (
        " (API-driven)" if api else "", fmt(total), rt[sel[0]], endword, ns,
        (" `" + CV + "`") if CV != "" else "", conf)
    return out, summ, first, ""


# ---------------------------------------------------------------- before the run: VCS flow
def pre_vcs(args, RUN, WIN):
    """Returns (markdown, summary, start, reason, api_handover) where api_handover = (CV, UUID, QE) or None."""
    needles = [RUN, '"resource":"configuration_version"', '"action":"receive_webhook"',
               "Downloading Terraform configuration", "Starting download request",
               "Starting upload request", "send-callback", '"name":"vcs-ingress"', '"path":"/webhooks/vcs/']
    ae = {}
    aa = {}
    cvreq = {}
    wi = {}
    we = [None]; wr = [None]; wev = [None]; wsha = [None]
    qe = 0
    dl = 0
    gmin = {}
    gmax = {}
    clone = {}
    dle = [None]
    dlcv = [None]
    ups = {}
    upc = {}
    hx = {}; hp = {}; hs = {}; hd = {}; hip = {}; hua = {}

    for line in source_lines(args, needles):
        if "[Audit Log]" in line:
            res = sval(line, "resource")
            act = sval(line, "action")
            rid = sval(line, "resource_id")
            e = isodt(sval(line, "timestamp"))
            if res == "configuration_version":
                k = (rid, act)
                if k not in ae:
                    ae[k] = e
                    aa[k] = sval(line, "actor")
                if act == "create":
                    rq = uuid_of(line)
                    if rq != "":
                        cvreq[rid] = rq
            elif res == "vcs-repo" and act == "receive_webhook":
                r = sval(line, "request_id")
                if r not in wi:
                    wi[r] = len(we)
                    we.append(e)
                    wr.append(r)
                    wev.append(sval(line, "event"))
                    wsha.append(sval(line, "sha")[:10])
            elif res == "run" and rid == RUN and act == "queue" and (not qe or e < qe):
                qe = e
            continue

        if "Downloading Terraform configuration" in line and '"run_id":"%s"' % RUN in line:
            e = isodt(sval(line, "@timestamp"))
            if not dl or e < dl:
                dl = e
            continue

        if '"name":"vcs-ingress"' in line and '"@module":"task-worker' in line:
            cv = sval(line, "workload_id")
            msg = sval(line, "@message")
            ts = sval(line, "@timestamp")
            m = re.match(r"[0-9]+-[0-9]+-[0-9]+T[0-9:.]+Z ", msg)
            if m:
                ts = msg[:m.end() - 1]
            e = isodt(ts)
            if cv not in gmin or e < gmin[cv]:
                gmin[cv] = e
            if cv not in gmax or e > gmax[cv]:
                gmax[cv] = e
            if "clone_url=" in msg:
                m = re.search(r"clone_url=[^ ]+", msg)
                clone[cv] = m.group(0)[len("clone_url="):] if m else ""
            continue

        if '"@module":"archivist' in line:
            key = sval(line, "obj.key")
            if not key.startswith("terraform/slugs/cv-"):
                continue
            cv = re.sub(r"/.*", "", key[len("terraform/slugs/"):], count=1)
            mod = sval(line, "@module")
            msg = sval(line, "@message")
            e = isodt(sval(line, "@timestamp"))
            if mod == "archivist.server.http.download" and msg == "Starting download request":
                dle.append(e)
                dlcv.append(cv)
            if mod == "archivist.server.http.upload" and msg == "Starting upload request" and cv not in ups:
                ups[cv] = e
            if "send-callback" in mod and msg == "success":
                upc[cv] = e
            continue

        if '"path":"/webhooks/vcs/' in line and '"duration":' in line:
            m = RE_LEAD_START.match(line)
            x = m.group(0) if m else ""
            r = sval(line, "request_id")
            if x == "" or r == "":
                continue
            a = x.split()
            hx[r] = epoch(a[0], a[1])
            hp[r] = sval(line, "path")
            hs[r] = nval(line, "status")
            hd[r] = nval(line, "duration")
            hip[r] = sval(line, "remote_ip")
            hua[r] = sval(line, "user_agent")

    if not dl:
        return None, None, None, 'no run-create event, and the agent line "Downloading Terraform configuration" for this run is not in the logs (needed to find the VCS configuration version)', None
    bk = 0
    bd = 0
    for k in range(1, len(dle)):
        dt = dle[k] - dl
        if 0 <= dt <= 0.5 and (not bk or dt < bd):
            bk = k
            bd = dt
    if not bk:
        return None, None, None, "no run-create event, and no archivist download of a configuration version followed the agent's download line", None
    CV = dlcv[bk]
    if (CV, "create") not in ae:
        return None, None, None, "no run-create event, and no create event for configuration version %s was found" % CV, None
    cve = ae[(CV, "create")]
    actor = aa[(CV, "create")]

    # A webhook creates the configuration version in a background job (no request ID).
    # A configuration version created by an API request means an API-driven run: hand
    # over to the token-based report, together with the moment TFE queued the run.
    if CV in cvreq:
        return None, None, None, "", (CV, cvreq[CV], int(qe))

    nw = len(we) - 1
    # webhook: the last one received up to 5s before the configuration version was created
    bw = 0
    for i in range(1, nw + 1):
        if we[i] <= cve and we[i] >= cve - 5 and (not bw or we[i] > we[bw]):
            bw = i
    lo = (qe if qe else cve) - WIN * 60
    others = []
    for i in range(1, nw + 1):
        if i != bw and we[i] >= lo and we[i] <= (qe if qe else cve):
            others.append((we[i], wev[i]))
    others.sort()                        # by time, then by event name (file order differs between systems)

    rows = []        # (epoch, precise, step, detail)
    if bw:
        r = wr[bw]
        if r in hx:
            rows.append((hx[r], 0, "Webhook received", "`POST %s` -> %s, %.0f ms, from %s (%s)" % (
                hp[r], hs[r], num(hd[r]), hip[r], hua[r])))
        rows.append((we[bw], 0, "Audit: vcs-repo receive_webhook", "event `%s`, commit `%s`, request `%s`" % (
            wev[bw], wsha[bw], r)))
    if (CV, "fetching") in ae:
        rows.append((ae[(CV, "fetching")], 0, "Audit: configuration_version fetching", "`" + CV + "`"))
    rows.append((cve, 0, "Audit: configuration_version create", "`%s` by `%s`" % (CV, actor)))
    if CV in gmin:
        rows.append((gmin[CV], 1, "Agent job vcs-ingress", "clone `%s`, package and hand over; done %.1fs later" % (
            clone.get(CV, "?"), gmax[CV] - gmin[CV])))
    if CV in ups:
        rows.append((ups[CV], 1, "Archivist upload of the configuration",
                     ("TFE callback done after %.0f ms" % ((upc[CV] - ups[CV]) * 1000)) if CV in upc else ""))
    if (CV, "uploaded") in ae:
        rows.append((ae[(CV, "uploaded")], 0, "Audit: configuration_version uploaded", "`" + CV + "`"))
    if qe:
        rows.append((qe, 0, "Audit: run queue", "`" + RUN + "` created and queued"))
    rows.sort(key=lambda r: r[0])          # stable
    first = rows[0][0]
    total = rows[-1][0] - first

    def clock(e, prec):
        return hms(e) if prec else hms(e)[:8]

    out = []
    out.append("## Before the run was created")
    out.append("")
    out.append("VCS workflow: no run-create request exists. A webhook creates a configuration version and TFE queues the run when the agent has cloned and uploaded the repository. Linked through configuration version `" + CV + "`. Audit events and atlas lines have whole-second times, so gaps are +/- 1s.")
    out.append("")
    out.append("| Time (UTC) | Gap | Step | Detail |")
    out.append("|---|---|---|---|")
    for j, (e, prec, step, detail) in enumerate(rows):
        out.append("| %s | %s | %s | %s |" % (
            clock(e, prec), ("+" + fmt(e - rows[j - 1][0])) if j > 0 else "", step, detail))
    out.append("")
    out.append("- **%s to %s:** %s (%s to %s)" % (
        "Webhook" if bw else "First event", "run queued" if qe else "last event", fmt(total),
        clock(rows[0][0], rows[0][1]), clock(rows[-1][0], rows[-1][1])))
    out.append('- **Configuration version:** `%s` - **confirmed**; agent "Downloading Terraform configuration" at %s, archivist "Starting download request" for %s %.0f ms later' % (
        CV, hms(dl), CV, bd * 1000))
    if bw:
        out.append("- **Webhook:** matched by time only; no log line holds both the webhook and the configuration version, so the push that created it is the last one received within 5s before the create.")
    else:
        out.append("- **Webhook:** none found in the 5s before the configuration version was created (is the VCS actor's create from a manual run or a different trigger?).")
    if others:
        w = "- **Warning:** %d other webhook(s) were received in the last %d min before the run was queued:" % (len(others), WIN)
        for j, (oe, oev) in enumerate(others):
            w += " `%s` at %s%s" % (oev, clock(oe, 0), "," if j < len(others) - 1 else "")
        w += "."
        out.append(w)
    out.append("")
    summ = "- **Before the run was created (VCS webhook):** %s from %s to %s; configuration version `%s` **confirmed**" % (
        fmt(total), "webhook" if bw else "first event", "run queued" if qe else "last event", CV)
    return out, summ, first, "", None


# ---------------------------------------------------------------- main
def main(argv):
    if argv and argv[0] == "--help":
        usage(0)
    WIN = "15"
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--":
            i += 1
            break
        if len(a) < 2 or a[0] != "-":
            break
        j = 1
        while j < len(a):
            ch = a[j]
            if ch == "w":
                if j + 1 < len(a):
                    WIN = a[j + 1:]
                elif i + 1 < len(argv):
                    i += 1
                    WIN = argv[i]
                else:
                    usage(1)
                break
            elif ch == "h":
                usage(0)
            else:
                usage(1)
            j += 1
        i += 1
    args = argv[i:]

    if WIN == "" or not WIN.isdigit() or not WIN.isascii() or WIN == "0":
        sys.stderr.write("error: -w needs a whole number of minutes (got '%s')\n" % WIN)
        return 1
    WIN = int(WIN)
    if len(args) < 1:
        usage(1)
    RUN = args[0]
    args = args[1:]
    if not RUN.startswith("run-"):
        sys.stderr.write("warning: '%s' does not look like a run ID (run-XXXXXXXXXXXXXXXX)\n" % RUN)

    # ---- collect: every line that mentions the run ID, exact duplicates removed
    stdin_mode = False
    if args:
        raw_lines = source_lines(args, [RUN])
    elif not sys.stdin.isatty():
        stdin_mode = True
        data = sys.stdin.buffer.read()
        raw_lines = (RE_PREFIX.sub("", ln, count=1) for ln in file_lines(io.BytesIO(data)) if RUN in ln)
    else:
        args = ["."]
        raw_lines = source_lines(args, [RUN])
    raw = sorted(set(raw_lines))          # byte order, like `sort -u` with LC_ALL=C
    if not raw:
        sys.stderr.write("error: no lines containing '%s' were found\n" % RUN)
        return 1

    ev, api_rows, err_rows, arch_rows, meta = extract(raw, RUN)
    ev_sorted = sorted_rows(ev)
    if not ev_sorted:
        sys.stderr.write("error: lines were found for '%s' but none could be parsed as run events\n" % RUN)
        return 1

    # ---- before the run
    pre_md = []
    pre_sum = ""
    pre_start = ""
    skip_reason = ""
    if stdin_mode:
        skip_reason = "the input was read from stdin; run the script on the raw log files or directory to get this section"
    else:
        UUID = ""
        for ln in raw:
            if '"resource":"run","action":"create"' in ln and RUN in ln:
                m = re.match(r".*\[([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\] \[Audit Log\]", ln)
                if m:
                    UUID = m.group(1)
                    break
        MODE = "cli"
        QE = 0
        if UUID == "":
            # no run-create event: a VCS (webhook) run or an API-driven run
            md, sm, st, reason, handover = pre_vcs(args, RUN, WIN)
            if reason:
                skip_reason = reason
            elif handover:
                _cv, UUID, QE = handover
                MODE = "api"
            else:
                pre_md, pre_sum, pre_start = md, sm, st
        if UUID != "":
            reqline = ""
            for ln in source_lines(args, [UUID]):
                if '"duration":' in ln:
                    reqline = ln
                    break
            m = re.match(r'.*"token_external_id":"([^"]+)"', reqline)
            TOKEN = m.group(1) if m else ""
            m = re.match(r'.*"remote_ip":"([^"]+)"', reqline)
            IP = m.group(1) if m else ""
            m = re.match(r'.*"user":"([^"]+)"', reqline)
            ACTOR = m.group(1) if m else ""
            if TOKEN == "":
                skip_reason = "the request that started the run (ID %s) was not found in the input, or it was made without an API token" % UUID
            else:
                md, sm, st, reason = pre_token_flow(args, RUN, UUID, TOKEN, IP, ACTOR or "unknown", MODE, QE, WIN)
                if reason:
                    skip_reason = reason
                else:
                    pre_md, pre_sum, pre_start = md, sm, st
    if skip_reason:
        pre_md = ["## Before the run was created", "", "_Not available: %s._" % skip_reason, ""]
        pre_sum = ""
        pre_start = ""

    # ---------------------------------------------------------------- report
    out = []
    out.append("# Run timing: `%s`" % RUN)
    out.append("")
    out.append("| Item | Value |")
    out.append("|---|---|")
    for k in ["Organization", "Project", "Workspace", "Created by", "Run message", "Plan ID", "Apply ID",
              "Policy check", "Terraform CLI", "Agent version", "Agent pool"]:
        if k in meta:
            out.append("| %s | `%s` |" % (k, esc(meta[k])))
    out.append("")

    E = []
    for r in ev_sorted:
        f = r.split("\t")
        f += [""] * (6 - len(f))
        E.append((num(f[0]), f[1], f[2], f[3], f[4], f[5]))
    n = len(E)
    ep = [x[0] for x in E]
    dt = [x[1] for x in E]
    tm = [x[2] for x in E]
    kind = [x[3] for x in E]
    st = [x[4] for x in E]
    desc = [x[5] for x in E]

    def srcname(i):
        s = ("run state" if kind[i] == "STATE" else "audit" if kind[i] == "AUD" else "agent" if kind[i] == "TW"
             else "policy check" if kind[i] == "POL" else "task-worker")
        if st[i] != "":
            s += " (" + st[i] + ")"
        return s

    def tdisp(i):
        return dt[i] + " " + tm[i] if dt[i] != dt[0] else tm[i]

    start = ep[0]
    havecreate = False
    for i in range(n):
        if kind[i] == "STATE" and desc[i] == "create":
            start = ep[i]
            havecreate = True
            break

    endep = start
    endtm = ""
    for i in range(n):
        if kind[i] in ("STATE", "TW") and ep[i] > endep:
            endep = ep[i]
            endtm = tm[i]
    states = [(desc[i], ep[i], dt[i], tm[i]) for i in range(n) if kind[i] == "STATE"]

    # time until the next agent step of the same stage
    has = [False] * n
    dur = [0] * n
    nxt = {}
    for i in range(n - 1, -1, -1):
        if kind[i] == "TW":
            if st[i] in nxt:
                dur[i] = ep[nxt[st[i]]] - ep[i]
                has[i] = True
            nxt[st[i]] = i

    # agent time per stage
    stages = []
    smin = {}; smint = {}; smax = {}; smaxt = {}
    for i in range(n):
        if kind[i] == "TW":
            s = st[i]
            if s not in smin:
                stages.append(s)
                smin[s] = ep[i]
                smint[s] = tm[i]
            smax[s] = ep[i]
            smaxt[s] = tm[i]

    # policy check
    pq = -1
    pf = -1
    for i in range(n):
        if pq < 0 and kind[i] == "AUD" and desc[i].startswith("policy_check queued"):
            pq = i
        if pf < 0 and kind[i] == "POL":
            pf = i

    out.append("## Summary")
    out.append("")
    if states:
        out.append("- **Final run state seen:** `%s` at %s" % (states[-1][0], states[-1][3]))
        if havecreate:
            out.append("- **Total, run create to last run-state/agent event (%s):** %s" % (endtm, fmt(endep - start)))
    if pre_sum:
        out.append(pre_sum)
    if pre_start != "":
        out.append("- **Total, first call before the run to last run-state/agent event:** %s" % fmt(endep - pre_start))
    if pf >= 0:
        r = desc[pf]
        m = re.search(r"Result: .*", r)
        if m:
            r = m.group(0)
        if pq >= 0:
            out.append("- **Policy check:** %s from queued to finished (%s)" % (fmt(ep[pf] - ep[pq]), r))
        else:
            out.append("- **Policy check finished** at %s (%s)" % (tm[pf], r))
    total = endep - start if havecreate else 0
    used = set()
    for k in range(1, 4):
        best = 0
        bi = -1
        for i in range(n):
            if has[i] and i not in used and dur[i] > best:
                best = dur[i]
                bi = i
        if bi < 0:
            break
        used.add(bi)
        if k == 1:
            out.append("- **Longest agent steps:**")
        pct = (", %.0f%% of the run" % (best * 100 / total)) if total > 0 else ""
        out.append("  %d. %s - `%s` (%s)%s" % (k, fmt(best), esc(desc[bi]), "agent" if st[bi] == "" else st[bi], pct))
    out.append("")

    out.extend(pre_md)

    if states:
        out.append("## Run state changes")
        out.append("")
        out.append("| State entered | Time (UTC) | Time in that state |")
        out.append("|---|---|---|")
        for j, (sn, se, sd, stm) in enumerate(states):
            out.append("| `%s` | %s | %s |" % (
                sn, (sd + " " if sd != dt[0] else "") + stm,
                fmt(states[j + 1][1] - se) if j < len(states) - 1 else "(last seen)"))
        out.append("")

    if stages:
        out.append("## Agent time per stage")
        out.append("")
        out.append("| Stage | First agent event | Last agent event | Duration |")
        out.append("|---|---|---|---|")
        for s in stages:
            out.append("| %s | %s | %s | %s |" % ("(unknown)" if s == "" else s, smint[s], smaxt[s], fmt(smax[s] - smin[s])))
        out.append("")

    out.append("## Timeline")
    out.append("")
    out.append("All times UTC. _Elapsed_ is counted from %s. _Step took_ is the time until the next agent event of the same stage." % (
        "run create" if havecreate else "the first event"))
    out.append("")
    out.append("| Time | Elapsed | Step took | Source | Event |")
    out.append("|---|---|---|---|---|")
    for i in range(n):
        out.append("| %s | %s | %s | %s | %s |" % (
            tdisp(i), fmt(ep[i] - start), fmt(dur[i]) if has[i] else "", srcname(i), esc(desc[i])))
    out.append("")

    if api_rows:
        out.append("## TFE API calls for this run")
        out.append("")
        out.append("Response times as logged by atlas (view/db are part of the total). Sorted by slowest call.")
        out.append("")
        out.append("| Request | Calls | Avg | Max | Max DB | Status |")
        out.append("|---|---|---|---|---|---|")
        c = {}
        s = {}
        mx = {}
        dm = {}
        sts = {}
        for k, stat, du, db in api_rows:
            c[k] = c.get(k, 0) + 1
            s[k] = s.get(k, 0) + num(du)
            if num(du) > mx.get(k, 0):
                mx[k] = num(du)
            if num(db) > dm.get(k, 0):
                dm[k] = num(db)
            cur = sts.get(k, "")
            if stat not in cur:                      # awk: index(sts, $2) == 0
                sts[k] = cur + (", " if cur != "" else "") + stat
        rows = []
        for k in c:
            rows.append("%012.2f\t| `%s` | %d | %.0f ms | %.0f ms | %.0f ms | %s |" % (
                mx.get(k, 0), k, c[k], s[k] / c[k], mx.get(k, 0), dm.get(k, 0), sts[k]))
        for r in sorted(rows, reverse=True):
            out.append(r.split("\t", 1)[1])
        out.append("")

    if err_rows:
        out.append("## Responses with status 400 or higher")
        out.append("")
        out.append("| Time (UTC) | Source | Status | Request |")
        out.append("|---|---|---|---|")
        for r in sorted_rows(err_rows):
            f = r.split("\t")
            out.append("| %s %s | %s | %s | `%s` |" % (f[1], f[2], f[3], f[4], f[5]))
        out.append("")

    if arch_rows:
        out.append("## Log reads (archivist / nginx)")
        out.append("")
        out.append("Someone or something reading the plan/apply log while the run was active or afterwards.")
        out.append("")
        out.append("| Source | What | Count | First | Last |")
        out.append("|---|---|---|---|---|")
        order = []
        cnt = {}
        first = {}
        last = {}
        for r in sorted_rows(arch_rows):
            f = r.split("\t")
            k = (f[3], f[4])
            if k not in cnt:
                order.append(k)
                first[k] = f[1] + " " + f[2]
            cnt[k] = cnt.get(k, 0) + 1
            last[k] = f[1] + " " + f[2]
        for k in order:
            out.append("| %s | %s | %d | %s | %s |" % (k[0], k[1], cnt[k], first[k], last[k]))
        out.append("")

    out.append("_Generated by run_timing.sh from %d unique log lines._" % len(raw))

    sys.stdout.buffer.write(("\n".join(out) + "\n").encode("latin-1"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.exit(0)
