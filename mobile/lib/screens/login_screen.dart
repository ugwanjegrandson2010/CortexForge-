/// Sign-in / account-creation screen.
///
/// The server is local-first, so the first thing the client does is confirm it
/// can reach it. Accounts give each learner their own API token; a local mode
/// exists for a single-device setup where an account is not wanted.
library;

import 'package:flutter/material.dart';

import '../state/app_state.dart';
import '../theme/app_theme.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.state});

  final AppState state;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  final _nameCtrl = TextEditingController();
  final _localCtrl = TextEditingController(text: 'local');

  bool _isRegister = false;
  bool _obscure = true;
  bool _checkingServer = true;
  String? _serverVersion;

  @override
  void initState() {
    super.initState();
    _checkServer();
  }

  Future<void> _checkServer() async {
    try {
      final health = await widget.state.api.health();
      setState(() {
        _serverVersion = health.version;
        _checkingServer = false;
      });
    } catch (_) {
      setState(() => _checkingServer = false);
    }
  }

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passwordCtrl.dispose();
    _nameCtrl.dispose();
    _localCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final state = widget.state;
    final ok = _isRegister
        ? await state.register(
            email: _emailCtrl.text.trim(),
            password: _passwordCtrl.text,
            displayName: _nameCtrl.text.trim(),
          )
        : await state.signIn(
            email: _emailCtrl.text.trim(),
            password: _passwordCtrl.text,
          );
    if (!mounted) return;
    if (!ok && state.statusMessage.isNotEmpty) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(state.statusMessage)));
    }
  }

  void _useLocal() {
    final id = _localCtrl.text.trim();
    if (id.isEmpty) return;
    widget.state.useLocalLearner(id);
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text(
                    'CortexForge',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 30,
                      fontWeight: FontWeight.w700,
                      letterSpacing: -0.5,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Measure first. Teach second. Say only what the evidence supports.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: CfColors.textDim, fontSize: 13),
                  ),
                  const SizedBox(height: 24),
                  _ServerStatus(
                    checking: _checkingServer,
                    version: _serverVersion,
                  ),
                  const SizedBox(height: 20),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(18),
                      child: Form(
                        key: _formKey,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Text(
                              _isRegister ? 'Create an account' : 'Sign in',
                              style: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 16),
                            if (_isRegister) ...[
                              TextFormField(
                                controller: _nameCtrl,
                                decoration: const InputDecoration(
                                  labelText: 'Display name',
                                ),
                                validator: (v) => _isRegister &&
                                        (v == null || v.trim().isEmpty)
                                    ? 'Enter a display name'
                                    : null,
                              ),
                              const SizedBox(height: 12),
                            ],
                            TextFormField(
                              controller: _emailCtrl,
                              keyboardType: TextInputType.emailAddress,
                              autofillHints: const [AutofillHints.email],
                              decoration: const InputDecoration(
                                labelText: 'Email',
                              ),
                              validator: (v) {
                                if (v == null || v.trim().isEmpty) {
                                  return 'Enter your email';
                                }
                                if (!v.contains('@')) return 'Enter a valid email';
                                return null;
                              },
                            ),
                            const SizedBox(height: 12),
                            TextFormField(
                              controller: _passwordCtrl,
                              obscureText: _obscure,
                              decoration: InputDecoration(
                                labelText: 'Password',
                                suffixIcon: IconButton(
                                  icon: Icon(
                                    _obscure
                                        ? Icons.visibility_outlined
                                        : Icons.visibility_off_outlined,
                                    color: CfColors.textDim,
                                  ),
                                  onPressed: () =>
                                      setState(() => _obscure = !_obscure),
                                ),
                              ),
                              validator: (v) {
                                if (v == null || v.isEmpty) {
                                  return 'Enter your password';
                                }
                                if (_isRegister && v.length < 8) {
                                  return 'Use at least 8 characters';
                                }
                                return null;
                              },
                            ),
                            const SizedBox(height: 18),
                            FilledButton(
                              onPressed: state.busy ? null : _submit,
                              child: state.busy
                                  ? const SizedBox(
                                      height: 20,
                                      width: 20,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                        color: Colors.white,
                                      ),
                                    )
                                  : Text(_isRegister ? 'Create account' : 'Sign in'),
                            ),
                            const SizedBox(height: 8),
                            TextButton(
                              onPressed: state.busy
                                  ? null
                                  : () => setState(
                                        () => _isRegister = !_isRegister,
                                      ),
                              child: Text(
                                _isRegister
                                    ? 'I already have an account'
                                    : 'Create a new account',
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(18),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          const Text(
                            'Continue without an account',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 4),
                          const Text(
                            'Everything stays on this device. Good for a single learner.',
                            style: TextStyle(
                              color: CfColors.textDim,
                              fontSize: 12,
                            ),
                          ),
                          const SizedBox(height: 12),
                          TextField(
                            controller: _localCtrl,
                            decoration: const InputDecoration(
                              labelText: 'Learner handle',
                            ),
                          ),
                          const SizedBox(height: 12),
                          OutlinedButton(
                            onPressed: state.busy ? null : _useLocal,
                            child: const Text('Use this device only'),
                          ),
                        ],
                      ),
                    ),
                  ),
                  if (state.statusMessage.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Text(
                      state.statusMessage,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: CfColors.textDim,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _ServerStatus extends StatelessWidget {
  const _ServerStatus({required this.checking, required this.version});

  final bool checking;
  final String? version;

  @override
  Widget build(BuildContext context) {
    if (checking) {
      return const Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          SizedBox(
            height: 14,
            width: 14,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          SizedBox(width: 8),
          Text(
            'Looking for the local server…',
            style: TextStyle(color: CfColors.textDim, fontSize: 12),
          ),
        ],
      );
    }
    final found = version != null;
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(
          found ? Icons.check_circle_outline : Icons.error_outline,
          size: 16,
          color: found ? CfColors.good : CfColors.warn,
        ),
        const SizedBox(width: 8),
        Flexible(
          child: Text(
            found
                ? 'Server connected (v$version)'
                : 'No server found at the configured address',
            style: TextStyle(
              color: found ? CfColors.good : CfColors.warn,
              fontSize: 12,
            ),
          ),
        ),
      ],
    );
  }
}
