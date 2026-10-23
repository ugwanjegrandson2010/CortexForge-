/// Profile — the open learner model.
///
/// Shows what the system believes, each observation's confidence label and
/// caveat, and the calibration record. Everything here is the learner's own
/// data; weak-evidence constructs are excluded server-side, not caveated here.
library;

import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../state/app_state.dart';
import '../theme/app_theme.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key, required this.state});

  final AppState state;

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  ProfileResponse? _data;
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
      final data = await widget.state.api.profile(widget.state.learnerId);
      if (!mounted) return;
      setState(() {
        _data = data;
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

    final profile = _data!.profile;
    final cal = _data!.calibration;

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Profile',
                    style: TextStyle(fontSize: 13, color: CfColors.textDim),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    profile.role,
                    style: const TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w700,
                      letterSpacing: -0.4,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Study shape: ${profile.studyShape}',
                    style: const TextStyle(
                      color: CfColors.textDim,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
          ),
          if (profile.limits.isNotEmpty) ...[
            const SizedBox(height: 16),
            const _Label('What this is not'),
            for (final limit in profile.limits)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(
                        Icons.info_outline,
                        size: 16,
                        color: CfColors.textDim,
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          limit,
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
              ),
          ],
          if (!cal.isEmpty) ...[
            const SizedBox(height: 16),
            const _Label('Calibration'),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        _metric('Bias', cal.bias.toStringAsFixed(3)),
                        const SizedBox(width: 24),
                        _metric('Brier', cal.brier.toStringAsFixed(3)),
                        const SizedBox(width: 24),
                        _metric('Answers', '${cal.n}'),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(
                      cal.bias.abs() <= 0.05
                          ? 'Well calibrated: confidence tracks accuracy.'
                          : cal.bias > 0
                              ? 'Over-confident: you feel more certain than your accuracy supports.'
                              : 'Under-confident: your accuracy is better than your feeling of certainty.',
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
          ],
          if (profile.observations.isNotEmpty) ...[
            const SizedBox(height: 16),
            const _Label('Behavioural observations'),
            for (final obs in profile.observations)
              _ObservationCard(observation: obs),
          ] else ...[
            const SizedBox(height: 16),
            const Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Text(
                  'No behavioural observations yet. Complete the onboarding '
                  'probes and they will appear here with confidence labels.',
                  style: TextStyle(
                    color: CfColors.textDim,
                    fontSize: 13,
                    height: 1.4,
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _metric(String label, String value) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label,
              style: const TextStyle(fontSize: 11, color: CfColors.textDim)),
          const SizedBox(height: 2),
          Text(
            value,
            style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
          ),
        ],
      );
}

class _ObservationCard extends StatelessWidget {
  const _ObservationCard({required this.observation});

  final Observation observation;

  @override
  Widget build(BuildContext context) {
    final conf = observation.confidence.toLowerCase();
    final color = conf == 'high'
        ? CfColors.good
        : conf == 'moderate'
            ? CfColors.accent
            : CfColors.warn;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                if (observation.label.isNotEmpty)
                  Expanded(
                    child: Text(
                      observation.label,
                      style: const TextStyle(
                        fontSize: 12,
                        color: CfColors.textDim,
                      ),
                    ),
                  ),
                if (observation.confidence.isNotEmpty)
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: color.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: color.withValues(alpha: 0.4)),
                    ),
                    child: Text(
                      observation.confidence,
                      style: TextStyle(
                        fontSize: 10,
                        color: color,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
              ],
            ),
            if (observation.statement.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(
                observation.statement,
                style: const TextStyle(fontSize: 14, height: 1.45),
              ),
            ],
            if (observation.caveat.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(
                'Does not measure: ${observation.caveat}',
                style: const TextStyle(
                  fontSize: 12,
                  color: CfColors.textDim,
                  fontStyle: FontStyle.italic,
                  height: 1.4,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Label extends StatelessWidget {
  const _Label(this.text);
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
