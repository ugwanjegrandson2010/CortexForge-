#!/usr/bin/env python3
"""Platform and packaging verification.

Checks that every platform claim in the PRD is backed by something that
actually exists on disk and parses. Run from the repo root:

    python3 scripts/test_platforms.py
"""

import json
import os
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILS: list[str] = []
CHECKS = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if ok:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILS.append(name)


def section(title: str) -> None:
    print(f"\n{title}")


# ---------------------------------------------------------------- structure

def test_structure() -> None:
    section("[1] Repository structure")
    required = [
        "pyproject.toml", "README.md", "LICENSE", "run.py",
        "src/cortexforge/__init__.py",
        "src/cortexforge/security.py",
        "src/cortexforge/store.py",
        "src/cortexforge/scheduler.py",
        "src/cortexforge/tracing.py",
        "src/cortexforge/questiongen.py",
        "src/cortexforge/instruments.py",
        "src/cortexforge/profile.py",
        "src/cortexforge/onboarding.py",
        "src/cortexforge/mcp.py",
        "src/cortexforge/server.py",
        "web/index.html", "web/app.css", "web/app.js",
        "tests/test_core.py", "tests/test_security.py",
        "scripts/e2e.py",
        "scripts/build/linux.sh", "scripts/build/macos.sh",
        "scripts/build/windows.sh", "scripts/build/mobile.sh",
        "docs/prd/PRD.md",
    ]
    for r in required:
        check(f"exists: {r}", (ROOT / r).exists())

    research = sorted((ROOT / "docs/research").glob("*.md"))
    check("five research dossiers present", len(research) == 5, len(research))
    total = sum(f.stat().st_size for f in research)
    check("research corpus > 200 KB", total > 200_000, f"{total} bytes")


# ---------------------------------------------------------------- packaging

def test_pyproject() -> None:
    section("[2] Python packaging")
    text = (ROOT / "pyproject.toml").read_text()
    check("declares no runtime dependencies",
          re.search(r"^dependencies = \[\]", text, re.M) is not None)
    check("declares console script",
          "cortexforge = \"cortexforge.server:main\"" in text)
    check("requires-python >= 3.11", ">=3.11" in text)
    check("MIT licence declared", "MIT" in text)
    check("package-dir points at src", '"" = "src"' in text)

    # The package must import with no third-party packages available.
    code = ("import sys; sys.path.insert(0,'src');"
            "import cortexforge, cortexforge.server, cortexforge.security,"
            "cortexforge.store, cortexforge.scheduler, cortexforge.tracing,"
            "cortexforge.questiongen, cortexforge.instruments,"
            "cortexforge.profile, cortexforge.onboarding, cortexforge.mcp;"
            "print('ok')")
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                       capture_output=True, text=True)
    check("all modules import with stdlib only",
          r.returncode == 0 and "ok" in r.stdout, r.stderr[-200:])


# ---------------------------------------------------------------- build scripts

def test_build_scripts() -> None:
    section("[3] Build scripts")
    for name in ("linux", "macos", "windows", "mobile"):
        p = ROOT / f"scripts/build/{name}.sh"
        check(f"{name}.sh exists", p.exists())
        if not p.exists():
            continue
        check(f"{name}.sh is executable",
              bool(p.stat().st_mode & stat.S_IXUSR))
        r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
        check(f"{name}.sh parses", r.returncode == 0, r.stderr[:200])
        text = p.read_text()
        check(f"{name}.sh uses strict mode", "set -euo pipefail" in text)
        check(f"{name}.sh has a version variable", "VERSION=" in text)


def test_linux_targets() -> None:
    section("[4] Linux distribution coverage")
    text = (ROOT / "scripts/build/linux.sh").read_text()
    for fmt, needle in [
        ("portable tarball", ".tar.gz"),
        ("AppImage", "AppImage"),
        (".deb", "dpkg-deb"),
        (".rpm", "rpmbuild"),
        ("Arch PKGBUILD", "PKGBUILD"),
        ("Flatpak", "flatpak"),
    ]:
        check(f"linux.sh produces {fmt}", needle in text)


def test_macos_targets() -> None:
    section("[5] macOS distribution coverage")
    text = (ROOT / "scripts/build/macos.sh").read_text()
    for fmt, needle in [
        (".app bundle", "Info.plist"),
        (".dmg", "hdiutil"),
        ("codesign", "codesign"),
        ("notarisation", "notarytool"),
        ("stapling", "stapler"),
        ("zip", "zip -qry"),
    ]:
        check(f"macos.sh handles {fmt}", needle in text)


def test_windows_targets() -> None:
    section("[6] Windows distribution coverage")
    text = (ROOT / "scripts/build/windows.sh").read_text()
    for fmt, needle in [
        ("portable zip", "windows-x64.zip"),
        ("batch launcher", "CortexForge.bat"),
        ("PowerShell launcher", "CortexForge.ps1"),
        ("MSI via WiX", "candle"),
    ]:
        check(f"windows.sh handles {fmt}", needle in text)


def test_mobile_targets() -> None:
    section("[7] Mobile distribution coverage")
    text = (ROOT / "scripts/build/mobile.sh").read_text()
    for fmt, needle in [
        ("Capacitor config", "capacitor.config.json"),
        ("iOS Info.plist", "Info.plist"),
        ("Android manifest", "AndroidManifest.xml"),
        ("Android network security config", "network_security_config"),
        ("App Store metadata", "APP_STORE_METADATA"),
        ("Play Store metadata", "PLAY_STORE_METADATA"),
        ("Android App Bundle", "bundleRelease"),
    ]:
        check(f"mobile.sh handles {fmt}", needle in text)

    # Mobile security posture
    check("android blocks cleartext except loopback",
          'cleartextTrafficPermitted="false"' in text and
          'cleartextTrafficPermitted="true"' in text)
    check("android disables backup of learner data",
          'android:allowBackup="false"' in text)
    check("android excludes db from cloud backup",
          "<exclude domain=\"database\"" in text)
    check("ios allows only local networking",
          "NSAllowsLocalNetworking" in text)
    check("ios declares no non-exempt encryption",
          "ITSAppUsesNonExemptEncryption" in text)


# ---------------------------------------------------------------- store metadata

def test_store_metadata() -> None:
    section("[8] Store submission metadata")
    mobile = ROOT / "scripts/build/mobile.sh"
    text = mobile.read_text()

    # The metadata must be honest: no medical claims asserted, only disclaimed.
    meta_start = text.find("APP_STORE_METADATA")
    meta_text = text[meta_start:].lower() if meta_start > 0 else ""

    # Phrases that must appear ONLY in a disclaimer context.
    disclaimed = ["prevent dementia", "cure anything", "make you smarter"]
    for phrase in disclaimed:
        if phrase in meta_text:
            idx = meta_text.index(phrase)
            window = meta_text[max(0, idx - 120):idx + 40]
            check(f"'{phrase}' appears only as a disclaimer",
                  "will not" in window or "not claim" in window, window[-80:])
        else:
            check(f"'{phrase}' absent or disclaimed", True)

    check("metadata states no data collected",
          "data collected: none" in meta_text or "no account" in meta_text)
    check("metadata declares no ads",
          "contains ads:** no" in meta_text or "contains ads: no" in meta_text)
    check("metadata declares no IAP",
          "in-app purchases:** no" in meta_text or "in-app purchases: no" in meta_text)
    check("metadata gives a privacy URL", "privacy policy url" in meta_text)
    check("metadata gives review notes",
          "review notes" in meta_text or "data safety declaration" in meta_text)


# ---------------------------------------------------------------- runtime

def test_runtime_portability() -> None:
    section("[9] Runtime portability")
    # The app must not import anything outside the stdlib.
    third_party = ("numpy", "pandas", "scipy", "sklearn", "flask", "django",
                   "fastapi", "requests", "aiohttp", "pydantic")
    offenders: list[str] = []
    for py in (ROOT / "src").rglob("*.py"):
        text = py.read_text()
        for mod in third_party:
            if re.search(rf"^\s*(?:import|from)\s+{mod}\b", text, re.M):
                offenders.append(f"{py.name}:{mod}")
    check("no third-party imports in src", not offenders, offenders)

    # PyYAML must be optional, never required.
    sec = (ROOT / "src/cortexforge/security.py").read_text()
    check("PyYAML import is guarded by try/except",
          "except ImportError" in sec and "import yaml" in sec)

    # No compiled extensions.
    check("no .so/.pyd files in src",
          not list((ROOT / "src").rglob("*.so")) and
          not list((ROOT / "src").rglob("*.pyd")))


def test_server_binding() -> None:
    section("[10] Server binding policy")
    text = (ROOT / "src/cortexforge/server.py").read_text()
    check("default host is loopback", 'default="127.0.0.1"' in text)
    check("non-loopback bind is refused",
          "refusing to bind" in text)
    check("host header allowlist present", "ALLOWED_HOSTS" in text)
    check("bearer token required for writes", "_check_auth" in text)
    check("body size capped", "MAX_BODY_BYTES" in text)


def test_artifact_integrity() -> None:
    section("[11] Build artifact integrity")
    dist = ROOT / "dist"
    if not dist.exists():
        check("dist/ exists (run a build first)", False, "no dist directory")
        return
    artifacts = list(dist.iterdir())
    check("dist/ is non-empty", len(artifacts) > 0, len(artifacts))
    for a in artifacts:
        if a.suffix == ".gz" and a.name.endswith(".tar.gz"):
            try:
                with tarfile.open(a) as tf:
                    names = tf.getnames()
                check(f"{a.name} is a valid tarball", len(names) > 0)
                check(f"{a.name} contains the launcher",
                      any("bin/cortexforge" in n for n in names))
                check(f"{a.name} contains the package",
                      any("cortexforge/server.py" in n for n in names))
                check(f"{a.name} contains the web client",
                      any("web/index.html" in n for n in names))
                # No absolute paths or traversal in the archive.
                bad = [n for n in names if n.startswith("/") or ".." in Path(n).parts]
                check(f"{a.name} has no unsafe member paths", not bad, bad[:3])
            except (tarfile.TarError, OSError) as e:
                check(f"{a.name} opens as tarball", False, str(e))
        elif a.suffix == ".zip":
            try:
                with zipfile.ZipFile(a) as zf:
                    names = zf.namelist()
                check(f"{a.name} is a valid zip", len(names) > 0)
                bad = [n for n in names if n.startswith("/") or ".." in Path(n).parts]
                check(f"{a.name} has no unsafe member paths", not bad, bad[:3])
            except (zipfile.BadZipFile, OSError) as e:
                check(f"{a.name} opens as zip", False, str(e))
        elif a.name == "PKGBUILD":
            text = a.read_text()
            check("PKGBUILD has required fields",
                  all(k in text for k in ("pkgname=", "pkgver=", "pkgrel=",
                                          "arch=", "license=", "package()")))
        elif a.suffix in (".yml", ".yaml"):
            text = a.read_text()
            check(f"{a.name} declares an app-id", "app-id:" in text)
            check(f"{a.name} declares finish-args", "finish-args:" in text)


def test_no_secrets_committed() -> None:
    section("[12] No secrets in the tree")
    patterns = [
        (r"sk-[A-Za-z0-9]{20,}", "OpenAI-style key"),
        (r"ghp_[A-Za-z0-9]{30,}", "GitHub token"),
        (r"AKIA[0-9A-Z]{16}", "AWS key id"),
        (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key"),
        (r"xox[baprs]-[A-Za-z0-9-]{10,}", "Slack token"),
    ]
    hits: list[str] = []
    skip_dirs = {".git", ".venv", "build", "dist", "__pycache__", "node_modules"}
    for p in ROOT.rglob("*"):
        if not p.is_file() or any(d in p.parts for d in skip_dirs):
            continue
        if p.suffix in (".png", ".jpg", ".gz", ".zip", ".db", ".icns"):
            continue
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        for pat, label in patterns:
            if re.search(pat, text):
                hits.append(f"{p.relative_to(ROOT)}: {label}")
    check("no credentials committed", not hits, hits[:5])


def test_gitignore() -> None:
    section("[13] .gitignore coverage")
    gi = ROOT / ".gitignore"
    check(".gitignore exists", gi.exists())
    if gi.exists():
        text = gi.read_text()
        for pat in (".venv", "build/", "dist/", "__pycache__", "*.db",
                    ".cortexforge"):
            check(f".gitignore covers {pat}", pat in text)
        # *.pyc is covered by the *.py[cod] glob; accept either spelling.
        check(".gitignore covers .pyc files",
              "*.pyc" in text or "*.py[cod]" in text)


def main() -> int:
    print("CortexForge platform verification")
    print("=" * 60)
    test_structure()
    test_pyproject()
    test_build_scripts()
    test_linux_targets()
    test_macos_targets()
    test_windows_targets()
    test_mobile_targets()
    test_store_metadata()
    test_runtime_portability()
    test_server_binding()
    test_artifact_integrity()
    test_no_secrets_committed()
    test_gitignore()
    print("\n" + "=" * 60)
    print(f"{CHECKS - len(FAILS)}/{CHECKS} checks passed")
    if FAILS:
        print("FAILED:")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("ALL PLATFORM CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
