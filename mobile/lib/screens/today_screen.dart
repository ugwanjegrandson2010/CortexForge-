/// Today — the daily landing surface.
///
/// Shows what is due, the honest session verdict, and one primary action.
/// Per the research mandates: one focal element, no feeds, no badges, and
/// every number is the learner's own.
library;

import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../state/app_state.dart';
import '../theme/app_theme.dart';

class TodayScreen extends StatefulWidget {
  const TodayScreen({
    super.key,
    required this.state,
    required this.onNavigate,
  });

  final AppState state;
  final ValueChanged<int> onNavigate;

  @override
  State<TodayScreen> createState() => _TodayScreenState();
}

class _TodayScreenState extends State<TodayScreen> {
  SessionData? _session;
  ProfileResponse? _profile;
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
      final session = await widget.state.api.session(widget.state.learnerId);
      ProfileResponse? profile;
      try {
        profile = await widget.state.api.profile(widget.state.learnerId);
      } on ApiException {
        profile = null;
      }
      if (!mounted) return;
      setState(() {
        _session = session;
        _profile = profile;
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
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return _ErrorView(message: _error!, onRetry: _load);
    }

    final session = _session!;
    final forecast = session.forecast;
    final due = session.items.length;

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _HeroCard(
            due: due,
            meanRetrievability: forecast.meanRetrievability,
            onStart: () => widget.onNavigate(2),
          ),
          const SizedBox(height: 8),
          _HonestVerdict(session: session),
          const SizedBox(height: 8),
          if (_profile != null) _CalibrationCard(profile: _profile!),
          const SizedBox(height: 8),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'What this system will not do',
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 8),
                  for (final line in const [
                    'It will not praise you for showing up.',
                    'It will not claim to make you smarter or prevent dementia.',
                    'It will not diagnose anything.',
                    'It will not send your data anywhere.',
                  ])
                    Padding(
                      padding: const EdgeInsets.only(bottom: 6),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('·  ',
                              style: TextStyle(color: CfColors.textDim)),
                          Expanded(
                            child: Text(
                              line,
                              style: const TextStyle(
                                color: CfColors.textDim,
                                fontSize: 13,
                                height: 1.4,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _HeroCard extends StatelessWidget {
  const _HeroCard({
    required this.due,
    required this.meanRetrievability,
    required this.onStart,
  });

  final int due;
  final double meanRetrievability;
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Today',
              style: TextStyle(
                fontSize: 13,
                color: CfColors.textDim,
                letterSpacing: 0.4,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              due == 0 ? 'Nothing is due' : '$due item${due == 1 ? '' : 's'} due',
              style: const TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.w700,
                letterSpacing: -0.5,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              due == 0
                  ? 'Add a source and generate questions to begin.'
                  : 'Mean retrievability ${(meanRetrievability * 100).toStringAsFixed(0)}% across tracked cards.',
              style: const TextStyle(color: CfColors.textDim, fontSize: 13),
            ),
            const SizedBox(height: 18),
            FilledButton.icon(
              onPressed: onStart,
              icon: const Icon(Icons.play_arrow_rounded),
              label: Text(due == 0 ? 'Go to sources' : 'Start session'),
            ),
          ],
        ),
      ),
    );
  }
}

class _HonestVerdict extends StatelessWidget {
  const _HonestVerdict({required this.session});

  final SessionData session;

  @override
  Widget build(BuildContext context) {
    if (session.items.isEmpty) return const SizedBox.shrink();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            const Icon(Icons.timelapse, color: CfColors.textDim, size: 20),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                'Target success band: 75–90%. Failing about one item in seven is the design, not a problem.',
                style: const TextStyle(
                  color: CfColors.textDim,
                  fontSize: 13,
                  height: 1.4,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CalibrationCard extends StatelessWidget {
  const _CalibrationCard({required this.profile});

  final ProfileResponse profile;

  @override
  Widget build(BuildContext context) {
    final cal = profile.calibration;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Confidence calibration',
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            if (cal.isEmpty)
              const Text(
                'Not enough rated answers yet. Rate your confidence as you practise and this fills in.',
                style: TextStyle(color: CfColors.textDim, fontSize: 13),
              )
            else ...[
              Row(
                children: [
                  _stat('Bias', cal.bias.toStringAsFixed(3)),
                  const SizedBox(width: 20),
                  _stat('Brier', cal.brier.toStringAsFixed(3)),
                  const SizedBox(width: 20),
                  _stat('Answers', '${cal.n}'),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                cal.bias > 0.05
                    ? 'You are over-confident: your confidence runs ahead of your accuracy.'
                    : cal.bias < -0.05
                        ? 'You are under-confident: your accuracy runs ahead of your confidence.'
                        : 'Your confidence and accuracy are close — well calibrated.',
                style: const TextStyle(
                  color: CfColors.textDim,
                  fontSize: 13,
                  height: 1.4,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _stat(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(color: CfColors.textDim, fontSize: 11),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off, size: 40, color: CfColors.textDim),
            const SizedBox(height: 12),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(color: CfColors.textDim),
            ),
            const SizedBox(height: 16),
            OutlinedButton(onPressed: onRetry, child: const Text('Try again')),
          ],
        ),
      ),
    );
  }
}
