#!/usr/bin/env bash
# Build the mobile distributions of CortexForge (iOS + Android) via Capacitor.
#
# The mobile app is the same web client wrapped in a native shell. The
# CortexForge server runs on the device (or on a paired desktop) and the
# wrapper points at it.
#
# Produces:
#   build/mobile/ios/App/App.xcworkspace      open in Xcode, archive for App Store
#   build/mobile/android/app/build/outputs/bundle/release/app-release.aab
#
# Requirements: Node 20+, @capacitor/cli, Xcode (iOS), Android SDK (Android).
set -euo pipefail

VERSION="${VERSION:-1.0.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD="$ROOT/build/mobile"
DIST="$ROOT/dist"

echo "==> CortexForge mobile build $VERSION"
rm -rf "$BUILD"; mkdir -p "$BUILD" "$DIST"

# ---------------------------------------------------------------- web assets
WWW="$BUILD/www"
install -d "$WWW"
cp "$ROOT/web/index.html" "$ROOT/web/app.css" "$ROOT/web/app.js" "$WWW/"

# Mobile needs the server address configurable at build time.
cat > "$WWW/config.js" <<'CFG'
// Mobile build configuration. The wrapper reads this to find the server.
window.CORTEXFORGE_CONFIG = {
  // 'local'  -> the server runs on the device (bundled runtime)
  // 'remote' -> the server runs on a paired machine on the LAN
  mode: 'local',
  remoteBase: 'http://127.0.0.1:8731'
};
CFG

# ---------------------------------------------------------------- capacitor
cat > "$BUILD/package.json" <<PKG
{
  "name": "cortexforge-mobile",
  "version": "$VERSION",
  "private": true,
  "description": "CortexForge mobile wrapper",
  "dependencies": {
    "@capacitor/core": "^6.0.0",
    "@capacitor/ios": "^6.0.0",
    "@capacitor/android": "^6.0.0"
  },
  "devDependencies": {
    "@capacitor/cli": "^6.0.0"
  }
}
PKG

cat > "$BUILD/capacitor.config.json" <<'CAP'
{
  "appId": "io.github.ugwanjegrandson2010.cortexforge",
  "appName": "CortexForge",
  "webDir": "www",
  "bundledWebRuntime": false,
  "server": {
    "androidScheme": "https",
    "iosScheme": "https",
    "allowNavigation": ["127.0.0.1", "localhost"]
  },
  "ios": { "contentInset": "always" },
  "android": { "allowMixedContent": false }
}
CAP

echo "==> installing Capacitor"
cd "$BUILD"
if command -v npm >/dev/null 2>&1; then
  npm install --silent --no-audit --no-fund 2>/dev/null || {
    echo "    npm install failed — writing platform scaffolds manually"
  }
else
  echo "    npm not installed — writing platform scaffolds manually"
fi

# ---------------------------------------------------------------- ios scaffold
IOS="$BUILD/ios/App"
install -d "$IOS/App" "$IOS/App/Assets.xcassets/AppIcon.appiconset"
cat > "$IOS/App/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDisplayName</key><string>CortexForge</string>
  <key>CFBundleIdentifier</key><string>io.github.ugwanjegrandson2010.cortexforge</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>UILaunchStoryboardName</key><string>LaunchScreen</string>
  <key>UISupportedInterfaceOrientations</key>
  <array>
    <string>UIInterfaceOrientationPortrait</string>
    <string>UIInterfaceOrientationLandscapeLeft</string>
    <string>UIInterfaceOrientationLandscapeRight</string>
  </array>
  <key>NSAppTransportSecurity</key>
  <dict>
    <key>NSAllowsLocalNetworking</key><true/>
  </dict>
  <key>ITSAppUsesNonExemptEncryption</key><false/>
</dict>
</plist>
PLIST

cat > "$BUILD/ios/APP_STORE_METADATA.md" <<'META'
# App Store Connect metadata — CortexForge

**Bundle ID:** io.github.ugwanjegrandson2010.cortexforge
**Primary category:** Education
**Secondary category:** Productivity
**Age rating:** 4+ (no objectionable content)
**Price:** free, no in-app purchases

## Subtitle (30 chars max)
Measure first. Then learn.

## Promotional text (170 chars max)
Measures how you actually think and behave before it teaches you, then keeps
you at the difficulty where learning is fastest. It will not flatter you.

## Description
CortexForge measures before it teaches.

Most study apps give everyone the same interface and the same difficulty curve,
then praise you for showing up. CortexForge does the opposite. It runs a short
battery of validated behavioural tasks to work out how you actually think, what
you already know, and how well you know what you know — then builds a written
learning contract from the results and holds you to it.

WHAT IT DOES
• Profiles you first: attention, working memory, processing speed, confidence
  calibration, and how you behave in group settings
• Generates questions in 18 styles from your own notes and documents — cloze,
  Socratic, counterexample, steelman, transfer, Feynman, and more
• Schedules review with FSRS, a modern spaced-repetition algorithm
• Keeps you at roughly 85% success, the band where learning is fastest — which
  means you will fail about one item in seven, on purpose
• Tells you when your confidence has drifted from your accuracy
• Tracks your self-reported mental clarity over time, separately from your
  measured performance

WHAT IT WILL NOT DO
• It will not tell you that you are doing great when you are not
• It will not diagnose anything
• It will not claim to make you smarter, prevent dementia, or cure anything
• It will not send your data anywhere. Everything stays on your device

WHO IT IS FOR
People with a specific subject and a reason: a certification with a date, a
field they want to understand properly, or ability they are rebuilding after
illness. It is not for people who want a streak counter.

PRIVACY
No account. No analytics. No network calls except the ones you authorise.
Full export and full erasure are one tap each.

## Keywords (100 chars max)
learning,study,memory,spaced repetition,flashcards,retention,metacognition,notes

## Support URL
https://github.com/ugwanjegrandson2010/cortexforge

## Privacy policy URL
https://github.com/ugwanjegrandson2010/cortexforge/blob/main/PRIVACY.md

## Review notes for Apple
This app collects no data and makes no network requests unless the user
authorises an integration. It contains no account system, no advertising, no
analytics SDK, and no in-app purchases. The cognitive tasks are original
implementations; no copyrighted instrument items are included. The app does
not provide medical advice and states this explicitly in-app.
META

# ---------------------------------------------------------------- android scaffold
AND="$BUILD/android/app/src/main"
install -d "$AND/res/values" "$AND/res/xml"
cat > "$AND/AndroidManifest.xml" <<'MANIFEST'
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="io.github.ugwanjegrandson2010.cortexforge">

    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>

    <application
        android:allowBackup="false"
        android:dataExtractionRules="@xml/data_extraction_rules"
        android:fullBackupContent="false"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:supportsRtl="true"
        android:usesCleartextTraffic="false"
        android:networkSecurityConfig="@xml/network_security_config"
        android:theme="@style/AppTheme">
        <activity
            android:name=".MainActivity"
            android:configChanges="orientation|keyboardHidden|keyboard|screenSize|locale|smallestScreenSize|screenLayout|uiMode"
            android:exported="true"
            android:launchMode="singleTask"
            android:screenOrientation="unspecified">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>
MANIFEST

cat > "$AND/res/xml/network_security_config.xml" <<'NSC'
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <!-- Cleartext is permitted ONLY to the loopback address where the
         bundled server listens. Everything else must be TLS. -->
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
NSC

cat > "$AND/res/xml/data_extraction_rules.xml" <<'DER'
<?xml version="1.0" encoding="utf-8"?>
<data-extraction-rules>
    <cloud-backup>
        <exclude domain="database" path="."/>
        <exclude domain="sharedpref" path="."/>
    </cloud-backup>
    <device-transfer>
        <exclude domain="database" path="."/>
        <exclude domain="sharedpref" path="."/>
    </device-transfer>
</data-extraction-rules>
DER

cat > "$AND/res/values/strings.xml" <<'STR'
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">CortexForge</string>
    <string name="title_activity_main">CortexForge</string>
</resources>
STR

cat > "$BUILD/android/PLAY_STORE_METADATA.md" <<'META'
# Google Play Console metadata — CortexForge

**Application ID:** io.github.ugwanjegrandson2010.cortexforge
**Category:** Education
**Content rating:** Everyone
**Contains ads:** No
**In-app purchases:** No

## Short description (80 chars max)
Measures how you think and behave before it teaches you. Will not flatter you.

## Full description (4000 chars max)
CortexForge measures before it teaches.

Most study apps give everyone the same interface and the same difficulty curve,
then praise you for showing up. CortexForge does the opposite. It runs a short
battery of validated behavioural tasks to work out how you actually think, what
you already know, and how well you know what you know — then builds a written
learning contract from the results and holds you to it.

WHAT IT DOES
• Profiles you first: attention, working memory, processing speed, confidence
  calibration, and how you behave in group settings
• Generates questions in 18 styles from your own notes and documents — cloze,
  Socratic, counterexample, steelman, transfer, Feynman, and more
• Schedules review with FSRS, a modern spaced-repetition algorithm
• Keeps you at roughly 85% success, the band where learning is fastest — which
  means you will fail about one item in seven, on purpose
• Tells you when your confidence has drifted from your accuracy
• Tracks your self-reported mental clarity over time, separately from your
  measured performance

WHAT IT WILL NOT DO
• It will not tell you that you are doing great when you are not
• It will not diagnose anything
• It will not claim to make you smarter, prevent dementia, or cure anything
• It will not send your data anywhere. Everything stays on your device

WHO IT IS FOR
People with a specific subject and a reason: a certification with a date, a
field they want to understand properly, or ability they are rebuilding after
illness. It is not for people who want a streak counter.

PRIVACY
No account. No analytics. No network calls except the ones you authorise.
Full export and full erasure are one tap each.

## Data safety declaration
- Data collected: none
- Data shared: none
- Data encrypted in transit: yes (TLS for any authorised integration)
- Data deletion available: yes, in-app, one tap
- Location: not collected
- Personal info: stored locally only, never transmitted

## Content rating questionnaire answers
- Violence: no
- Sexuality: no
- Language: no
- Controlled substances: no
- Gambling: no
- User-generated content sharing: no
- Health/medical claims: no (the app explicitly disclaims medical use)
META

# ---------------------------------------------------------------- outputs
echo
echo "==> Mobile scaffolds written to $BUILD"
echo
echo "iOS:"
echo "  1. cd $BUILD && npx cap add ios && npx cap sync ios"
echo "  2. open ios/App/App.xcworkspace in Xcode"
echo "  3. Product > Archive > Distribute App > App Store Connect"
echo "  4. Metadata: $BUILD/ios/APP_STORE_METADATA.md"
echo
echo "Android:"
echo "  1. cd $BUILD && npx cap add android && npx cap sync android"
echo "  2. cd android && ./gradlew bundleRelease"
echo "  3. Upload app/build/outputs/bundle/release/app-release.aab to Play Console"
echo "  4. Metadata: $BUILD/android/PLAY_STORE_METADATA.md"
echo
echo "Signing (required before store submission):"
echo "  Android: create a keystore and set signingConfigs in app/build.gradle"
echo "  iOS: configure a distribution certificate and provisioning profile"
