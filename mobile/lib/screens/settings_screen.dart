/// Settings — data rights and session control.
///
/// Export produces machine-readable JSON; erasure requires the literal
/// confirmation string and removes every row. Signing out drops the token
/// from memory.
library;

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api/api_client.dart';
import '../state/app_state.dart';
import '../theme/app_theme.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key, required this.state});

  final AppState state;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool _busy = false;

  Future<void> _export() async {
    setState(() => _busy = true);
    try {
      final data = await widget.state.api.exportData(widget.state.learnerId);
      final pretty = const JsonEncoder.withIndent('  ').convert(data);
      await Clipboard.setData(ClipboardData(text: pretty));
      if (!mounted) return;
      setState(() => _busy = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Exported ${pretty.length} characters of JSON to the clipboard.',
          ),
        ),
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  Future<void> _erase() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: CfColors.surface,
        title: const Text('Erase all data?'),
        content: const Text(
          'This removes every source, question, attempt and card for this '
          'learner. It cannot be undone.',
          style: TextStyle(color: CfColors.textDim, height: 1.4),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Erase', style: TextStyle(color: CfColors.bad)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() => _busy = true);
    try {
      await widget.state.api.erase(widget.state.learnerId);
      if (!mounted) return;
      setState(() => _busy = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('All data erased.')),
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  Future<void> _signOut() async {
    await widget.state.signOut();
    if (!mounted) return;
    Navigator.of(context).popUntil((route) => route.isFirst);
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.person_outline),
                  title: const Text('Learner'),
                  subtitle: Text(
                    state.displayName,
                    style: const TextStyle(color: CfColors.textDim),
                  ),
                ),
                if (state.email.isNotEmpty)
                  ListTile(
                    leading: const Icon(Icons.mail_outline),
                    title: const Text('Email'),
                    subtitle: Text(
                      state.email,
                      style: const TextStyle(color: CfColors.textDim),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          Card(
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.download_outlined),
                  title: const Text('Export my data'),
                  subtitle: const Text(
                    'Copy all learner data as JSON',
                    style: TextStyle(color: CfColors.textDim, fontSize: 12),
                  ),
                  enabled: !_busy,
                  onTap: _export,
                ),
                const Divider(height: 1),
                ListTile(
                  leading:
                      const Icon(Icons.delete_outline, color: CfColors.bad),
                  title: const Text(
                    'Erase all data',
                    style: TextStyle(color: CfColors.bad),
                  ),
                  subtitle: const Text(
                    'Removes everything, permanently',
                    style: TextStyle(color: CfColors.textDim, fontSize: 12),
                  ),
                  enabled: !_busy,
                  onTap: _erase,
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          Card(
            child: Column(
              children: [
                const ListTile(
                  leading: Icon(Icons.shield_outlined),
                  title: Text('Privacy'),
                  subtitle: Text(
                    'No trackers, no ads, no third parties. The token lives in '
                    'memory only and is never written to disk.',
                    style: TextStyle(color: CfColors.textDim, fontSize: 12),
                  ),
                ),
                const Divider(height: 1),
                ListTile(
                  leading: const Icon(Icons.logout),
                  title: const Text('Sign out'),
                  enabled: !_busy,
                  onTap: _signOut,
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Center(
            child: Text(
              state.statusMessage,
              textAlign: TextAlign.center,
              style: const TextStyle(color: CfColors.textDim, fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }
}
