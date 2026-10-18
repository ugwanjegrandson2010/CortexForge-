/// Application state shared across screens.
///
/// Uses Flutter's built-in [ChangeNotifier] so no state-management package is
/// required — keeping the dependency surface to a single HTTP client.
library;

import 'package:flutter/foundation.dart';

import '../api/api_client.dart';
import '../api/models.dart';

enum AuthStatus { signedOut, signedIn }

class AppState extends ChangeNotifier {
  final CortexForgeApi api;

  AuthStatus _authStatus = AuthStatus.signedOut;
  String _learnerId = '';
  String _displayName = '';
  String _email = '';
  String? _sessionToken;

  String _statusMessage = '';
  bool _busy = false;

  AppState({CortexForgeApi? api})
      : api = api ?? CortexForgeApi();

  AuthStatus get authStatus => _authStatus;
  bool get isSignedIn => _authStatus == AuthStatus.signedIn;
  String get learnerId => _learnerId;
  String get displayName => _displayName.isEmpty ? _learnerId : _displayName;
  String get email => _email;
  String? get sessionToken => _sessionToken;
  String get statusMessage => _statusMessage;
  bool get busy => _busy;

  void setStatus(String message) {
    _statusMessage = message;
    notifyListeners();
  }

  void setBusy(bool value) {
    _busy = value;
    notifyListeners();
  }

  Future<void> _run(Future<void> Function() action) async {
    setBusy(true);
    try {
      await action();
    } on ApiException catch (e) {
      setStatus(e.toString());
    } catch (e) {
      setStatus('Unexpected error: $e');
    } finally {
      setBusy(false);
    }
  }

  Future<bool> register({
    required String email,
    required String password,
    required String displayName,
  }) async {
    var ok = false;
    await _run(() async {
      final session = await api.createAccount(
        email: email,
        password: password,
        displayName: displayName,
      );
      _applySession(session);
      ok = true;
    });
    return ok;
  }

  Future<bool> signIn({
    required String email,
    required String password,
  }) async {
    var ok = false;
    await _run(() async {
      final session = await api.login(email: email, password: password);
      _applySession(session);
      ok = true;
    });
    return ok;
  }

  void _applySession(AccountSession session) {
    _learnerId = session.learnerId;
    _displayName = session.displayName;
    _email = session.email;
    _sessionToken = session.sessionToken;
    _authStatus = AuthStatus.signedIn;
    _statusMessage = 'Signed in as ${session.displayName.isEmpty ? session.learnerId : session.displayName}';
    notifyListeners();
  }

  Future<void> signOut() async {
    final st = _sessionToken;
    if (st != null) {
      try {
        await api.logout(st);
      } on ApiException {
        // Logging out locally is enough even if the server call fails.
      }
    }
    _authStatus = AuthStatus.signedOut;
    _learnerId = '';
    _displayName = '';
    _email = '';
    _sessionToken = null;
    api.token = '';
    setStatus('Signed out.');
  }

  /// Sets the learner id directly for a local, account-less session.
  void useLocalLearner(String learnerId) {
    _learnerId = learnerId;
    _authStatus = AuthStatus.signedIn;
    setStatus('Using local learner "$learnerId".');
  }
}
