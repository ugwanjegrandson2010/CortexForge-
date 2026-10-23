/// Study — the practice session player.
///
/// One item on screen at a time. Confidence is captured *before* feedback so
/// calibration can be measured (the research's highest-leverage feature).
/// Feedback is informational, never praise.
library;

import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../logic/answer_judge.dart';
import '../state/app_state.dart';
import '../theme/app_theme.dart';

class StudyScreen extends StatefulWidget {
  const StudyScreen({super.key, required this.state});

  final AppState state;

  @override
  State<StudyScreen> createState() => _StudyScreenState();
}

class _StudyScreenState extends State<StudyScreen> {
  List<Question> _items = [];
  int _index = 0;
  bool _loading = true;
  String? _error;
  bool _finished = false;

  double _confidence = 0.7;
  final _answerCtrl = TextEditingController();
  AttemptResult? _lastResult;
  bool _lastCorrect = false;
  final List<bool> _history = [];
  final List<double> _confidences = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _answerCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
      _finished = false;
      _index = 0;
      _history.clear();
      _confidences.clear();
      _lastResult = null;
    });
    try {
      final session = await widget.state.api.session(widget.state.learnerId);
      if (!mounted) return;
      setState(() {
        _items = session.items;
        _loading = false;
        _finished = session.items.isEmpty;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _submit() async {
    final item = _items[_index];
    final answer = _answerCtrl.text.trim();
    final correct = judgeAnswer(answer, item.answer);
    try {
      final result = await widget.state.api.attempt(
        learnerId: widget.state.learnerId,
        qid: item.qid,
        correct: correct,
        grade: gradeFor(correct: correct, confidence: _confidence),
        confidence: _confidence,
        skillId: item.skillId,
        response: answer,
      );
      if (!mounted) return;
      setState(() {
        _lastResult = result;
        _lastCorrect = correct;
        _history.add(correct);
        _confidences.add(_confidence);
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString());
    }
  }

  void _next() {
    setState(() {
      _lastResult = null;
      _answerCtrl.clear();
      _confidence = 0.7;
      if (_index + 1 >= _items.length) {
        _finished = true;
      } else {
        _index += 1;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(
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
              OutlinedButton(onPressed: _load, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }
    if (_finished) {
      return _Summary(
        history: _history,
        confidences: _confidences,
        onRestart: _load,
      );
    }

    final item = _items[_index];
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            Expanded(
              child: LinearProgressIndicator(
                value: (_index + 1) / _items.length,
                minHeight: 4,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(width: 12),
            Text(
              '${_index + 1}/${_items.length}',
              style: const TextStyle(color: CfColors.textDim, fontSize: 12),
            ),
          ],
        ),
        const SizedBox(height: 16),
        Row(
          children: [
            _Tag(item.style),
            const SizedBox(width: 8),
            if (item.bloomLevel.isNotEmpty) _Tag(item.bloomLevel, dim: true),
          ],
        ),
        const SizedBox(height: 14),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Text(
              item.prompt,
              style: const TextStyle(fontSize: 16, height: 1.5),
            ),
          ),
        ),
        if (_lastResult == null) ...[
          const SizedBox(height: 16),
          _ConfidenceSelector(
            value: _confidence,
            onChanged: (v) => setState(() => _confidence = v),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _answerCtrl,
            minLines: 1,
            maxLines: 4,
            textInputAction: TextInputAction.done,
            decoration: const InputDecoration(
              labelText: 'Your answer',
              alignLabelWithHint: true,
            ),
            onSubmitted: (_) => _submit(),
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: _submit,
            icon: const Icon(Icons.check_rounded),
            label: const Text('Submit answer'),
          ),
        ] else
          _Feedback(
            correct: _lastCorrect,
            expected: item.answer,
            result: _lastResult!,
            onNext: _next,
          ),
      ],
    );
  }
}

class _ConfidenceSelector extends StatelessWidget {
  const _ConfidenceSelector({required this.value, required this.onChanged});

  final double value;
  final ValueChanged<double> onChanged;

  @override
  Widget build(BuildContext context) {
    final label = value >= 0.85
        ? 'Confident'
        : value >= 0.6
            ? 'Fairly sure'
            : value >= 0.4
                ? 'Unsure'
                : 'Guessing';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text(
              'How confident are you?',
              style: TextStyle(fontSize: 13, color: CfColors.textDim),
            ),
            Text(
              '$label · ${(value * 100).toStringAsFixed(0)}%',
              style: const TextStyle(
                fontSize: 13,
                color: CfColors.accent,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        Slider(
          value: value,
          min: 0.1,
          max: 1.0,
          divisions: 9,
          label: '${(value * 100).toStringAsFixed(0)}%',
          onChanged: onChanged,
        ),
        const Text(
          'Answer before you see feedback — this is what makes the calibration measure real.',
          style: TextStyle(fontSize: 11, color: CfColors.textDim),
        ),
      ],
    );
  }
}

class _Feedback extends StatelessWidget {
  const _Feedback({
    required this.correct,
    required this.expected,
    required this.result,
    required this.onNext,
  });

  final bool correct;
  final String expected;
  final AttemptResult result;
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) {
    final color = correct ? CfColors.good : CfColors.warn;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      correct ? Icons.check_circle_outline : Icons.info_outline,
                      color: color,
                      size: 20,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      correct ? 'Correct' : 'Not yet',
                      style: TextStyle(
                        color: color,
                        fontWeight: FontWeight.w600,
                        fontSize: 15,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                const Text(
                  'Reference answer',
                  style: TextStyle(fontSize: 11, color: CfColors.textDim),
                ),
                const SizedBox(height: 4),
                Text(
                  expected,
                  style: const TextStyle(fontSize: 14, height: 1.4),
                ),
                const Divider(height: 24),
                Row(
                  children: [
                    _mini('Mastery',
                        '${(result.pKnown * 100).toStringAsFixed(0)}%'),
                    const SizedBox(width: 20),
                    _mini(
                      'Next review',
                      result.nextDueDay < 1
                          ? 'today'
                          : 'in ${result.nextDueDay.toStringAsFixed(0)}d',
                    ),
                    const SizedBox(width: 20),
                    _mini('Status', result.mastered ? 'mastered' : 'learning'),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: onNext,
          icon: const Icon(Icons.arrow_forward_rounded),
          label: const Text('Next item'),
        ),
      ],
    );
  }

  Widget _mini(String label, String value) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label,
              style: const TextStyle(fontSize: 11, color: CfColors.textDim)),
          const SizedBox(height: 2),
          Text(
            value,
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
          ),
        ],
      );
}

class _Summary extends StatelessWidget {
  const _Summary({
    required this.history,
    required this.confidences,
    required this.onRestart,
  });

  final List<bool> history;
  final List<double> confidences;
  final VoidCallback onRestart;

  @override
  Widget build(BuildContext context) {
    final n = history.length;
    if (n == 0) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.inbox_outlined,
                  size: 40, color: CfColors.textDim),
              const SizedBox(height: 12),
              const Text(
                'Nothing is due right now.',
                style: TextStyle(color: CfColors.textDim),
              ),
              const SizedBox(height: 4),
              const Text(
                'Add a source and generate questions, or come back when cards are due.',
                textAlign: TextAlign.center,
                style: TextStyle(color: CfColors.textDim, fontSize: 12),
              ),
              const SizedBox(height: 16),
              OutlinedButton(
                  onPressed: onRestart, child: const Text('Refresh')),
            ],
          ),
        ),
      );
    }

    final correct = history.where((c) => c).length;
    final rate = correct / n;
    final v = sessionVerdict(rate);
    final color = rate >= 0.90
        ? CfColors.warn
        : rate >= 0.75
            ? CfColors.good
            : rate >= 0.50
                ? CfColors.accent
                : CfColors.bad;

    final avgConf = confidences.isEmpty
        ? 0.0
        : confidences.reduce((a, b) => a + b) / confidences.length;
    final bias = avgConf - rate;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Session summary',
                  style: TextStyle(fontSize: 13, color: CfColors.textDim),
                ),
                const SizedBox(height: 6),
                Text(
                  v.verdict,
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.w700,
                    color: color,
                    letterSpacing: -0.4,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  v.explanation,
                  style: const TextStyle(
                    color: CfColors.textDim,
                    fontSize: 13,
                    height: 1.4,
                  ),
                ),
                const Divider(height: 28),
                Row(
                  children: [
                    _stat('Correct', '$correct/$n'),
                    const SizedBox(width: 24),
                    _stat('Success', '${(rate * 100).toStringAsFixed(0)}%'),
                    const SizedBox(width: 24),
                    _stat(
                      'Bias',
                      '${bias >= 0 ? '+' : ''}${(bias * 100).toStringAsFixed(0)}%',
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 8),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Text(
              bias > 0.10
                  ? 'Your confidence ran ahead of your accuracy this session. That gap is the thing to watch.'
                  : bias < -0.10
                      ? 'You did better than you expected. Under-confidence is also a calibration error.'
                      : 'Your confidence and your accuracy were close this session.',
              style: const TextStyle(
                color: CfColors.textDim,
                fontSize: 13,
                height: 1.4,
              ),
            ),
          ),
        ),
        const SizedBox(height: 16),
        OutlinedButton.icon(
          onPressed: onRestart,
          icon: const Icon(Icons.refresh_rounded),
          label: const Text('Study more'),
        ),
      ],
    );
  }

  Widget _stat(String label, String value) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label,
              style: const TextStyle(fontSize: 11, color: CfColors.textDim)),
          const SizedBox(height: 2),
          Text(
            value,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
          ),
        ],
      );
}

class _Tag extends StatelessWidget {
  const _Tag(this.text, {this.dim = false});
  final String text;
  final bool dim;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: dim
              ? CfColors.surfaceAlt
              : CfColors.accent.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(
            color:
                dim ? CfColors.border : CfColors.accent.withValues(alpha: 0.4),
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
