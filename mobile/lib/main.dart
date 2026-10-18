/// CortexForge mobile client entry point.
library;

import 'package:flutter/material.dart';

import 'api/api_client.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'state/app_state.dart';
import 'theme/app_theme.dart';

void main() {
  runApp(const CortexForgeApp());
}

class CortexForgeApp extends StatefulWidget {
  const CortexForgeApp({super.key, this.state, this.baseUrl});

  /// Injectable state for tests.
  final AppState? state;
  final String? baseUrl;

  @override
  State<CortexForgeApp> createState() => _CortexForgeAppState();
}

class _CortexForgeAppState extends State<CortexForgeApp> {
  late final AppState _state;

  @override
  void initState() {
    super.initState();
    _state = widget.state ??
        AppState(
          api: CortexForgeApi(
            baseUrl: widget.baseUrl ?? 'http://127.0.0.1:8731',
          ),
        );
  }

  @override
  void dispose() {
    _state.api.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CortexForge',
      debugShowCheckedModeBanner: false,
      theme: CfTheme.dark(),
      home: AnimatedBuilder(
        animation: _state,
        builder: (context, _) {
          return _state.isSignedIn
              ? HomeScreen(state: _state)
              : LoginScreen(state: _state);
        },
      ),
    );
  }
}
