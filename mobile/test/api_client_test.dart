import 'dart:convert';

import 'package:cortexforge_mobile/api/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  group('CortexForgeApi', () {
    test('health parses the server response', () async {
      final api = CortexForgeApi(
        baseUrl: 'http://127.0.0.1:8731',
        client: MockClient((req) async {
          expect(req.url.path, '/api/health');
          return http.Response(
            jsonEncode({'ok': true, 'version': '1.0.0'}),
            200,
            headers: {'content-type': 'application/json'},
          );
        }),
      );
      final h = await api.health();
      expect(h.ok, isTrue);
      expect(h.version, '1.0.0');
    });

    test('mutating calls send the X-CortexForge-Token header', () async {
      String? seenToken;
      final api = CortexForgeApi(
        baseUrl: 'http://127.0.0.1:8731',
        token: 'tok_123',
        client: MockClient((req) async {
          seenToken = req.headers['X-CortexForge-Token'];
          return http.Response(jsonEncode({'learner_id': 'sam'}), 200);
        }),
      );
      await api.onboardingStart('sam');
      expect(seenToken, 'tok_123');
    });

    test('the token is omitted when unset', () async {
      var hadHeader = true;
      final api = CortexForgeApi(
        baseUrl: 'http://127.0.0.1:8731',
        client: MockClient((req) async {
          hadHeader = req.headers.containsKey('X-CortexForge-Token');
          return http.Response(jsonEncode({'ok': true}), 200);
        }),
      );
      await api.health();
      expect(hadHeader, isFalse);
    });

    test('login stores the returned api token for later calls', () async {
      String? tokenOnSecondCall;
      var calls = 0;
      final api = CortexForgeApi(
        baseUrl: 'http://127.0.0.1:8731',
        client: MockClient((req) async {
          calls++;
          if (calls == 1) {
            return http.Response(
              jsonEncode({
                'learner_id': 'sam',
                'api_token': 'tok_from_login',
                'session_token': 'sess',
              }),
              200,
            );
          }
          tokenOnSecondCall = req.headers['X-CortexForge-Token'];
          return http.Response(jsonEncode({'ok': true}), 200);
        }),
      );
      final session = await api.login(email: 'a@b.c', password: 'password1');
      expect(session.apiToken, 'tok_from_login');
      expect(api.hasToken, isTrue);
      await api.onboardingStart('sam');
      expect(tokenOnSecondCall, 'tok_from_login');
    });

    test('a non-2xx response raises ApiException with the server message',
        () async {
      final api = CortexForgeApi(
        baseUrl: 'http://127.0.0.1:8731',
        token: 'tok',
        client: MockClient((req) async {
          return http.Response(
            jsonEncode({'error': 'missing or invalid token'}),
            401,
          );
        }),
      );
      expect(
        () => api.onboardingStart('sam'),
        throwsA(
          isA<ApiException>()
              .having((e) => e.status, 'status', 401)
              .having((e) => e.message, 'message', 'missing or invalid token'),
        ),
      );
    });

    test('generate sends source_id and max_per_style', () async {
      late Map<String, dynamic> body;
      final api = CortexForgeApi(
        baseUrl: 'http://127.0.0.1:8731',
        token: 'tok',
        client: MockClient((req) async {
          body = jsonDecode(req.body) as Map<String, dynamic>;
          return http.Response(
            jsonEncode({
              'generated': 1,
              'questions': [
                {'qid': 'q1', 'style': 'cloze', 'prompt': 'p', 'answer': 'a'}
              ],
              'provenance': {},
            }),
            200,
          );
        }),
      );
      final result = await api.generate(
        learnerId: 'sam',
        sourceId: 'src-1',
        maxPerStyle: 2,
      );
      expect(body['source_id'], 'src-1');
      expect(body['max_per_style'], 2);
      expect(result.generated, 1);
      expect(result.questions.single.style, 'cloze');
    });

    test('session passes learner_id and limit as query parameters', () async {
      late Uri uri;
      final api = CortexForgeApi(
        baseUrl: 'http://127.0.0.1:8731',
        client: MockClient((req) async {
          uri = req.url;
          return http.Response(jsonEncode({'items': [], 'forecast': {}}), 200);
        }),
      );
      await api.session('sam', limit: 5);
      expect(uri.queryParameters['learner_id'], 'sam');
      expect(uri.queryParameters['limit'], '5');
    });

    test('attempt posts the confidence only when provided', () async {
      late Map<String, dynamic> body;
      final api = CortexForgeApi(
        baseUrl: 'http://127.0.0.1:8731',
        token: 'tok',
        client: MockClient((req) async {
          body = jsonDecode(req.body) as Map<String, dynamic>;
          return http.Response(
            jsonEncode({'p_known': 0.5, 'mastered': false, 'next_due_day': 1}),
            200,
          );
        }),
      );
      await api.attempt(
        learnerId: 'sam',
        qid: 'q1',
        correct: true,
        confidence: 0.9,
      );
      expect(body['confidence'], 0.9);

      await api.attempt(learnerId: 'sam', qid: 'q2', correct: false);
      expect(body.containsKey('confidence'), isFalse);
    });

    test('erase sends the literal ERASE confirmation', () async {
      late Map<String, dynamic> body;
      final api = CortexForgeApi(
        baseUrl: 'http://127.0.0.1:8731',
        token: 'tok',
        client: MockClient((req) async {
          body = jsonDecode(req.body) as Map<String, dynamic>;
          return http.Response(jsonEncode({'erased': 'sam'}), 200);
        }),
      );
      await api.erase('sam');
      expect(body['confirm'], 'ERASE');
    });

    test('mcpServers merges the core flag from the manifest', () async {
      final api = CortexForgeApi(
        baseUrl: 'http://127.0.0.1:8731',
        client: MockClient((req) async {
          return http.Response(
            jsonEncode({
              'mcp': {
                'catalogue': [
                  {'key': 'notion', 'name': 'Notion', 'auth': 'oauth'},
                  {'key': 'obsidian', 'name': 'Obsidian', 'auth': 'none'},
                ],
                'core': ['notion'],
              },
            }),
            200,
          );
        }),
      );
      final servers = await api.mcpServers();
      expect(servers.length, 2);
      expect(servers.firstWhere((s) => s.key == 'notion').core, isTrue);
      expect(servers.firstWhere((s) => s.key == 'obsidian').core, isFalse);
    });
  });
}
