/// Onboarding — the 13-probe first-run sequence.
///
/// Each probe states its purpose in plain language before it runs. Probes
/// adapt: one already answered is skipped, and the skip is recorded. The
/// learner may leave at any point; a partial run still produces a valid
/// contract with a smaller evidence base.
library;

import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../state/app_state.dart';
import '../theme/app_theme.dart';

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key, required this.state});

  final AppState state;

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  OnboardingProgress? _progress;
  Probe? _current;
  bool _loading = true;
  bool _busy = false;
  bool _done = false;
  String? _error;
  String? _contractSummary;

  final _answerCtrl = TextEditingController();
  int _selectedOption = 0;

  @override
  void initState() {
    super.initState();
    _start();
  }

  @override
  void dispose() {
    _answerCtrl.dispose();
    super.dispose();
  }

  Future<void> _start() async {
    setState(() {
      _loading = true;
      _error = null;
      _done = false;
      _contractSummary = null;
    });
    try {
      final res =
          await widget.state.api.onboardingStart(widget.state.learnerId);
      if (!mounted) return;
      setState(() {
        _progress = OnboardingProgress.fromJson(
          (res['progress'] as Map?)?.cast<String, dynamic>() ?? {},
        );
        _loading = false;
      });
      await _nextProbe();
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _nextProbe() async {
    try {
      final res = await widget.state.api.onboardingNext(widget.state.learnerId);
      final probeJson = res['probe'];
      if (!mounted) return;
      setState(() {
        _progress = OnboardingProgress.fromJson(
          (res['progress'] as Map?)?.cast<String, dynamic>() ?? {},
        );
        if (probeJson == null) {
          _current = null;
        } else {
          _current = Probe.fromJson((probeJson as Map).cast<String, dynamic>());
          _selectedOption = 0;
          _answerCtrl.clear();
        }
      });
      if (probeJson == null) {
        await _finish();
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString());
    }
  }

  Future<void> _record(dynamic answer) async {
    final probe = _current;
    if (probe == null) return;
    setState(() => _busy = true);
    try {
      await widget.state.api.onboardingRecord(
        learnerId: widget.state.learnerId,
        probeId: probe.probeId,
        answer: answer,
      );
      if (!mounted) return;
      setState(() => _busy = false);
      await _nextProbe();
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = e.toString();
      });
    }
  }

  Future<void> _finish() async {
    setState(() => _busy = true);
    try {
      final res =
          await widget.state.api.onboardingFinish(widget.state.learnerId);
      if (!mounted) return;
      setState(() {
        _busy = false;
        _done = true;
        _contractSummary = (res['summary'] ?? '').toString();
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = e.toString();
      });
    }
  }

  void _submitCurrent() {
    final probe = _current;
    if (probe == null) return;
    if (probe.hasOptions) {
      _record(probe.options[_selectedOption]);
    } else {
      final text = _answerCtrl.text.trim();
      if (text.isEmpty) return;
      _record(text);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Setup'),
        actions: [
          if (!_done && _progress != null)
            Padding(
              padding: const EdgeInsets.only(right: 16),
              child: Center(
                child: Text(
                  '${_progress!.complete}/${_progress!.total}',
                  style: const TextStyle(
                    color: CfColors.textDim,
                    fontSize: 13,
                  ),
                ),
              ),
            ),
        ],
      ),
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
                          style: const TextStyle(color: CfColors.bad),
                        ),
                        const SizedBox(height: 16),
                        OutlinedButton(
                          onPressed: _start,
                          child: const Text('Restart setup'),
                        ),
                      ],
                    ),
                  ),
                )
              : _done
                  ? _ContractView(
                      summary: _contractSummary ?? '',
                      onDone: () => Navigator.of(context).pop(),
                    )
                  : _buildProbe(),
    );
  }

  Widget _buildProbe() {
    final probe = _current;
    if (probe == null) {
      return const Center(child: CircularProgressIndicator());
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (_progress != null) ...[
          LinearProgressIndicator(
            value: _progress!.fraction,
            minHeight: 4,
            borderRadius: BorderRadius.circular(2),
          ),
          const SizedBox(height: 6),
          Text(
            '${_progress!.minutesLeft.toStringAsFixed(0)} minutes remaining',
            style: const TextStyle(color: CfColors.textDim, fontSize: 12),
          ),
          const SizedBox(height: 16),
        ],
        Text(
          probe.name,
          style: const TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w700,
            letterSpacing: -0.3,
          ),
        ),
        const SizedBox(height: 10),
        if (probe.purpose.isNotEmpty)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Text(
                probe.purpose,
                style: const TextStyle(
                  color: CfColors.textDim,
                  fontSize: 13,
                  height: 1.45,
                ),
              ),
            ),
          ),
        const SizedBox(height: 16),
        if (probe.question.isNotEmpty)
          Text(
            probe.question,
            style: const TextStyle(fontSize: 15, height: 1.45),
          ),
        const SizedBox(height: 16),
        if (probe.hasOptions)
          for (var i = 0; i < probe.options.length; i++)
            Card(
              child: ListTile(
                leading: Icon(
                  i == _selectedOption
                      ? Icons.radio_button_checked
                      : Icons.radio_button_unchecked,
                  color:
                      i == _selectedOption ? CfColors.accent : CfColors.textDim,
                ),
                title: Text(
                  probe.options[i],
                  style: const TextStyle(fontSize: 14),
                ),
                selected: i == _selectedOption,
                onTap: () => setState(() => _selectedOption = i),
              ),
            )
        else
          TextField(
            controller: _answerCtrl,
            minLines: 3,
            maxLines: 8,
            decoration: const InputDecoration(
              labelText: 'Your answer',
              alignLabelWithHint: true,
            ),
          ),
        const SizedBox(height: 20),
        FilledButton(
          onPressed: _busy ? null : _submitCurrent,
          child: _busy
              ? const SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                )
              : const Text('Continue'),
        ),
        const SizedBox(height: 8),
        TextButton(
          onPressed: _busy ? null : () => Navigator.of(context).pop(),
          child: const Text('Leave and continue later'),
        ),
      ],
    );
  }
}

class _ContractView extends StatelessWidget {
  const _ContractView({required this.summary, required this.onDone});

  final String summary;
  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Icon(Icons.assignment_turned_in_outlined,
            size: 40, color: CfColors.good),
        const SizedBox(height: 12),
        const Text(
          'Your learning contract',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 16),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Text(
              summary,
              style: const TextStyle(fontSize: 13, height: 1.5),
            ),
          ),
        ),
        const SizedBox(height: 20),
        FilledButton(onPressed: onDone, child: const Text('Done')),
      ],
    );
  }
}
