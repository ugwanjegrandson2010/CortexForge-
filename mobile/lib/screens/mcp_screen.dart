/// Integrations — the MCP server catalogue.
///
/// Shows which servers are available, which need OAuth, and which are in the
/// core set. Connecting is a per-server consent action; nothing is connected
/// silently.
library;

import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../state/app_state.dart';
import '../theme/app_theme.dart';

class McpScreen extends StatefulWidget {
  const McpScreen({super.key, required this.state});

  final AppState state;

  @override
  State<McpScreen> createState() => _McpScreenState();
}

class _McpScreenState extends State<McpScreen> {
  List<McpServer> _servers = [];
  Map<String, dynamic> _plan = {};
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final servers = await widget.state.api.mcpServers();
      Map<String, dynamic> plan = {};
      try {
        plan = await widget.state.api.mcpPlan();
      } on ApiException {
        plan = {};
      }
      if (!mounted) return;
      setState(() {
        _servers = servers;
        _plan = plan;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Integrations')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          _error!,
                          textAlign: TextAlign.center,
                          style: const TextStyle(color: CfColors.textDim),
                        ),
                        const SizedBox(height: 16),
                        OutlinedButton(
                          onPressed: _load,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Model Context Protocol',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              'Connect note systems and tools so your own material '
                              'can become the source. ${_servers.length} servers '
                              'declared; ${_oauthCount()} need only an OAuth step.',
                              style: const TextStyle(
                                color: CfColors.textDim,
                                fontSize: 13,
                                height: 1.4,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    for (final server in _servers)
                      _ServerCard(
                        server: server,
                        onConnect: () => _connect(server),
                      ),
                    if (_servers.isEmpty)
                      const Padding(
                        padding: EdgeInsets.all(24),
                        child: Text(
                          'No servers reported by the manifest.',
                          style: TextStyle(color: CfColors.textDim),
                        ),
                      ),
                  ],
                ),
    );
  }

  int _oauthCount() {
    final oauth = _plan['oauth_required'];
    if (oauth is List) return oauth.length;
    return _servers.where((s) => s.auth.toLowerCase().contains('oauth')).length;
  }

  void _connect(McpServer server) {
    final needsAuth = server.auth.toLowerCase().contains('oauth') ||
        server.auth.toLowerCase().contains('key');
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: CfColors.surface,
        title: Text(server.name),
        content: Text(
          needsAuth
              ? 'This server needs authorisation before it can be used. '
                  'In this build you complete that step from the desktop '
                  'client; the connection is never made silently.'
              : 'This server needs no authentication and can be used directly.',
          style: const TextStyle(color: CfColors.textDim, height: 1.4),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }
}

class _ServerCard extends StatelessWidget {
  const _ServerCard({required this.server, required this.onConnect});

  final McpServer server;
  final VoidCallback onConnect;

  @override
  Widget build(BuildContext context) {
    final needsAuth = server.auth.toLowerCase().contains('oauth') ||
        server.auth.toLowerCase().contains('key');
    return Card(
      child: ListTile(
        leading: Icon(
          needsAuth ? Icons.lock_outline : Icons.link,
          color: needsAuth ? CfColors.warn : CfColors.good,
        ),
        title: Row(
          children: [
            Flexible(
              child: Text(
                server.name,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
            ),
            if (server.core) ...[
              const SizedBox(width: 8),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: CfColors.accent.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(5),
                ),
                child: const Text(
                  'core',
                  style: TextStyle(fontSize: 10, color: CfColors.accent),
                ),
              ),
            ],
          ],
        ),
        subtitle: Text(
          server.description.isEmpty
              ? (needsAuth ? 'Requires authorisation' : 'No auth needed')
              : server.description,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontSize: 12, color: CfColors.textDim),
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: onConnect,
      ),
    );
  }
}
