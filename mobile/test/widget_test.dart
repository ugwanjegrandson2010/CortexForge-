import 'dart:convert';

import 'package:cortexforge_mobile/api/api_client.dart';
import 'package:cortexforge_mobile/main.dart';
import 'package:cortexforge_mobile/screens/home_screen.dart';
import 'package:cortexforge_mobile/screens/login_screen.dart';
import 'package:cortexforge_mobile/state/app_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

/// A mock client that answers the handful of endpoints the widget tests touch.
http.Client _mockClient({
  bool serverUp = true,
  bool loginSucceeds = true,
}) {
  return MockClient((req) async {
    final path = req.url.path;
    if (path == '/api/health') {
      if (!serverUp) {
        return http.Response(jsonEncode({'error': 'down'}), 503);
      }
      return http.Response(
        jsonEncode({'ok': true, 'version': '1.0.0'}),
        200,
      );
    }
    if (path == '/api/account/login') {
      if (!loginSucceeds) {
        return http.Response(jsonEncode({'error': 'bad credentials'}), 401);
      }
      return http.Response(
        jsonEncode({
          'learner_id': 'sam',
          'api_token': 'tok',
          'session_token': 'sess',
          'display_name': 'Sam',
          'email': 'sam@example.com',
        }),
        200,
      );
    }
    if (path == '/api/session') {
      return http.Response(
        jsonEncode({
          'day': 0.0,
          'n_due': 1,
          'items': [
            {
              'qid': 'q1',
              'style': 'cloze',
              'prompt': 'The Calvin cycle occurs in the ____.',
              'answer': 'stroma',
              'skill_id': 'photo',
            }
          ],
          'forecast': {'mean_retrievability': 0.8, 'due_now': 1},
        }),
        200,
      );
    }
    if (path == '/api/profile') {
      return http.Response(
        jsonEncode({
          'profile': {
            'role': 'Unclassified',
            'study_shape': 'Steady',
            'limits': ['This is not a clinical assessment.'],
            'observations': [],
          },
          'session': {
            'calibration': {'bias': 0.0, 'brier': 0.0, 'n': 0},
            'n_attempts': 0,
          },
        }),
        200,
      );
    }
    if (path == '/api/manifest') {
      return http.Response(
        jsonEncode({
          'mcp': {
            'catalogue': [
              {'key': 'notion', 'name': 'Notion', 'auth': 'oauth'},
            ],
            'core': ['notion'],
          },
        }),
        200,
      );
    }
    return http.Response(jsonEncode({}), 200);
  });
}

Widget _app({bool serverUp = true, bool loginSucceeds = true}) {
  final api = CortexForgeApi(
    baseUrl: 'http://127.0.0.1:8731',
    client: _mockClient(serverUp: serverUp, loginSucceeds: loginSucceeds),
  );
  return CortexForgeApp(state: AppState(api: api));
}

void main() {
  testWidgets('shows the login screen when signed out', (tester) async {
    await tester.pumpWidget(_app());
    await tester.pumpAndSettle();
    expect(find.byType(LoginScreen), findsOneWidget);
    expect(find.text('CortexForge'), findsOneWidget);
    expect(find.text('Sign in'), findsWidgets);
  });

  testWidgets('reports a reachable server', (tester) async {
    await tester.pumpWidget(_app());
    await tester.pumpAndSettle();
    expect(find.textContaining('Server connected'), findsOneWidget);
  });

  testWidgets('reports an unreachable server without crashing', (tester) async {
    await tester.pumpWidget(_app(serverUp: false));
    await tester.pumpAndSettle();
    expect(find.textContaining('No server found'), findsOneWidget);
  });

  testWidgets('signing in moves to the home shell', (tester) async {
    await tester.pumpWidget(_app());
    await tester.pumpAndSettle();

    await tester.enterText(
      find.widgetWithText(TextFormField, 'Email'),
      'sam@example.com',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Password'),
      'password1',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
    await tester.pumpAndSettle();

    expect(find.byType(HomeScreen), findsOneWidget);
    expect(find.text('Sam'), findsWidgets);
  });

  testWidgets('a failed sign-in stays on the login screen', (tester) async {
    await tester.pumpWidget(_app(loginSucceeds: false));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.widgetWithText(TextFormField, 'Email'),
      'sam@example.com',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Password'),
      'wrongpass',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
    await tester.pumpAndSettle();

    expect(find.byType(LoginScreen), findsOneWidget);
    expect(find.byType(HomeScreen), findsNothing);
  });

  testWidgets('validation blocks an empty email', (tester) async {
    await tester.pumpWidget(_app());
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
    await tester.pumpAndSettle();
    expect(find.text('Enter your email'), findsOneWidget);
  });

  testWidgets('local mode signs in without an account', (tester) async {
    await tester.pumpWidget(_app());
    await tester.pumpAndSettle();
    final localButton =
        find.widgetWithText(OutlinedButton, 'Use this device only');
    // The sign-in form is taller than the default 800x600 test viewport, so
    // the local-mode button starts below the fold. Scroll it into view before
    // tapping, otherwise the tap lands outside the render tree.
    await tester.ensureVisible(localButton);
    await tester.pumpAndSettle();
    await tester.tap(localButton);
    await tester.pumpAndSettle();
    expect(find.byType(HomeScreen), findsOneWidget);
  });
}
