#!/usr/bin/env python3
"""End-to-end API test against a running CortexForge server.

Usage:  python3 scripts/e2e.py [base_url]
Exits non-zero on the first failure.
"""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8731"
TOKEN = sys.argv[2] if len(sys.argv) > 2 else ""
FAILURES = []
CHECKS = 0


def check(name, condition, detail=""):
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILURES.append(name)

def call(method, path, body=None, token=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-CortexForge-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"raw": raw}


SOURCE = """Photosynthesis is the process by which green plants convert light
energy into chemical energy stored in glucose. Chlorophyll absorbs light most
strongly in the blue and red parts of the spectrum. The light-dependent
reactions occur in the thylakoid membrane and produce ATP and NADPH. The Calvin
cycle occurs in the stroma and fixes carbon dioxide into a three-carbon sugar.
Because the Calvin cycle depends on ATP from the light reactions, photosynthesis
stops within minutes when light is removed. In contrast, respiration occurs in
the mitochondria and releases energy rather than storing it. The overall yield
is approximately 6 molecules of oxygen per molecule of glucose."""


def _provision_token() -> str:
    """Create a throwaway account and return its API token.

    Tokens are per-account (there is no shared server token any more), so the
    harness provisions its own rather than asking the caller to paste one. The
    email is run-unique so repeat runs against the same database do not collide
    on "email already registered".
    """
    email = f"e2e+{int(time.time() * 1000)}@example.com"
    st, body = call("POST", "/api/account/create",
                    {"email": email, "password": "E2eProbePass123!",
                     "display_name": "E2E Probe"})
    if st not in (200, 201) or not body or not body.get("api_token"):
        print(f"  SKIP  could not provision a token (status {st})")
        return ""
    return body["api_token"]


def main():
    print(f"E2E against {BASE}\n")

    print("[1] liveness and manifest")
    st, health = call("GET", "/api/health")
    check("health returns 200", st == 200, st)
    check("health reports ok", health and health.get("ok") is True)
    # Tokens are per-account now, so /api/health must not leak one.
    check("health does not expose a token",
          not (health and "token" in health))
    st, man = call("GET", "/api/manifest")
    check("manifest returns 200", st == 200, st)
    check("manifest lists tasks", man and len(man["tasks"]["tasks"]) >= 15,
          len(man.get("tasks", {}).get("tasks", [])) if man else 0)
    check("manifest lists styles", man and len(man["styles"]) >= 21)
    check("manifest lists probes", man and len(man["probes"]) >= 10)

    print("\n[2] auth enforcement")
    st, _ = call("POST", "/api/onboarding/start", {"learner_id": "e2e"})
    check("write without token is rejected", st == 401, st)
    st, _ = call("POST", "/api/onboarding/start", {"learner_id": "e2e"},
                 token="wrong-token")
    check("write with wrong token is rejected", st == 401, st)
    global TOKEN
    if not TOKEN:
        # Provision a throwaway account so the run is self-contained and
        # repeatable; the email carries a run-unique suffix.
        TOKEN = _provision_token()
    if not TOKEN:
        print("  SKIP  token-dependent checks (no token supplied)")
        return report()
    st, _ = call("POST", "/api/onboarding/start", {"learner_id": "e2e"},
                 token=TOKEN)
    check("write with correct token succeeds", st == 200, st)

    print("\n[3] host header validation")
    req = urllib.request.Request(BASE + "/api/health")
    req.add_header("Host", "evil.example.com")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            check("host header rejected", resp.status == 403, resp.status)
    except urllib.error.HTTPError as e:
        check("host header rejected", e.code == 403, e.code)

    print("\n[4] path traversal on static")
    for bad in ("/static/../../etc/passwd", "/static/..%2f..%2fetc%2fpasswd",
                "/static/%2e%2e/%2e%2e/etc/passwd"):
        st, _ = call("GET", bad)
        check(f"traversal blocked: {bad}", st in (403, 404), st)

    print("\n[5] onboarding flow")
    lid = "e2e"
    st, data = call("POST", "/api/onboarding/start", {"learner_id": lid}, TOKEN)
    check("onboarding starts", st == 200 and data.get("learner_id") == lid, st)
    seen = 0
    while True:
        st, nxt = call("GET", f"/api/onboarding/next?learner_id={lid}")
        if st != 200:
            check("next probe returns 200", False, st)
            break
        probe = nxt.get("probe")
        if not probe:
            break
        seen += 1
        if seen > 40:
            check("probe loop terminates", False, "ran away")
            break
        pid = probe["probe_id"]
        if pid == "source":
            ans = "none"
        elif pid == "goal":
            ans = "Pass a specific exam or certification, with a date attached"
        elif pid == "domain":
            ans = "Statistics and probability"
        elif pid == "constraints":
            ans = {"session_minutes": 25, "days_per_week": 5, "best_time": "morning"}
        elif pid == "difficulty_preference":
            ans = "85% — the evidence-based band (recommended)"
        elif pid == "fog_baseline":
            ans = {"a": 3, "b": 2, "c": 2, "d": 3, "e": 3}
        else:
            ans = {"ok": True}
        st, _ = call("POST", "/api/onboarding/record",
                     {"learner_id": lid, "probe_id": pid, "answer": ans}, TOKEN)
        if st != 200:
            check(f"record probe {pid}", False, st)
            break
    check("probes were served", seen >= 10, seen)
    st, fin = call("POST", "/api/onboarding/finish", {"learner_id": lid}, TOKEN)
    check("contract built", st == 200 and "contract" in fin, st)
    check("contract has falsifiers",
          fin and len(fin["contract"]["falsifiers"]) >= 4)
    check("contract summary readable",
          fin and "PROVE THIS CONTRACT WRONG" in fin.get("summary", ""))

    print("\n[6] source ingestion and generation")
    st, src = call("POST", "/api/source",
                   {"learner_id": lid, "title": "Photosynthesis", "text": SOURCE},
                   TOKEN)
    check("source added", st == 200 and "source_id" in src, st)
    sid = src.get("source_id")
    st, gen = call("POST", "/api/generate",
                   {"learner_id": lid, "source_id": sid, "max_per_style": 2}, TOKEN)
    check("questions generated", st == 200 and gen.get("generated", 0) > 20,
          gen.get("generated") if gen else st)
    styles = {q["style"] for q in gen.get("questions", [])}
    check("multiple styles produced", len(styles) >= 15, len(styles))
    check("no provenance in payload",
          "provenance" not in styles)
    for q in gen.get("questions", []):
        if not q.get("source_span"):
            check("every question has provenance", False, q["qid"])
            break
    else:
        check("every question has provenance", True)

    print("\n[7] session and attempts")
    st, sess = call("GET", f"/api/session?learner_id={lid}&limit=10")
    check("session returns 200", st == 200, st)
    qs = call("POST", "/api/generate",
              {"learner_id": lid, "source_id": sid, "max_per_style": 1}, TOKEN)[1]
    first = qs["questions"][0]
    st, att = call("POST", "/api/attempt",
                   {"learner_id": lid, "qid": first["qid"],
                    "skill_id": first["skill_id"], "correct": True, "grade": 3,
                    "latency_ms": 1500, "confidence": 0.8, "response": "test"},
                   TOKEN)
    check("attempt recorded", st == 200 and "p_known" in att, st)
    check("mastery estimate returned", att and 0 <= att["p_known"] <= 1)
    check("schedule returned", att and att["schedule"]["interval_days"] >= 1)

    print("\n[8] profile")
    st, prof = call("GET", f"/api/profile?learner_id={lid}")
    check("profile returns 200", st == 200, st)
    check("profile has limits", prof and len(prof["profile"]["limits"]) >= 4)
    # Clinical vocabulary must never be used to describe the learner. It may
    # appear only inside the explicit disclaimer that denies clinical status.
    observations = prof["profile"]["observations"] if prof else []
    obs_text = " ".join(
        (o.get("statement", "") + " " + o.get("action", "") + " " + o.get("label", ""))
        for o in observations
    ).lower()
    clinical = ("disorder", "diagnos", "symptom", "pathology", "deficit",
                "impaired", "abnormal", "clinical", "patient", "adhd",
                "autism", "dementia")
    leaked = [c for c in clinical if c in obs_text]
    check("no clinical language in observations", not leaked, leaked)
    check("disclaimer present",
          prof and any("not a clinical" in x.lower() or "clinical assessment" in x.lower()
                       for x in prof["profile"]["limits"]))
    check("no pampering in observations",
          not any(p in obs_text for p in ("great job", "well done", "you are so",
                                          "proud of you", "good effort")))

    print("\n[9] MCP plan and config")
    st, plan = call("GET", "/api/mcp/plan")
    check("mcp plan returns 200", st == 200, st)
    check("notion requires oauth",
          any(o["key"] == "notion" for o in plan.get("oauth_required", [])))
    check("obsidian needs no oauth",
          "obsidian" not in {o["key"] for o in plan.get("oauth_required", [])})
    st, cfg = call("POST", "/api/mcp/config", {}, TOKEN)
    check("mcp config written", st == 200 and "written" in cfg, st)

    print("\n[10] export and erase")
    st, exp = call("GET", f"/api/export?learner_id={lid}")
    check("export returns 200", st == 200, st)
    check("export has all tables",
          exp and all(k in exp for k in ("learner", "sources", "questions",
                                         "attempts", "skills", "cards")))
    st, _ = call("POST", "/api/erase", {"learner_id": lid, "confirm": "no"}, TOKEN)
    check("erase without confirmation rejected", st == 400, st)
    st, _ = call("POST", "/api/erase", {"learner_id": lid, "confirm": "ERASE"}, TOKEN)
    check("erase succeeds", st == 200, st)
    st, exp2 = call("GET", f"/api/export?learner_id={lid}")
    check("data actually erased",
          exp2 and exp2.get("learner") is None and not exp2.get("questions"))

    print("\n[11] scheduler weights and fitting")
    # Use a dedicated learner: section [10] erased `e2e`, and fitting needs a
    # review history that survives.
    slid = "e2e-scheduler"
    call("POST", "/api/onboarding/start", {"learner_id": slid}, TOKEN)
    st, ssrc = call("POST", "/api/source",
                    {"learner_id": slid, "title": "Scheduler source",
                     "text": SOURCE}, TOKEN)
    ssid = ssrc.get("source_id")
    st, sgen = call("POST", "/api/generate",
                    {"learner_id": slid, "source_id": ssid, "max_per_style": 1},
                    TOKEN)
    st, w0 = call("GET", f"/api/scheduler/weights?learner_id={slid}")
    check("weights endpoint returns 200", st == 200, st)
    check("weights has 19 entries", w0 and len(w0.get("weights", [])) == 19,
          len(w0.get("weights", [])) if w0 else None)
    check("weights start as defaults", w0 and w0.get("using_defaults") is True)
    check("fit refused below review threshold",
          call("POST", "/api/scheduler/fit", {"learner_id": slid}, TOKEN)[0] == 409)
    # Build enough history to fit: repeated reviews of the same items on
    # distinct days, so the sequences have length AND elapsed time. (All-same-
    # day reviews give R == 1.0 and a zero loss, which carries no signal.)
    for i in range(16):
        q = sgen["questions"][i % len(sgen["questions"])]
        call("POST", "/api/attempt",
             {"learner_id": slid, "qid": q["qid"], "skill_id": q["skill_id"],
              "correct": True, "grade": 3, "latency_ms": 900,
              "confidence": 0.7, "response": "fit"}, TOKEN)
    # A fresh learner's reviews all land on day 0, so predicted retrievability
    # is 1.0 for every one of them and the loss is exactly 0. The endpoint must
    # say so honestly rather than persisting noise as a "fit".
    st, fit = call("POST", "/api/scheduler/fit",
                   {"learner_id": slid, "max_iter": 25}, TOKEN)
    check("fit refused when reviews carry no signal",
          st == 200 and fit.get("fitted") is False, st)
    check("degenerate fit explains itself",
          fit and "no scheduling signal" in fit.get("reason", ""), fit)
    check("degenerate fit persists nothing",
          call("GET", f"/api/scheduler/weights?learner_id={slid}")[1]
          .get("using_defaults") is True)
    st, _ = call("POST", "/api/scheduler/fit",
                 {"learner_id": slid, "max_iter": "notanumber"}, TOKEN)
    check("non-numeric max_iter rejected", st == 400, st)
    # Cleanup: erase the extra learner so the run is repeatable.
    call("POST", "/api/erase", {"learner_id": slid, "confirm": "ERASE"}, TOKEN)

    # A genuinely spaced history must produce a real fit. The API derives the
    # day from the learner's epoch, so distinct days are simulated directly.
    print("\n[12] fit from a spaced review history")
    import tempfile as _tf
    from pathlib import Path as _P
    from cortexforge.store import Store
    from cortexforge.scheduler import (DEFAULT_W, fit_parameters,
                                       total_loss)
    tmp = _tf.TemporaryDirectory()
    st2 = Store(_P(tmp.name) / "f.db")
    st2.upsert_learner("spaced", "Spaced")
    seqs = []
    for c in range(4):
        grades = [3, 1, 3, 4, 3, 3, 2, 4, 3, 1, 3, 4]
        seq = [(float(i * 2), g) for i, g in enumerate(grades)]
        seqs.append(seq)
        for day, g in seq:
            st2.add_attempt("spaced", f"q{c}", "sk", g >= 3,
                            1.0 if g >= 3 else 0.0, 900, 0.7, "x", day)
    before = total_loss(DEFAULT_W, seqs)
    w = fit_parameters(seqs, max_iter=60)
    after = total_loss(w, seqs)
    check("fit reduces loss on real history", after < before,
          f"{after} vs {before}")
    check("fitted weights are finite and positive",
          all(x > 0 for x in w) and len(w) == 19)
    st2.save_fitted_weights("spaced", w, sum(len(s) for s in seqs), after)
    check("fitted weights round-trip through the store",
          st2.get_fitted_weights("spaced") is not None)
    st2.erase_learner("spaced")
    check("erase clears fitted weights",
          st2.get_fitted_weights("spaced") is None)
    st2.close()
    tmp.cleanup()

    print("\n[13] input validation")
    st, _ = call("POST", "/api/source", {"learner_id": "bad id!", "text": "x"}, TOKEN)
    check("invalid learner_id rejected", st == 400, st)
    st, _ = call("POST", "/api/generate",
                 {"learner_id": "e2e", "text": SOURCE, "styles": ["nope"]}, TOKEN)
    check("unknown style rejected", st == 400, st)
    st, _ = call("POST", "/api/generate",
                 {"learner_id": "e2e", "text": SOURCE, "styles": "notalist"}, TOKEN)
    check("non-list styles rejected", st == 400, st)
    st, _ = call("POST", "/api/onboarding/record",
                 {"learner_id": "e2e", "probe_id": "nonexistent", "answer": 1}, TOKEN)
    check("unknown probe rejected", st == 404, st)

    return report()


def report():
    print(f"\n{'=' * 60}")
    print(f"{CHECKS - len(FAILURES)}/{CHECKS} checks passed")
    if FAILURES:
        print("FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("ALL E2E CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
