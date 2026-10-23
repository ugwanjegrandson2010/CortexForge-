/// Sources — paste or pick the learner's own material, then generate questions.
library;

import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../state/app_state.dart';
import '../theme/app_theme.dart';

class SourcesScreen extends StatefulWidget {
  const SourcesScreen({super.key, required this.state});

  final AppState state;

  @override
  State<SourcesScreen> createState() => _SourcesScreenState();
}

class _SourcesScreenState extends State<SourcesScreen> {
  final _titleCtrl = TextEditingController();
  final _textCtrl = TextEditingController();

  final List<SourceRef> _sources = [];
  SourceRef? _lastSource;
  GenerateResult? _lastGenerated;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _titleCtrl.dispose();
    _textCtrl.dispose();
    super.dispose();
  }

  Future<void> _addSource() async {
    final text = _textCtrl.text.trim();
    if (text.isEmpty) {
      setState(() => _error = 'Paste some material first.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final ref = await widget.state.api.addSource(
        learnerId: widget.state.learnerId,
        text: text,
        title: _titleCtrl.text.trim(),
      );
      if (!mounted) return;
      setState(() {
        _sources.add(ref);
        _lastSource = ref;
        _busy = false;
      });
      _textCtrl.clear();
      _titleCtrl.clear();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Source added — ${ref.nChars} characters.')),
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _busy = false;
      });
    }
  }

  Future<void> _generate() async {
    final ref = _lastSource;
    if (ref == null) {
      setState(() => _error = 'Add a source first.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final result = await widget.state.api.generate(
        learnerId: widget.state.learnerId,
        sourceId: ref.sourceId,
      );
      if (!mounted) return;
      setState(() {
        _lastGenerated = result;
        _busy = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '${result.generated} questions across '
            '${result.questions.map((q) => q.style).toSet().length} styles.',
          ),
        ),
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _busy = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Add material',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 4),
                const Text(
                  'Your own material gives questions in your vocabulary, about your syllabus.',
                  style: TextStyle(color: CfColors.textDim, fontSize: 12),
                ),
                const SizedBox(height: 14),
                TextField(
                  controller: _titleCtrl,
                  decoration: const InputDecoration(labelText: 'Title'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _textCtrl,
                  minLines: 6,
                  maxLines: 12,
                  decoration: const InputDecoration(
                    labelText: 'Paste your text',
                    alignLabelWithHint: true,
                  ),
                ),
                const SizedBox(height: 14),
                FilledButton(
                  onPressed: _busy ? null : _addSource,
                  child: _busy
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Text('Add source'),
                ),
              ],
            ),
          ),
        ),
        if (_error != null) ...[
          const SizedBox(height: 12),
          Text(
            _error!,
            style: const TextStyle(color: CfColors.bad, fontSize: 13),
          ),
        ],
        if (_sources.isNotEmpty) ...[
          const SizedBox(height: 20),
          const _SectionLabel('Your sources'),
          for (final s in _sources)
            Card(
              child: ListTile(
                leading: Icon(
                  s == _lastSource ? Icons.check_circle : Icons.description_outlined,
                  color: s == _lastSource ? CfColors.good : CfColors.textDim,
                ),
                title: Text('${s.nChars} characters'),
                subtitle: Text(
                  'sha ${_shortSha(s.sha256)}',
                  style: const TextStyle(fontSize: 11, color: CfColors.textDim),
                ),
                onTap: () => setState(() => _lastSource = s),
              ),
            ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: _busy ? null : _generate,
            icon: const Icon(Icons.auto_awesome_outlined),
            label: const Text('Generate questions from this source'),
          ),
        ],
        if (_lastGenerated != null) ...[
          const SizedBox(height: 20),
          _SectionLabel('Generated (${_lastGenerated!.generated})'),
          for (final q in _lastGenerated!.questions.take(12))
            Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        _Chip(q.style),
                        const SizedBox(width: 8),
                        if (q.bloomLevel.isNotEmpty) _Chip(q.bloomLevel, dim: true),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      q.prompt,
                      style: const TextStyle(fontSize: 14, height: 1.4),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Source: ${q.sourceSpan}',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 11,
                        color: CfColors.textDim,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ],
    );
  }
}

/// First 12 characters of a hex digest, for a compact identifier.
String _shortSha(String sha) => sha.length <= 12 ? sha : sha.substring(0, 12);

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);

  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8, top: 4),
        child: Text(
          text.toUpperCase(),
          style: const TextStyle(
            fontSize: 11,
            letterSpacing: 0.8,
            color: CfColors.textDim,
          ),
        ),
      );
}

class _Chip extends StatelessWidget {
  const _Chip(this.text, {this.dim = false});
  final String text;
  final bool dim;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: dim ? CfColors.surfaceAlt : CfColors.accent.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: dim ? CfColors.border : CfColors.accent.withValues(alpha: 0.4),
        ),
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 11,
          color: dim ? CfColors.textDim : CfColors.accent,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }
}
