/// HTTP client for the CortexForge local server.
///
/// The server binds to 127.0.0.1 and requires a per-user API token on every
/// mutating endpoint, sent as the `X-CortexForge-Token` header (the
/// localhost-CSRF guard). The token is held in memory only — never written
/// to disk — matching the web client's policy (PRD NFR-S8).
library;

import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'models.dart';

/// Raised for any non-2xx response or transport failure.
class ApiException implements Exception {
  final int status;
  final String message;
  ApiException(this.status, this.message);

  @override
  String toString() => status == 0 ? message : 'HTTP $status: $message';
}

class CortexForgeApi {
  /// Base URL, e.g. `http://127.0.0.1:8731`.
  final String baseUrl;

  /// Per-user API token. Empty until an account is created or logged into.
  String _token;

  final http.Client _client;
  final Duration timeout;

  CortexForgeApi({
    this.baseUrl = 'http://127.0.0.1:8731',
    String token = '',
    http.Client? client,
    this.timeout = const Duration(seconds: 30),
  })  : _token = token,
        _client = client ?? http.Client();

  String get token => _token;
  bool get hasToken => _token.isNotEmpty;

  set token(String value) => _token = value;

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        if (_token.isNotEmpty) 'X-CortexForge-Token': _token,
      };

  Uri _uri(String path, [Map<String, dynamic>? params]) {
    final qp = <String, String>{};
    params?.forEach((k, v) {
      if (v != null) qp[k] = v.toString();
    });
    return Uri.parse('$baseUrl$path').replace(
      queryParameters: qp.isEmpty ? null : qp,
    );
  }

  Future<Map<String, dynamic>> _get(
    String path, [
    Map<String, dynamic>? params,
  ]) async {
    try {
      final resp = await _client
          .get(_uri(path, params), headers: _headers)
          .timeout(timeout);
      return _decode(resp);
    } on TimeoutException {
      throw ApiException(0, 'Request timed out');
    } on http.ClientException catch (e) {
      throw ApiException(0, e.message);
    }
  }

  Future<Map<String, dynamic>> _post(
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    try {
      final resp = await _client
          .post(
            _uri(path),
            headers: _headers,
            body: jsonEncode(body ?? const {}),
          )
          .timeout(timeout);
      return _decode(resp);
    } on TimeoutException {
      throw ApiException(0, 'Request timed out');
    } on http.ClientException catch (e) {
      throw ApiException(0, e.message);
    }
  }

  Map<String, dynamic> _decode(http.Response resp) {
    final raw = utf8.decode(resp.bodyBytes);
    Map<String, dynamic> json = const {};
    if (raw.isNotEmpty) {
      try {
        final parsed = jsonDecode(raw);
        if (parsed is Map) json = parsed.cast<String, dynamic>();
      } catch (_) {
        json = {'raw': raw};
      }
    }
    if (resp.statusCode >= 200 && resp.statusCode < 300) {
      return json;
    }
    final msg = (json['error'] ?? json['message'] ?? raw).toString();
    throw ApiException(resp.statusCode, msg);
  }

  // --- health & manifest ---------------------------------------------------

  Future<HealthInfo> health() async =>
      HealthInfo.fromJson(await _get('/api/health'));

  Future<Map<String, dynamic>> manifest() => _get('/api/manifest');

  // --- accounts ------------------------------------------------------------

  Future<AccountSession> createAccount({
    required String email,
    required String password,
    required String displayName,
  }) async {
    final j = await _post('/api/account/create', {
      'email': email,
      'password': password,
      'display_name': displayName,
    });
    final session = AccountSession.fromJson(j);
    _token = session.apiToken;
    return session;
  }

  Future<AccountSession> login({
    required String email,
    required String password,
  }) async {
    final j = await _post('/api/account/login', {
      'email': email,
      'password': password,
    });
    final session = AccountSession.fromJson(j);
    _token = session.apiToken;
    return session;
  }

  Future<void> logout(String sessionToken) async {
    await _post('/api/account/logout', {'session_token': sessionToken});
    _token = '';
  }

  // --- onboarding ----------------------------------------------------------

  Future<Map<String, dynamic>> onboardingStart(String learnerId) =>
      _post('/api/onboarding/start', {'learner_id': learnerId});

  Future<Map<String, dynamic>> onboardingNext(String learnerId) =>
      _get('/api/onboarding/next', {'learner_id': learnerId});

  Future<Map<String, dynamic>> onboardingRecord({
    required String learnerId,
    required String probeId,
    required dynamic answer,
  }) =>
      _post('/api/onboarding/record', {
        'learner_id': learnerId,
        'probe_id': probeId,
        'answer': answer,
      });

  Future<Map<String, dynamic>> onboardingFinish(String learnerId) =>
      _post('/api/onboarding/finish', {'learner_id': learnerId});

  // --- sources & generation ------------------------------------------------

  Future<SourceRef> addSource({
    required String learnerId,
    required String text,
    String title = '',
  }) async {
    final j = await _post('/api/source', {
      'learner_id': learnerId,
      'text': text,
      'title': title,
    });
    return SourceRef.fromJson(j);
  }

  Future<GenerateResult> generate({
    required String learnerId,
    String sourceId = '',
    String text = '',
    List<String>? styles,
    int maxPerStyle = 3,
  }) async {
    final body = <String, dynamic>{
      'learner_id': learnerId,
      'max_per_style': maxPerStyle,
    };
    if (sourceId.isNotEmpty) body['source_id'] = sourceId;
    if (text.isNotEmpty) body['text'] = text;
    if (styles != null && styles.isNotEmpty) body['styles'] = styles;
    return GenerateResult.fromJson(await _post('/api/generate', body));
  }

  // --- sessions ------------------------------------------------------------

  Future<SessionData> session(String learnerId, {int limit = 20}) async =>
      SessionData.fromJson(
        await _get('/api/session', {'learner_id': learnerId, 'limit': limit}),
      );

  Future<AttemptResult> attempt({
    required String learnerId,
    required String qid,
    required bool correct,
    int grade = 3,
    double? confidence,
    String skillId = 'general',
    int latencyMs = 0,
    String response = '',
  }) async {
    final body = <String, dynamic>{
      'learner_id': learnerId,
      'qid': qid,
      'correct': correct,
      'grade': grade,
      'skill_id': skillId,
      'latency_ms': latencyMs,
      'response': response,
    };
    if (confidence != null) body['confidence'] = confidence;
    return AttemptResult.fromJson(await _post('/api/attempt', body));
  }

  // --- profile & data rights ----------------------------------------------

  Future<ProfileResponse> profile(String learnerId) async =>
      ProfileResponse.fromJson(
        await _get('/api/profile', {'learner_id': learnerId}),
      );

  Future<Map<String, dynamic>> exportData(String learnerId) =>
      _get('/api/export', {'learner_id': learnerId});

  Future<void> erase(String learnerId) =>
      _post('/api/erase', {'learner_id': learnerId, 'confirm': 'ERASE'});

  // --- MCP -----------------------------------------------------------------

  Future<Map<String, dynamic>> mcpPlan() => _get('/api/mcp/plan');

  Future<List<McpServer>> mcpServers() async {
    final man = await manifest();
    final mcp = (man['mcp'] as Map?)?.cast<String, dynamic>() ?? {};
    final catalogue = mcp['catalogue'];
    final core = (mcp['core'] as List?)?.map((e) => e.toString()).toSet() ?? {};
    if (catalogue is List) {
      return catalogue
          .whereType<Map>()
          .map((e) => McpServer.fromJson({
                ...e.cast<String, dynamic>(),
                'core': core.contains(e['key']?.toString()),
              }))
          .toList(growable: false);
    }
    return const [];
  }

  void dispose() => _client.close();
}
