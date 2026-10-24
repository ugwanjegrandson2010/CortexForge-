# CortexForge Mobile

A native Flutter client for the CortexForge adaptive learning server.

The Python server does all the modelling — BKT, FSRS, question generation,
profile synthesis, the honesty validator. This client is a thin, native shell
over that HTTP API, so the same learner state is visible on phone, desktop and
the web without duplicating any logic.

## What it covers

| Surface | Screen |
|---|---|
| Today | Due count, mean retrievability, calibration summary |
| Sources | Paste material, add it, generate questions, inspect provenance |
| Study | One item at a time, confidence rating before feedback, honest verdict |
| Profile | Role, study shape, calibration, behavioural observations with caveats |
| More | Onboarding (13 probes), MCP integrations, settings |

## Design rules carried over from the research

- **Confidence before feedback.** The rating is captured *before* the answer is
  graded, so calibration is a real measurement rather than a memory.
- **No pampering.** Feedback states what was correct or not and why. No praise
  for attendance, no streak-loss theatre.
- **One focal element.** Full-screen item player, no feeds, no badges during a
  session.
- **Honest verdicts.** Session summaries use the server's four bands
  (under-challenged / productive / struggling productively / over-loaded).
- **Token in memory only.** The API token is never written to disk, matching
  the web client and PRD NFR-S8.

## Running it

You need the server running first:

```bash
cd ..                       # the repo root
.venv/bin/python -m cortexforge.server --port 8731
```

Then, with Flutter installed:

```bash
cd mobile
flutter pub get
flutter run                 # pick a device
```

The app looks for the server at `http://127.0.0.1:8731` by default. To point it
elsewhere, change the `baseUrl` passed to `CortexForgeApi` in `lib/main.dart`.

### Building per platform

| Platform | Command | Host required |
|---|---|---|
| Linux desktop | `flutter build linux` | Linux |
| Android | `flutter build apk --release` | any (Android SDK) |
| iOS | `flutter build ios --release --no-codesign` | **macOS + Xcode** |
| iOS archive | `flutter build ipa --release` | **macOS + Xcode** |

iOS builds are macOS-only by design — Flutter gates the `ios`, `ipa` and
`swift-package` subcommands behind `platform.isMacOS`, so they do not exist at
all on Linux or Windows. Nothing in the project configuration can change that;
building or archiving for the App Store needs a Mac.

Both platforms share the bundle ID `com.cortexforge.cortexforge`. iOS forbids
underscores in bundle identifiers, so the ID avoids them — keep it identical
across the two platforms.

The client reaches the server over plain HTTP on loopback. Android gets a
network security config permitting cleartext for `127.0.0.1`/`localhost` only;
iOS gets the matching `NSAllowsLocalNetworking` exemption. Both are scoped to
loopback so no other host is affected.

### Accounts vs local mode

Create an account to get a per-learner API token, or choose **Use this device
only** for a single-learner, account-less setup. Both paths work against the
same local server.

## Tests

```bash
flutter analyze
flutter test
```

The suite covers answer grading and session verdicts, JSON model parsing, the
HTTP client's auth-header behaviour, and the login → home flow as a widget test.

## Layout

```
mobile/
├─ lib/
│  ├─ api/          HTTP client and JSON models
│  ├─ logic/        pure grading/verdict helpers (no Flutter imports)
│  ├─ screens/      one file per surface
│  ├─ state/        AppState (ChangeNotifier — no state package needed)
│  ├─ theme/        Material 3 palette shared with the web client
│  └─ main.dart
└─ test/            unit + widget tests
```

## Dependency footprint

One runtime dependency: `http`. State is Flutter's built-in `ChangeNotifier`,
so there is no provider/riverpod/bloc dependency to keep current.
