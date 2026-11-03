#!/usr/bin/env python3
#
# run_summary.py - summary (markdown) of all Terraform Enterprise runs in a set of log files
#
# Python version of run_summary.sh. It gives the same report (byte for byte) and needs
# only Python 3 and its standard library.
#
# Usage:
#   ./run_summary.py [--full | --errors] [file-or-dir ...]   > run_summary.md
#   grep -h run- * | ./run_summary.py [--full | --errors]    > run_summary.md
#
#   (default)  Only the summary: number of runs, runs and percentage per status, and
#              the split per workflow. The size does not depend on the number of runs.
#   --full     Everything: also one row per run, the run IDs without a status, the runs
#              that need attention (errored, waiting, running) and other observations.
#              With thousands of runs this is a long report.
#   --errors   Like --full, but the run table and the "runs that need attention" list only
#              have the runs that ended in an error (errored, canceled, discarded). Planned,
#              applying, planning, queued and pending runs count as alright. The counts
#              in the summary still cover all runs. The run IDs without a status are
#              only in --full.
#   -h, --help Show this text.
#
# Input can be raw log files or directories (searched recursively), or pre-grepped
# lines on stdin. With no arguments and a terminal on stdin the current directory
# is searched. Output goes to stdout; times are UTC as found in the logs.
# Files ending in .md, .sh or .py are skipped.
#
# The report shows how many runs there are, how many (and what percentage) ended in
# each status, a split per workflow (CLI / API-driven / VCS / UI) and, with --full, one row per run
# (with organization name and ID, workspace name and ID).
# Use run_timing.py <run-id> (or run_timing.sh) for the timing details of a single run.
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
import fnmatch
import io
import os
import re
import sys

SKIP_NAMES = ("*.md", "*.sh", "*.py")     # reports and scripts can sit next to the logs

# Lines with a run ID, the "POST /api/v2/runs" request lines (user agent), errored
# audit events and git "fatal:" lines (why a configuration version failed).
PAT = re.compile(r'run-[A-Za-z0-9]{16}|"path":"/api/v2/runs"|"action":"errored"|[|] fatal:|'
                 r'"resource":"configuration_version","action":"(create|uploaded)"')
RUNID16 = re.compile(r'run-[A-Za-z0-9]{16}')

LABELS = ["applied", "errored", "canceled", "discarded", "plan only (speculative)",
          "planned (waiting for confirmation)", "applying (running)", "planning (running)",
          "queued (waiting for an agent)", "pending (waiting for a previous run or its approval)"]
SHORT = ["applied", "errored", "canceled", "discarded", "plan only", "planned", "applying",
         "planning", "queued", "pending"]
WORKFLOWS = ["CLI", "API-driven", "VCS", "UI", "API client"]


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


def ep(s):
    """'YYYY-MM-DD HH:MM:SS' -> epoch"""
    a = s.split()
    return epoch(part(a, 1), part(a, 2))


def isostr(ts):
    """'2026-11-02T10:22:44.123Z' -> '2026-11-02 10:22:44'"""
    return ts[:19].replace("T", " ", 1)


def clk(e):
    """time of day of an epoch"""
    s = e - 86400 * int(e / 86400)
    h = int(s / 3600)
    m = int((s % 3600) / 60)
    return "%02d:%02d:%02d" % (h, m, s - h * 3600 - m * 60)


def esc(s):
    return s.replace("|", "\\|")


def pct(n, t):
    return "%.1f%%" % (n * 100 / t) if t > 0 else "-"


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


def main(argv):
    full = False
    errors = False
    args = []
    i = 0
    while i < len(argv):             # options may stand anywhere on the command line
        a = argv[i]
        if a == "--full":
            full = True
        elif a == "--errors":
            full = True
            errors = True
        elif a in ("-h", "--help"):
            usage(0)
        elif a == "--":
            args.extend(argv[i + 1:])
            break
        elif a.startswith("-") and len(a) >= 2:
            sys.stderr.write("error: unknown option '%s' (try --help)\n" % a)
            return 1
        else:
            args.append(a)
        i += 1

    stdin_mode = False
    stdin_data = b""
    if not args:
        if not sys.stdin.isatty():
            stdin_mode = True
            stdin_data = sys.stdin.buffer.read()
        else:
            args = ["."]

    def all_lines():
        if stdin_mode:
            yield from file_lines(io.BytesIO(stdin_data))
            return
        for p in input_files(args):
            try:
                with open(p, "rb") as fh:
                    yield from file_lines(fh)
            except OSError:
                continue

    # ---------------------------------------------------------------- collect + time span
    # First and last timestamp over ALL lines of the input (not only the run lines), so
    # the report can tell how old the last event of a running run is.
    span_a = re.compile(r"20[0-9][0-9]-[0-9][0-9]-[0-9][0-9][T ][0-9][0-9]:[0-9][0-9]:[0-9][0-9]")
    span_b = re.compile(r"[A-Z]+ 20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]")
    raw = set()
    span_lo = ""
    span_hi = ""
    span_n = 0
    for line in all_lines():
        span_n += 1
        t = ""
        if span_a.match(line):
            t = line[:19]
        else:
            t = sval(line, "@timestamp")
            if t == "":
                m = span_b.match(line)
                if m:
                    t = line[m.end() - 19:m.end()]
        if t != "":
            t = isostr(t)
            if span_lo == "" or t < span_lo:
                span_lo = t
            if span_hi == "" or t > span_hi:
                span_hi = t
        if PAT.search(line):
            raw.add(line)

    if not any(RUNID16.search(ln) for ln in raw):
        sys.stderr.write("error: no run IDs (run-XXXXXXXXXXXXXXXX) were found in the input\n")
        return 1
    lines = sorted(raw)          # byte order, like `sort -u` with LC_ALL=C

    if stdin_mode:
        nfiles = "input from stdin"
    else:
        count = 0
        for a in args:
            if os.path.isdir(a):
                for _dp, _dn, fns in os.walk(a):
                    count += sum(1 for f in fns if not skipped(f)
                                 and not os.path.islink(os.path.join(_dp, f)))
            elif os.path.isfile(a) and not os.path.islink(a) and not skipped(a):
                count += 1
        nfiles = "%d file(s)" % count

    # ---------------------------------------------------------------- extract
    re_runid = re.compile(r"run-[A-Za-z0-9]+")
    re_wsid = re.compile(r"ws-[A-Za-z0-9]+")
    re_reqid = re.compile(r"\[([0-9a-f-]+)\] \[Audit Log\]")
    re_wsurl = re.compile(r'/workspaces/([^/ "?]+)/runs/(run-[A-Za-z0-9]+)')
    re_handling = re.compile(r"Handling run: run_id=(run-[A-Za-z0-9]+)")
    re_wsname = re.compile(r'workspace_name=([^ "]+)')
    re_lead = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")
    re_getrun = re.compile(r"/api/v2/runs/run-[A-Za-z0-9]+")

    def shown(s):
        """show the date only when it differs from the first day of the logs"""
        if span_lo != "" and s[:10] == span_lo[:10]:
            return s[11:]
        return s

    seen = set()
    order = []
    cnt = {}
    wsi = {}                  # run -> workspace ID
    aep = {}                  # (run, action) -> first epoch
    fe = {}; fs = {}          # first event: epoch, text
    le = {}; ls = {}          # last event
    actors = {}
    orgn = {}; orgi = {}
    runreq = {}
    cverr = {}; cvorder = []
    cvhook = set(); chlist = []
    upl = {}; uplstr = {}; cvorgn = {}; cvorgi = {}
    intr = {}
    wsn = {}
    wsr = {}
    cvwhy = {}
    ua = {}
    pc = {}
    pf = {}

    for line in lines:
        # ---- every run ID on the line (run- + 16 characters; "run-events" etc. are shorter)
        firstrid = ""
        nvr = 0
        for m in re_runid.finditer(line):
            rid_ = m.group(0)
            if len(rid_) == 20:
                if rid_ not in seen:
                    seen.add(rid_)
                    order.append(rid_)
                cnt[rid_] = cnt.get(rid_, 0) + 1
                if firstrid == "":
                    firstrid = rid_
                    nvr = 1
                elif rid_ != firstrid:
                    nvr = 2

        # ---- workspace ID (ws- + 16 characters): only from a line with one run ID and one workspace ID
        if nvr == 1 and "ws-" in line and firstrid not in wsi:
            wid = ""
            nws = 0
            for m in re_wsid.finditer(line):
                x = m.group(0)
                if len(x) == 19:
                    if wid == "":
                        wid = x
                    elif x != wid:
                        nws = 2
            if wid != "" and nws == 0:
                wsi[firstrid] = wid

        # ---- audit log (atlas / sidekiq / sidekiq-critical)
        if "[Audit Log]" in line:
            res = sval(line, "resource")
            act = sval(line, "action")
            rid = sval(line, "resource_id")
            ts = sval(line, "timestamp")
            if ts == "":
                continue
            st = isostr(ts)
            if res == "run" and rid.startswith("run-"):
                e = ep(st)
                k = (rid, act)
                if k not in aep or e < aep[k]:
                    aep[k] = e
                if rid not in fe or e < fe[rid]:
                    fe[rid] = e
                    fs[rid] = st
                if rid not in le or e > le[rid]:
                    le[rid] = e
                    ls[rid] = st
                actors[rid] = actors.get(rid, "") + "|" + sval(line, "actor")
                if rid not in orgn and sval(line, "organization") != "":
                    orgn[rid] = sval(line, "organization")
                    orgi[rid] = sval(line, "organization_id")
                if act == "create":
                    m = re_reqid.search(line)
                    if m and m.group(1) != "":
                        runreq[rid] = m.group(1)
            elif res == "configuration_version" and act == "errored":
                if rid not in cverr:
                    cverr[rid] = st
                    cvorder.append(rid)
            elif res == "configuration_version" and act == "create" and "-webhooks-" in sval(line, "actor"):
                if rid not in cvhook:
                    cvhook.add(rid)
                    chlist.append(rid)
            elif res == "configuration_version" and act == "uploaded":
                e = ep(st)
                if rid not in upl or e < upl[rid]:
                    upl[rid] = e
                    uplstr[rid] = st
                    cvorgn[rid] = sval(line, "organization")
                    cvorgi[rid] = sval(line, "organization_id")
            continue

        # ---- agent was told to shut down while working on a run
        if "Received interrupt, shutting down" in line:
            r = sval(line, "run_id")
            ts = sval(line, "@timestamp")
            if r != "" and ts != "":
                e = ep(isostr(ts))
                if r not in intr or e < intr[r]:
                    intr[r] = e
            continue

        # ---- workspace name
        if "Handling run: run_id=" in line:
            m = re_handling.search(line)
            r = m.group(1) if m else ""
            m = re_wsname.search(line)
            w = m.group(1) if m else ""
            if r != "" and w != "":
                wsn[r] = w
            continue

        # ---- workspace from the UI page URL (nginx Referer), also known for runs that never ran
        m = re_wsurl.search(line)
        if m and m.group(2) not in wsr:
            wsr[m.group(2)] = m.group(1)

        # ---- why a configuration version failed (vcs-ingress job)
        if "| fatal:" in line:
            cv = sval(line, "workload_id")
            if cv.startswith("cv-") and cv not in cvwhy:
                cvwhy[cv] = re.sub(r"^ *\| *", "", sval(line, "@message"), count=1)
            continue

        # ---- atlas request lines
        if '"method":"' in line and '"duration":' in line:
            meth = sval(line, "method")
            p = sval(line, "path")
            if meth == "POST" and p == "/api/v2/runs":
                ua[sval(line, "request_id")] = sval(line, "user_agent")
                continue
            if meth == "GET" and re_getrun.fullmatch(p):
                rid = p[13:]
                m = re_lead.search(line)
                if m:
                    pc[rid] = pc.get(rid, 0) + 1
                    e = ep(m.group(0))
                    if rid not in pf or e < pf[rid]:
                        pf[rid] = e

    # ---------------------------------------------------------------- classify
    def hasact(rid, a):
        return (rid, a) in aep

    def statuscode(rid):
        if hasact(rid, "applied"):
            return 1
        if hasact(rid, "errored"):
            return 2
        if hasact(rid, "canceled") or hasact(rid, "force_canceled"):
            return 3
        if hasact(rid, "discarded"):
            return 4
        if hasact(rid, "finished"):
            return 5
        if hasact(rid, "applying") or hasact(rid, "confirmed") or hasact(rid, "apply"):
            return 7
        if hasact(rid, "planned"):
            return 6
        if hasact(rid, "planning"):
            return 8
        return 9

    def shortst(c):
        return "planned" if c == 6 else "applying" if c == 7 else "planning" if c == 8 else "queued"

    n2i = {}
    i2n = {}

    def wsof(rid):
        if rid in wsn:
            return wsn[rid]
        if rid in wsr:
            return wsr[rid]
        if rid in wsi and wsi[rid] in i2n:
            return i2n[wsi[rid]]
        return ""

    def wsidof(rid):
        """workspace ID of a run: from its own lines, else from another run with the same workspace name"""
        if rid in wsi:
            return wsi[rid]
        nm = wsof(rid)
        if nm != "" and nm in n2i:
            return n2i[nm]
        return ""

    def dash(x):
        return "-" if x == "" else x

    lastlog = ep(span_hi) if span_hi != "" else 0
    # workspace name <-> ID pairs known from runs that have both (names are unique in an organization)
    for rid in order:
        nm = wsn[rid] if rid in wsn else (wsr[rid] if rid in wsr else "")
        if nm != "" and rid in wsi:
            n2i[nm] = wsi[rid]
            i2n[wsi[rid]] = nm

    # ---- pending runs that never got a queue event: a VCS configuration version (created by
    # a webhook user and uploaded) with no run starting within a few seconds after the upload.
    # Normal VCS runs are queued in the same second as the upload. Such a run is created but
    # blocked, typically by an earlier run of the workspace that waits for a confirm.
    fsec = {}
    for rid in order:
        if rid in fe and not hasact(rid, "create"):
            fsec[fe[rid]] = fsec.get(fe[rid], 0) + 1
    claimed = set()
    blocks = {}
    pend = []                      # (cv, run id label, workspace, blocking run)
    for cv in chlist:
        if cv not in upl:
            continue
        u = upl[cv]
        if any(fsec.get(u + d, 0) > 0 for d in range(-2, 11)):
            continue
        # the run ID is only known from page requests after the upload: used as a label only
        best = ""
        bp = 0
        for rid in order:
            if (rid not in fe and rid in pf and rid not in claimed and u <= pf[rid] <= u + 600
                    and (best == "" or pf[rid] < bp)):
                best = rid
                bp = pf[rid]
        if best != "":
            claimed.add(best)
        label = best if best != "" else "(run ID not in the logs)"
        ows = wsof(best) if best != "" else ""
        # blocking run: latest run of the same workspace, started before, that has not finished
        blk = ""
        bt = 0
        if ows != "":
            for rid in order:
                if rid in fe and fe[rid] < u and statuscode(rid) >= 6 and wsof(rid) == ows and fe[rid] >= bt:
                    blk = rid
                    bt = fe[rid]
        if blk != "":
            blocks[blk] = blocks.get(blk, "") + " `" + label + "`"
        pend.append((cv, label, ows, blk))

    runs = []        # (first epoch, id, workflow, workspace, code, first, last, duration, note, wsid, org, orgid)
    obs = []         # (sort key, text)
    hist = []        # (id, lines, page requests)
    for rid in order:
        if rid in fe:
            code = statuscode(rid)

            # ---- workflow
            if hasact(rid, "create"):
                a = ua.get(runreq.get(rid, ""), "")
                if "go-tfe" in a:
                    wf = "CLI"
                elif "Mozilla" in a:
                    wf = "UI"
                else:
                    wf = "API client"
            elif "-webhooks-" in actors.get(rid, ""):
                wf = "VCS"
            else:
                wf = "API-driven"

            # ---- evidence
            note = ""
            if code == 2 and rid in intr and aep[(rid, "errored")] >= intr[rid]:
                note = "agent interrupted at %s (task-worker), run errored at %s, %s later" % (
                    clk(intr[rid]), clk(aep[(rid, "errored")]), fmt(aep[(rid, "errored")] - intr[rid]))
            elif code == 2 and rid in intr:
                note = "agent interrupted at %s (task-worker)" % clk(intr[rid])
            elif 6 <= code <= 10:
                note = "no later event; last event %s" % clk(le[rid])
                if lastlog > 0:
                    note += ", last log line %s (%s later)" % (clk(lastlog), fmt(lastlog - le[rid]))
                if code == 6:
                    note += "; waiting for a confirm or discard"
            if rid in blocks:
                note = note + ("; " if note != "" else "") + "blocks the pending run" + blocks[rid]
            dur = fmt(le[rid] - fe[rid]) if code <= 5 else "-"
            runs.append((int(fe[rid]), rid, wf, wsof(rid) or "-", code, shown(fs[rid]), shown(ls[rid]),
                         dur, note, dash(wsidof(rid)), dash(orgn.get(rid, "")), dash(orgi.get(rid, ""))))
            if 2 <= code <= 4 or 6 <= code <= 10:
                obs.append((1 if code <= 4 else 2, "- `%s` is %s: %s" % (rid, LABELS[code - 1], note)))
        elif rid not in claimed:
            hist.append((rid, cnt.get(rid, 0), pc.get(rid, 0)))

    for cv, label, ows, blk in pend:
        note = "configuration version `%s` uploaded at %s by a webhook, but no run was queued after it" % (
            cv, clk(upl[cv]))
        if blk != "":
            note += "; the workspace is blocked by `%s` (%s)" % (blk, shortst(statuscode(blk)))
        runs.append((int(upl[cv]), label, "VCS", ows if ows != "" else "-", 10, shown(uplstr[cv]),
                     shown(uplstr[cv]), "-", note, n2i[ows] if ows in n2i else "-",
                     dash(cvorgn[cv]), dash(cvorgi[cv])))
        obs.append((2, "- `%s` is %s: %s" % (label, LABELS[9], note)))

    cvobs = []
    for cv in cvorder:
        cvobs.append("- Configuration version `%s` errored at %s%s. Configuration versions are not counted as runs." % (
            cv, shown(cverr[cv]), ": " + cvwhy[cv] if cv in cvwhy else ""))

    runs.sort(key=lambda r: r[0])                    # stable, like `sort -s -k1,1n`
    obs.sort(key=lambda o: o[0])                     # errors first
    obs_all = [t for _k, t in obs]
    obs_err = [t for k, t in obs if k == 1]

    # ---------------------------------------------------------------- report
    def cell(nm, ident):
        """name (`id`), or only the part that is known"""
        if nm == "-" and ident == "-":
            return "-"
        if ident == "-":
            return nm
        if nm == "-":
            return "`" + ident + "`"
        return nm + " (`" + ident + "`)"

    out = []
    total = len(runs)
    cc = {}
    wc = {}
    wcs = {}
    scs = {}
    for r in runs:
        code = r[4]
        cc[code] = cc.get(code, 0) + 1
        wc[r[2]] = wc.get(r[2], 0) + 1
        wcs[(r[2], SHORT[code - 1])] = wcs.get((r[2], SHORT[code - 1]), 0) + 1
        scs[SHORT[code - 1]] = scs.get(SHORT[code - 1], 0) + 1

    out.append("# Run summary")
    out.append("")
    out.append("Logs read: %s, %d lines, from %s to %s (UTC)." % (
        nfiles, span_n, span_lo if span_lo != "" else "?", span_hi if span_hi != "" else "?"))
    out.append("")
    out.append("## Summary")
    out.append("")
    out.append("- **Runs with a lifecycle in the logs:** %d" % total)
    out.append("")
    if total > 0:
        out.append("| Status | Runs | % |")
        out.append("|---|---|---|")
        for c in range(1, 11):
            if cc.get(c, 0) > 0:
                out.append("| %s | %d | %s |" % (LABELS[c - 1], cc[c], pct(cc[c], total)))
        out.append("| **Total** | **%d** | **100%%** |" % total)
        out.append("")

        out.append("## By workflow")
        out.append("")
        # one column per status that occurs, so every number says what the runs are
        cols = [SHORT[c - 1] for c in range(1, 11) if scs.get(SHORT[c - 1], 0) > 0]
        h = "| Workflow | Runs | % |"
        d = "|---|---|---|"
        for c in cols:
            h += " " + c + " |"
            d += "---|"
        out.append(h)
        out.append(d)
        for w in WORKFLOWS:
            if wc.get(w, 0) > 0:
                r = "| %s | %d | %s |" % (w, wc[w], pct(wc[w], total))
                for c in cols:
                    r += " %d |" % wcs.get((w, c), 0)
                out.append(r)
        r = "| **Total** | **%d** | **100%%** |" % total
        for c in cols:
            r += " **%d** |" % scs[c]
        out.append(r)
        out.append("")
        out.append("Each column is a run status. The workflow is how the run was started: `CLI` = terraform CLI, `VCS` = push or pull request on the connected repository, `API-driven` = an API client uploaded the configuration and TFE created the run, `UI` = started in the web UI.")
        out.append("")

        def run_row(r):
            return "| `%s` | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                r[1], r[2], cell(r[10], r[11]), cell(r[3], r[9]), LABELS[r[4] - 1], r[5], r[6], r[7], esc(r[8]))

        header = "| Run | Workflow | Organization | Workspace | Status | First event | Last event | Duration | Evidence |"
        rule = "|---|---|---|---|---|---|---|---|---|"
        if full and errors:
            bad = [r for r in runs if 2 <= r[4] <= 4]
            out.append("## Runs with an error")
            out.append("")
            out.append("Showing %d of %d runs (errored, canceled or discarded). Left out: runs that are applied, plan only, or still in progress (planned, applying, planning, queued, pending). Sorted by the first event. All times UTC. Audit events have whole-second times. For the details of one run use `run_timing.sh <run-id>`." % (len(bad), total))
            out.append("")
            if not bad:
                out.append("- None. None of the %d runs errored, was canceled or discarded." % total)
            else:
                out.append(header)
                out.append(rule)
                out.extend(run_row(r) for r in bad)
            out.append("")
        elif full:
            out.append("## Runs")
            out.append("")
            out.append("Sorted by the first event. All times UTC. Audit events have whole-second times. For the details of one run use `run_timing.sh <run-id>`.")
            out.append("")
            out.append(header)
            out.append(rule)
            out.extend(run_row(r) for r in runs)
            out.append("")
    else:
        out.append("No run with audit events was found. Are atlas.log, sidekiq.log and sidekiq-critical.log in the input?")
        out.append("")

    if hist and full and not errors:
        out.append("## Run IDs without a status")
        out.append("")
        out.append("These IDs have no create or queue event in the logs, so they are not counted as runs. They are runs from before the logs start, or runs that were only viewed or polled.")
        out.append("")
        out.append("| Run | Lines in the logs | Page requests |")
        out.append("|---|---|---|")
        for rid, n_lines, n_pages in hist:
            out.append("| `%s` | %d | %d |" % (rid, n_lines, n_pages))
        out.append("")

    if full:
        out.append("## Runs that need attention")
        out.append("")
        if errors:
            out.append("Errored, canceled or discarded runs.")
        else:
            out.append("Errored, canceled or discarded runs, and runs that are still waiting or running. Errored runs come first.")
        out.append("")
        shown_obs = obs_err if errors else obs_all
        out.extend(shown_obs if shown_obs else ["- None."])
        out.append("")
        out.append("## Other observations")
        out.append("")
        out.extend(cvobs if cvobs else ["- None."])
        out.append("")
    else:
        out.append("_Short report. Run with `--full` for one row per run, the runs that need attention and other observations._")
        out.append("")
    out.append("_Status is derived from the run audit events (atlas, sidekiq, sidekiq-critical). The workflow is the user agent of the run-create request (CLI = go-tfe, UI = browser); runs without a create event are VCS when a webhook user changed the state, otherwise API-driven. Only runs that were created are counted (a run create or queue event, or for VCS a webhook configuration version that was uploaded without a run being queued: a pending run waiting behind another run)._")
    out.append("")
    out.append("_Generated by run_summary.sh from %d unique log lines._" % len(raw))

    sys.stdout.buffer.write(("\n".join(out) + "\n").encode("latin-1"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.exit(0)
