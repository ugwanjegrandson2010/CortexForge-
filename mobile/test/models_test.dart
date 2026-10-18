import 'package:cortexforge_mobile/api/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('HealthInfo', () {
    test('parses ok and version', () {
      final h = HealthInfo.fromJson({'ok': true, 'version': '1.0.0'});
      expect(h.ok, isTrue);
      expect(h.version, '1.0.0');
    });

    test('tolerates missing fields', () {
      final h = HealthInfo.fromJson({});
      expect(h.ok, isFalse);
      expect(h.version, 'unknown');
    });
  });

  group('Probe', () {
    test('parses options and flags', () {
      final p = Probe.fromJson({
        'probe_id': 'goal',
        'name': 'What you are trying to do',
        'purpose': 'Everything downstream depends on this.',
        'minutes': 2,
        'kind': 'interview',
        'question': 'Which of these?',
        'options': ['Exam', 'Understanding'],
      });
      expect(p.probeId, 'goal');
      expect(p.hasOptions, isTrue);
      expect(p.options.length, 2);
    });

    test('a task probe has no options', () {
      final p = Probe.fromJson({
        'probe_id': 'flanker',
        'name': 'Attention',
        'kind': 'task',
        'task_id': 'flanker',
        'minutes': 7,
      });
      expect(p.hasOptions, isFalse);
      expect(p.taskId, 'flanker');
    });
  });

  group('Question', () {
    test('parses a generated question with provenance', () {
      final q = Question.fromJson({
        'qid': 'q1',
        'style': 'cloze',
        'prompt': 'The Calvin cycle occurs in the ____.',
        'answer': 'stroma',
        'source_span': 'The Calvin cycle occurs in the stroma',
        'skill_id': 'photosynthesis',
      });
      expect(q.qid, 'q1');
      expect(q.style, 'cloze');
      expect(q.sourceSpan, isNotEmpty);
    });

    test('defaults skill_id when absent', () {
      final q = Question.fromJson({'qid': 'q2', 'style': 'definition'});
      expect(q.skillId, 'general');
    });
  });

  group('SessionData', () {
    test('parses items and forecast', () {
      final s = SessionData.fromJson({
        'day': 1.5,
        'n_due': 2,
        'items': [
          {'qid': 'a', 'style': 'cloze', 'prompt': 'p', 'answer': 'x'},
          {'qid': 'b', 'style': 'definition', 'prompt': 'q', 'answer': 'y'},
        ],
        'forecast': {'mean_retrievability': 0.83, 'due_now': 2},
      });
      expect(s.items.length, 2);
      expect(s.forecast.dueNow, 2);
      expect(s.forecast.meanRetrievability, closeTo(0.83, 1e-9));
    });

    test('empty payload yields empty items, not an error', () {
      final s = SessionData.fromJson({});
      expect(s.items, isEmpty);
      expect(s.nDue, 0);
    });
  });

  group('AttemptResult', () {
    test('parses mastery and schedule', () {
      final a = AttemptResult.fromJson({
        'p_known': 0.42,
        'mastered': false,
        'next_due_day': 3.0,
      });
      expect(a.pKnown, closeTo(0.42, 1e-9));
      expect(a.mastered, isFalse);
      expect(a.nextDueDay, 3.0);
    });
  });

  group('ProfileResponse', () {
    test('parses role, limits and calibration', () {
      final p = ProfileResponse.fromJson({
        'profile': {
          'role': 'Reciprocator',
          'study_shape': 'Steady',
          'limits': ['This is not a clinical assessment.'],
          'observations': [
            {
              'label': 'Fairness',
              'statement': 'You rejected offers below 35% of the stake.',
              'confidence': 'moderate',
              'caveat': 'altruism outside the game',
            },
          ],
        },
        'session': {
          'calibration': {'bias': 0.12, 'brier': 0.21, 'n': 40},
          'n_attempts': 40,
        },
      });
      expect(p.profile.role, 'Reciprocator');
      expect(p.profile.observations.length, 1);
      expect(p.profile.observations.first.confidence, 'moderate');
      expect(p.calibration.n, 40);
      expect(p.calibration.isEmpty, isFalse);
      expect(p.nAttempts, 40);
    });

    test('missing calibration is reported as empty, not zero-filled noise', () {
      final p = ProfileResponse.fromJson({'profile': {}, 'session': {}});
      expect(p.calibration.isEmpty, isTrue);
    });
  });

  group('AccountSession', () {
    test('parses login response', () {
      final s = AccountSession.fromJson({
        'learner_id': 'sam',
        'api_token': 'tok_abc',
        'session_token': 'sess_xyz',
        'display_name': 'Sam',
        'email': 'sam@example.com',
      });
      expect(s.learnerId, 'sam');
      expect(s.apiToken, 'tok_abc');
      expect(s.sessionToken, 'sess_xyz');
    });
  });
}
