# CortexForge Cross-Platform Packaging Strategy

## Architecture Overview

CortexForge is a **local-first, stdlib-only Python application** with a web frontend. Understanding this architecture is critical to every packaging decision:

```
┌─────────────────────────────────────────────────────────────┐
│  CortexForge Runtime                                        │
│                                                             │
│  ┌─────────────────┐    HTTP/JSON     ┌──────────────────┐  │
│  │  Python Backend  │ ◄──────────────► │  Web Frontend    │  │
│  │  (port 8731)    │                  │  (static files)  │  │
│  │  http.server    │                  │  index.html      │  │
│  │  SQLite store   │                  │  app.js          │  │
│  │  Zero deps      │                  │  three.js, gsap  │  │
│  └─────────────────┘                  └──────────────────┘  │
│                                                             │
│  Data: ~/.cortexforge/cortexforge.db                         │
│  Token: per-run bearer token for CSRF protection             │
└─────────────────────────────────────────────────────────────┘
```

**Key implications for packaging:**

1. **No pip dependencies** → the Python runtime is the only external requirement
2. **Web frontend** → can be served from the backend or embedded in a native WebView
3. **SQLite** → file-based, no server needed, works on every platform
4. **127.0.0.1 binding** → app never needs external network access
5. **ThreadingHTTPServer** → lightweight, works in any embedded context

---

## Strategy Summary

| Platform | Approach | Frontend Delivery | Difficulty |
|----------|----------|-------------------|------------|
| Linux | AppImage + deb/rpm | Served by bundled Python | ⭐ Easy |
| macOS | .app bundle + DMG | Served by bundled Python | ⭐ Easy |
| Windows | Portable zip / MSI | Served by bundled Python | ⭐ Easy |
| iOS | Capacitor wrapper | WKWebView loads from local server | ⭐⭐ Medium |
| Android | Capacitor wrapper | WebView loads from local server | ⭐⭐ Medium |

**Universal principle:** The Python backend is the single source of truth on every platform. The frontend is always served by the Python server, never embedded as static assets in a native app. This means:
- One codebase, one build pipeline
- The frontend is a thin client that talks to `http://127.0.0.1:8731`
- On mobile, the Python server runs **on the device** inside the app container

---

## 1. Linux Packaging

### 1.1 Recommended Tool: AppImage (primary) + deb/rpm (distro-native)

**Why AppImage first:**
- Single file, runs anywhere — no root, no dependencies
- No package manager required
- Matches the "local-first, zero-dependency" philosophy
- Users can download and double-click

**Why also deb/rpm:**
- Native integration: auto-start, system tray, file associations
- Distribution through package repositories
- Trust signal for enterprise/education buyers

### 1.2 Build Approach: Bundled Python Runtime

The existing `scripts/build/linux.sh` already implements this. The core strategy:

```
AppDir/
├── usr/
│   ├── bin/
│   │   └── cortexforge          # Shell launcher script
│   ├── lib/
│   │   └── cortexforge/
│   │       ├── python/          # Private Python runtime
│   │       │   ├── bin/python3
│   │       │   └── lib/python3.x/
│   │       ├── cortexforge/     # Application package
│   │       └── web/             # Frontend static files
│   └── share/
│       ├── applications/
│       │   └── cortexforge.desktop
│       └── icons/
│           └── hicolor/256x256/apps/
│               └── cortexforge.svg
└── cortexforge.desktop
```

### 1.3 Step-by-Step Build

```bash
# Prerequisites (on the build machine)
sudo apt install dpkg-dev rpm    # for deb/rpm
# appimagetool downloaded separately

# Build everything
cd /home/labuser/cortexforge
VERSION=1.0.0 bash scripts/build/linux.sh

# Output in dist/:
# cortexforge-1.0.0-linux-x86_64.tar.gz
# cortexforge-1.0.0-x86_64.AppImage
# cortexforge_1.0.0_amd64.deb
# cortexforge-1.0.0-1.x86_64.rpm
# PKGBUILD
# cortexforge.flatpak.yml
```

### 1.4 Critical Build Detail: Base Interpreter Resolution

The single most important detail in the entire Linux build (shared with macOS/Windows):

```python
# WRONG: Inside a virtualenv, this resolves to the venv shim
sys.executable  # → /home/user/.venv/bin/python3

# CORRECT: This resolves to the real base interpreter
sys.base_prefix  # → /usr
```

The build script must use `sys.base_prefix` to locate the stdlib, never `sys.executable` inside a venv. The existing scripts handle this correctly.

### 1.5 Frontend Serving on Linux

The launcher script starts the server and opens the browser:

```sh
#!/bin/sh
# AppDir/usr/bin/cortexforge
HERE="$(cd "$(dirname "$0")/.." && pwd)"
APP="$HERE/lib/cortexforge"
export PYTHONHOME="$APP/python"
export PYTHONPATH="$APP"
PORT="${CORTEXFORGE_PORT:-8731}"
exec "$APP/python/bin/python3" -m cortexforge.server \
    --port "$PORT" --static "$APP/web" "$@"
```

The frontend is **always served by the bundled Python server** at `http://127.0.0.1:8731`. The user opens this URL in their browser.

### 1.6 Auto-Start and System Tray

For desktop integration, add a `.desktop` file and optional autostart:

```ini
# Already in the build: usr/share/applications/cortexforge.desktop
[Desktop Entry]
Type=Application
Name=CortexForge
Comment=Adaptive learning system with honest feedback
Exec=cortexforge
Terminal=true
Categories=Education;Science;
```

For **system tray integration**, the simplest approach is a small Python background process that creates a tray icon using only stdlib (via `tkinter` — but tkinter is stripped from the bundle). The recommended approach:

- Ship a minimal tray script as a separate optional install
- Or rely on the browser-based UI and skip tray integration
- Or use a third-party tool like `snixembed` / `trayicon` on the user's system

### 1.7 Required Configuration Files

| File | Purpose |
|------|---------|
| `AppDir/usr/bin/cortexforge` | Shell launcher |
| `AppDir/usr/share/applications/cortexforge.desktop` | Desktop entry |
| `AppDir/usr/share/icons/.../cortexforge.svg` | App icon |
| `AppDir/cortexforge.desktop` | AppImage desktop entry |
| `AppDir/AppRun` | AppImage entry point (generated by appimagetool) |
| `DEBIAN/control` | Debian package metadata |
| `SPECS/cortexforge.spec` | RPM spec file |

---

## 2. macOS Packaging

### 2.1 Recommended Tool: Native .app Bundle + DMG

**Why not pure Swift:**
- Rewriting the Python backend in Swift is unnecessary — the backend is stdlib Python
- A .app bundle with an embedded Python runtime is fully native
- macOS users expect .app bundles distributed via DMG
- Code signing and notarization work normally

**Why not a Python-based wrapper (like Py2App):**
- Py2App produces bundles that are fragile across macOS versions
- Manual .app construction gives full control over the bundle structure
- Easier to codesign and notarize

### 2.2 Build Approach: .app with Bundled Python

```
CortexForge.app/
├── Contents/
│   ├── MacOS/
│   │   └── CortexForge          # Shell launcher (executable)
│   ├── Resources/
│   │   ├── app/
│   │   │   ├── python/          # Private Python runtime
│   │   │   │   ├── bin/python3
│   │   │   │   └── lib/python3.x/
│   │   │   ├── cortexforge/     # Application package
│   │   │   └── web/             # Frontend static files
│   │   ├── icon.icns            # macOS icon
│   │   └── icon.svg             # Source icon
│   └── Info.plist               # Bundle metadata
```

### 2.3 Step-by-Step Build

```bash
# On macOS (requires Xcode command line tools)
cd /home/labuser/cortexforge
VERSION=1.0.0 bash scripts/build/macos.sh

# With code signing (set env vars first):
CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAM_ID)" \
VERSION=1.0.0 bash scripts/build/macos.sh

# With notarization:
CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAM_ID)" \
APPLE_ID="your@email.com" \
APPLE_TEAM_ID="TEAM_ID" \
APPLE_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx" \
VERSION=1.0.0 bash scripts/build/macos.sh

# Output in dist/:
# CortexForge.app/
# CortexForge-1.0.0-macos.zip
# CortexForge-1.0.0.dmg
```

### 2.4 Info.plist Configuration

The key fields in `Info.plist`:

```xml
<key>CFBundleIdentifier</key>
<string>io.github.ugwanjegrandson2010.cortexforge</string>
<key>CFBundleExecutable</key>
<string>CortexForge</string>
<key>CFBundlePackageType</key>
<string>APPL</string>
<key>LSMinimumSystemVersion</key>
<string>11.0</string>
<key>LSApplicationCategoryType</key>
<string>public.app-category.education</string>
```

### 2.5 Frontend Serving on macOS

Identical to Linux — the bundled Python server serves the frontend:

```sh
#!/bin/sh
# Contents/MacOS/CortexForge
HERE="$(cd "$(dirname "$0")/../Resources/app" && pwd)"
export PYTHONHOME="$HERE/python"
export PYTHONPATH="$HERE"
PORT="${CORTEXFORGE_PORT:-8731}"
exec "$HERE/python/bin/python3" -m cortexforge.server \
    --port "$PORT" --static "$HERE/web" "$@"
```

### 2.6 Code Signing and Notarization

For distribution outside the Mac App Store (direct download):

```bash
# Sign the bundle
codesign --force --deep --options runtime \
    --sign "Developer ID Application: Your Name (TEAM_ID)" \
    CortexForge.app

# Verify
codesign --verify --verbose=2 CortexForge.app

# Create DMG
hdiutil create -volname "CortexForge" -srcfolder CortexForge.app \
    -ov -format UDZO CortexForge-1.0.0.dmg

# Sign the DMG
codesign --force --sign "Developer ID Application: Your Name (TEAM_ID)" \
    CortexForge-1.0.0.dmg

# Notarize (takes several minutes)
xcrun notarytool submit CortexForge-1.0.0.dmg \
    --apple-id "your@email.com" \
    --team-id "TEAM_ID" \
    --password "xxxx-xxxx-xxxx-xxxx" \
    --wait

# Staple the notarization ticket
xcrun stapler staple CortexForge-1.0.0.dmg
```

### 2.7 Native macOS Considerations

- **App Sandbox:** If sandboxed, the app cannot write to `~/.cortexforge/`. Use `~/Library/Application Support/CortexForge/` instead. For non-sandboxed (direct download), the home directory works fine.
- **Hardened Runtime:** Required for notarization. The Python interpreter must be signed with `--options runtime`.
- **Gatekeeper:** Unsigned apps are blocked by default. Code signing is mandatory for distribution.

---

## 3. iOS Packaging

### 3.1 Recommended Tool: Capacitor (WebView Wrapper)

**Why Capacitor over pure Swift:**
- The frontend is a complete web app — rewriting in SwiftUI is a massive effort
- Capacitor wraps the existing web app in a WKWebView
- The Python backend runs **on the device** inside the app's container
- Standard App Store distribution through Xcode

**Why not a pure Python approach (like Kivy/BeeWare):**
- Python iOS apps are fragile, large, and hard to get through App Store review
- Capacitor uses native WKWebView which is well-supported
- The web frontend already works in mobile browsers

### 3.2 Architecture on iOS

```
┌─────────────────────────────────────────┐
│  CortexForge.iOS (Capacitor App)        │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │  WKWebView                       │   │
│  │  Loads http://127.0.0.1:8731     │   │
│  │  (the web frontend)              │   │
│  └──────────────┬───────────────────┘   │
│                 │                        │
│  ┌──────────────▼───────────────────┐   │
│  │  Python Backend (embedded)       │   │
│  │  http.server on port 8731        │   │
│  │  Running in app's file container │   │
│  │  SQLite DB in app's Documents/   │   │
│  └──────────────────────────────────┘   │
│                                         │
│  Bundle ID: io.github.ugwanjegrandson2010.cortexforge │
└─────────────────────────────────────────┘
```

### 3.3 Step-by-Step Build

#### Option A: Capacitor (Recommended)

```bash
# 1. Create Capacitor project
cd /home/labuser/cortexforge/build/mobile
npm init -y
npm install @capacitor/core @capacitor/cli @capacitor/ios

# 2. Configure Capacitor
cat > capacitor.config.json << 'EOF'
{
  "appId": "io.github.ugwanjegrandson2010.cortexforge",
  "appName": "CortexForge",
  "webDir": "www",
  "bundledWebRuntime": false,
  "server": {
    "iosScheme": "https",
    "allowNavigation": ["127.0.0.1", "localhost"]
  },
  "ios": { "contentInset": "always" }
}
EOF

# 3. Copy frontend assets
mkdir -p www
cp /home/labuser/cortexforge/web/* www/

# 4. Add iOS platform
npx cap add ios

# 5. Sync web assets
npx cap sync ios

# 6. Open in Xcode
npx cap open ios

# 7. In Xcode:
#    - Set the Team for signing
#    - Set the Bundle Identifier
#    - Product > Archive
#    - Distribute App > App Store Connect
```

#### Option B: Pure Swift with Embedded Python (Advanced)

This is significantly more complex and generally not recommended unless you have specific requirements that Capacitor cannot meet. It would involve:

1. Compiling Python for iOS (using `python-ios` or a custom build)
2. Embedding the Python framework in the Xcode project
3. Writing a Swift launcher that initializes Python and starts the server
4. Using `WKWebView` to load `http://127.0.0.1:8731`

The complexity is high and the App Store review risk is non-trivial. Capacitor is the pragmatic choice.

### 3.4 iOS-Specific Configuration

#### Info.plist Requirements

```xml
<!-- Required for local network access -->
<key>NSLocalNetworkUsageDescription</key>
<string>CortexForge needs to access the local network to start its learning server.</key>

<!-- Allow cleartext to localhost (required for the HTTP server) -->
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsLocalNetworking</key>
    <true/>
    <key>NSExceptionDomains</key>
    <dict>
        <key>localhost</key>
        <dict>
            <key>NSExceptionAllowsInsecureHTTPLoads</key>
            <true/>
        </dict>
        <key>127.0.0.1</key>
        <dict>
            <key>NSExceptionAllowsInsecureHTTPLoads</key>
            <true/>
        </dict>
    </dict>
</dict>
```

#### Data Storage on iOS

The SQLite database must live in the app's container. The `store.py` module uses `Path.home() / ".cortexforge" / "cortexforge.db"`. On iOS, this maps to the app's Documents directory, which is correct and backed up by iCloud.

If you need to override the database path for iOS, add an environment variable check in the launcher:

```python
# In the iOS launcher, set the db path explicitly:
import os
db_path = os.path.expanduser("~/Library/Application Support/CortexForge/cortexforge.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)
```

### 3.5 App Store Metadata

The existing `mobile.sh` generates comprehensive App Store metadata at `build/ios/APP_STORE_METADATA.md`. Key points:

- **Bundle ID:** `io.github.ugwanjegrandson2010.cortexforge`
- **Category:** Education
- **Age rating:** 4+
- **No IAP, no ads, no analytics**
- **Privacy:** No data collection, no network requests (except localhost)

---

## 4. Android Packaging

### 4.1 Recommended Tool: Capacitor (WebView Wrapper)

**Why Capacitor over Flutter:**
- The frontend is a web app — Flutter would require a complete rewrite
- Capacitor wraps the existing web app in a native WebView
- The Python backend runs **on the device** inside the app container
- Smaller APK/AAB than Flutter (no Flutter engine)

**Why not a pure Python approach (like Kivy/BeeWare/Chaquopy):**
- Kivy doesn't use native UI components
- Chaquopy adds significant complexity and APK size
- Capacitor uses the system WebView which is well-optimized

### 4.2 Architecture on Android

Identical to iOS:

```
┌─────────────────────────────────────────┐
│  CortexForge.apk (Capacitor App)        │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │  WebView                         │   │
│  │  Loads http://127.0.0.1:8731     │   │
│  └──────────────┬───────────────────┘   │
│                 │                        │
│  ┌──────────────▼───────────────────┐   │
│  │  Python Backend (embedded)       │   │
│  │  http.server on port 8731        │   │
│  │  SQLite DB in app's files dir    │   │
│  └──────────────────────────────────┘   │
│                                         │
│  Package: io.github.ugwanjegrandson2010.cortexforge │
└─────────────────────────────────────────┘
```

### 4.3 Step-by-Step Build

```bash
# 1. Set up Android SDK
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$PATH:$ANDROID_HOME/tools:$ANDROID_HOME/platform-tools

# 2. Create Capacitor project (same as iOS)
cd /home/labuser/cortexforge/build/mobile
npm init -y
npm install @capacitor/core @capacitor/cli @capacitor/android

# 3. Configure Capacitor
cat > capacitor.config.json << 'EOF'
{
  "appId": "io.github.ugwanjegrandson2010.cortexforge",
  "appName": "CortexForge",
  "webDir": "www",
  "bundledWebRuntime": false,
  "server": {
    "androidScheme": "https",
    "allowNavigation": ["127.0.0.1", "localhost"]
  },
  "android": { "allowMixedContent": false }
}
EOF

# 4. Copy frontend assets
mkdir -p www
cp /home/labuser/cortexforge/web/* www/

# 5. Add Android platform
npx cap add android

# 6. Sync web assets
npx cap sync android

# 7. Build release AAB
cd android
./gradlew bundleRelease

# Output: app/build/outputs/bundle/release/app-release.aab
# Upload to Google Play Console
```

### 4.4 Android-Specific Configuration

#### AndroidManifest.xml

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="io.github.ugwanjegrandson2010.cortexforge">

    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>

    <application
        android:allowBackup="false"
        android:fullBackupContent="false"
        android:dataExtractionRules="@xml/data_extraction_rules"
        android:networkSecurityConfig="@xml/network_security_config"
        android:usesCleartextTraffic="false">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:launchMode="singleTask">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>
```

#### Network Security Config

```xml
<!-- res/xml/network_security_config.xml -->
<network-security-config>
    <!-- Cleartext permitted ONLY to loopback where the server listens -->
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="false">127.0.0.1</domain>
        <domain includeSubdomains="false">localhost</domain>
    </domain-config>
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors>
            <certificates src="system"/>
        </trust-anchors>
    </base-config>
</network-security-config>
```

### 4.5 Play Store Metadata

The existing `mobile.sh` generates comprehensive Play Store metadata at `build/android/PLAY_STORE_METADATA.md`. Key points:

- **Package:** `io.github.ugwanjegrandson2010.cortexforge`
- **Category:** Education
- **Content rating:** Everyone
- **No ads, no IAP**
- **Data safety:** No data collection, no sharing

---

## 5. Windows Packaging

### 5.1 Recommended Tool: Portable Zip (primary) + MSI (installer)

**Why portable zip first:**
- No admin rights required
- No registry modifications
- Matches the "local-first" philosophy
- Users can put it anywhere

**Why also MSI:**
- Native installer experience
- Add/Remove Programs integration
- Enterprise deployment via Group Policy

### 5.2 Build Approach: Bundled Python Runtime

```
CortexForge/
├── CortexForge.bat               # CMD launcher
├── CortexForge.ps1               # PowerShell launcher
├── README.txt
├── app/
│   ├── cortexforge/              # Application package
│   └── web/                      # Frontend static files
└── python/                       # Private Python runtime
    ├── python.exe
    ├── *.dll
    └── Lib/                      # Standard library
```

### 5.3 Step-by-Step Build

```bash
# On Windows (Git Bash / MSYS2) or under Wine on Linux
cd /home/labuser/cortexforge
VERSION=1.0.0 bash scripts/build/windows.sh

# Output in dist/:
# CortexForge-1.0.0-windows-x64.zip    (portable)
# CortexForge-1.0.0-x64.msi            (installer, if WiX available)
```

### 5.4 Windows-Specific Details

#### Runtime Resolution

On Windows, `sys.base_prefix` typically resolves to `C:\Users\<user>\AppData\Local\Programs\Python\Python3xx`. The build script must resolve symlinks and copy the real files:

```bash
# The base interpreter, not a venv shim
PYBIN="$(command -v python || command -v python3)"
BASEPREFIX="$("$PYBIN" -c 'import sys;print(sys.base_prefix)')"
BASEBIN="$BASEPREFIX/python.exe"
```

#### DLL Dependencies

Windows requires the Python DLLs to be alongside the executable:

```bash
PYEXE_DIR="$(dirname "$BASEBIN")"
cp "$PYEXE_DIR"/*.dll "$PKG/python/" 2>/dev/null || true
cp "$PYEXE_DIR/python"*.exe "$PKG/python/" 2>/dev/null || true
```

#### Windows Launcher

```bat
@echo off
setlocal
set HERE=%~dp0
set PYTHONHOME=%HERE%python
set PYTHONPATH=%HERE%app
if "%CORTEXFORGE_PORT%"=="" set CORTEXFORGE_PORT=8731
"%HERE%python\python.exe" -m cortexforge.server --port %CORTEXFORGE_PORT% --static "%HERE%app\web" %*
endlocal
```

### 5.5 MSI Installer (WiX)

If WiX Toolset is available, the build script generates an MSI using `heat` (harvesting) + `candle` (compilation) + `light` (linking):

```bash
# The WiX workflow:
heat dir "CortexForge" -cg AppFiles -gg -g1 -sfrag -srd \
    -dr INSTALLFOLDER -var var.SourceDir -out files.wxs
candle -dSourceDir="CortexForge" -out product.wixobj product.wxs
candle -dSourceDir="CortexForge" -out files.wixobj files.wxs
light -out "CortexForge-1.0.0-x64.msi" product.wixobj files.wixobj
```

### 5.6 Auto-Start on Windows

For auto-start, the installer can create a registry entry or a Startup folder shortcut:

```powershell
# PowerShell: create Startup shortcut
$startup = [Environment]::GetFolderPath('Startup')
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut(
    "$startup\CortexForge.lnk")
$shortcut.TargetPath = "%LOCALAPPDATA%\CortexForge\CortexForge.bat"
$shortcut.Save()
```

---

## 6. Cross-Cutting Concerns

### 6.1 Bundling the Python Runtime

Every platform shares the same fundamental approach:

| Step | Detail |
|------|--------|
| 1. Resolve base interpreter | `sys.base_prefix`, never `sys.executable` in a venv |
| 2. Copy stdlib | `<prefix>/lib/python3.x/` (Linux/macOS), `<prefix>/Lib/` (Windows) |
| 3. Strip unused modules | Remove `test/`, `idlelib/`, `tkinter/`, `turtledemo/`, `ensurepip/` |
| 4. Copy interpreter binary | `python3` (Linux/macOS), `python.exe` + DLLs (Windows) |
| 5. Smoke test | `PYTHONHOME=<bundle> <bundle>/bin/python3 -c 'import encodings, sqlite3, http.server'` |
| 6. Copy application | `src/cortexforge/` and `web/` |

### 6.2 Frontend Delivery

**Every platform uses the same strategy:** the Python server serves the frontend at `http://127.0.0.1:8731`. The user's browser (or WebView) is the client.

This means:
- No separate frontend build step
- No CDN or external hosting
- Works offline
- One codebase for all platforms

### 6.3 Data Storage

SQLite database location per platform:

| Platform | Default Path | Override |
|----------|-------------|----------|
| Linux | `~/.cortexforge/cortexforge.db` | `--db` flag or `CORTEXFORGE_DB` env var |
| macOS | `~/.cortexforge/cortexforge.db` | Same |
| Windows | `%USERPROFILE%\.cortexforge\cortexforge.db` | Same |
| iOS | App's Documents directory (via `~/Library/`) | Hardcoded in launcher |
| Android | App's files directory (via `~/`) | Hardcoded in launcher |

### 6.4 Security Model

The security model is identical across all platforms:

1. Server binds to `127.0.0.1` only
2. Per-run bearer token required for all mutating endpoints
3. CSP headers on every response
4. Host header validation (DNS rebinding protection)
5. Request body size caps
6. Static file path traversal protection

No platform-specific security changes are needed.

---

## 7. Build Pipeline

### 7.1 Unified Build Script

```bash
#!/usr/bin/env bash
# scripts/build-all.sh — build all platform targets

VERSION="${VERSION:-1.0.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo "==> Building CortexForge $VERSION for all platforms"

# Linux (always works on Linux)
bash scripts/build/linux.sh

# macOS (only on macOS)
if [[ "$(uname)" == "Darwin" ]]; then
    bash scripts/build/macos.sh
else
    echo "==> Skipping macOS build (not on macOS)"
fi

# Windows (works under Wine)
if command -v wine >/dev/null 2>&1; then
    bash scripts/build/windows.sh
else
    echo "==> Skipping Windows build (wine not available)"
fi

# Mobile scaffolds (works anywhere with Node)
if command -v npm >/dev/null 2>&1; then
    bash scripts/build/mobile.sh
else
    echo "==> Skipping mobile build (npm not available)"
fi

echo "==> All builds complete. Artifacts in dist/:"
ls -lh dist/
```

### 7.2 CI/CD Integration

For automated builds, use GitHub Actions:

```yaml
# .github/workflows/build.yml
name: Build All Platforms
on:
  push:
    tags: ['v*']

jobs:
  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: sudo apt-get install -y dpkg-dev rpm
      - run: VERSION=${GITHUB_REF#v} bash scripts/build/linux.sh

  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: VERSION=${GITHUB_REF#v} bash scripts/build/macos.sh

  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - shell: bash
        run: VERSION=${GITHUB_REF#v} bash scripts/build/windows.sh
```

---

## 8. Testing the Packages

### 8.1 Smoke Test Checklist

Every artifact must pass:

- [ ] The bundled interpreter starts (`import encodings, sqlite3, http.server`)
- [ ] The server binds to `127.0.0.1:8731`
- [ ] The frontend loads in a browser
- [ ] The API responds to `/api/health`
- [ ] A token is printed on startup
- [ ] The database file is created
- [ ] All static assets (JS, CSS, fonts) load

### 8.2 Platform-Specific Tests

| Platform | Test |
|----------|------|
| Linux | Double-click .deb → app appears in menu → starts |
| macOS | Double-click .app → Gatekeeper passes → starts |
| Windows | Unzip → double-click .bat → starts |
| iOS | Install via TestFlight → app launches → WebView loads |
| Android | Install APK → app launches → WebView loads |

---

## 9. Existing Scripts Reference

The repository already contains build scripts that implement this strategy:

| Script | Platform | Status |
|--------|----------|--------|
| `scripts/build/linux.sh` | Linux (AppImage, deb, rpm, Flatpak, tarball) | ✅ Complete |
| `scripts/build/macos.sh` | macOS (.app, DMG, zip) | ✅ Complete |
| `scripts/build/windows.sh` | Windows (zip, MSI) | ✅ Complete |
| `scripts/build/mobile.sh` | iOS + Android (Capacitor scaffold) | ✅ Complete |

All scripts:
- Use `sys.base_prefix` for correct runtime resolution
- Include fatal smoke tests before producing artifacts
- Support environment variable overrides for version and paths
- Skip optional steps gracefully when tools are unavailable

---

## 10. File Inventory

### Configuration Files Required

```
cortexforge/
├── pyproject.toml                          # Package metadata (exists)
├── scripts/
│   ├── build/
│   │   ├── linux.sh                        # Linux build (exists)
│   │   ├── macos.sh                        # macOS build (exists)
│   │   ├── windows.sh                      # Windows build (exists)
│   │   └── mobile.sh                       # Mobile build (exists)
│   └── build-all.sh                        # Unified build (to create)
├── docs/
│   └── PACKAGING.md                        # This document
└── .github/
    └── workflows/
        └── build.yml                       # CI/CD pipeline (to create)
```

### Files Generated at Build Time

| Artifact | Generated By |
|----------|-------------|
| `dist/cortexforge-*.tar.gz` | `linux.sh` |
| `dist/cortexforge-*.AppImage` | `linux.sh` + `appimagetool` |
| `dist/cortexforge_*.deb` | `linux.sh` + `dpkg-deb` |
| `dist/cortexforge-*.rpm` | `linux.sh` + `rpmbuild` |
| `dist/PKGBUILD` | `linux.sh` |
| `dist/cortexforge.flatpak.yml` | `linux.sh` |
| `dist/CortexForge.app/` | `macos.sh` |
| `dist/CortexForge-*.dmg` | `macos.sh` + `hdiutil` |
| `dist/CortexForge-*-macos.zip` | `macos.sh` |
| `dist/CortexForge-*-windows-x64.zip` | `windows.sh` |
| `dist/CortexForge-*-x64.msi` | `windows.sh` + WiX |
| `build/mobile/ios/` | `mobile.sh` + Capacitor |
| `build/mobile/android/` | `mobile.sh` + Capacitor |
