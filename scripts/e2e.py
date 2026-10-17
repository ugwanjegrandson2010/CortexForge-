#!/usr/bin/env python3
"""End-to-end API test against a running CortexForge server.

Usage:  python3 scripts/e2e.py [base_url]
Exits non-zero on the first failure.
"""

import json
import sys
import urllib.error
import urllib.request

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


def main():
    print(f"E2E against {BASE}\n")

    print("[1] liveness and manifest")
    st, health = call("GET", "/api/health")
    check("health returns 200", st == 200, st)
    check("health reports ok", health and health.get("ok") is True)
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

    print("\n[11] input validation")
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
