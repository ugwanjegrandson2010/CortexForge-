import 'package:cortexforge_mobile/logic/answer_judge.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('normaliseAnswer', () {
    test('lower-cases and collapses whitespace', () {
      expect(normaliseAnswer('  Glucose   Stores  Energy '),
          'glucose stores energy');
    });

    test('strips surrounding punctuation', () {
      expect(normaliseAnswer('"glucose."'), 'glucose');
    });

    test('handles empty input', () {
      expect(normaliseAnswer('   '), '');
    });
  });

  group('judgeAnswer', () {
    test('exact match after normalisation is correct', () {
      expect(judgeAnswer('Glucose', 'glucose'), isTrue);
      expect(judgeAnswer('the  CALVIN cycle', 'The Calvin Cycle'), isTrue);
    });

    test('empty answer is never correct', () {
      expect(judgeAnswer('', 'glucose'), isFalse);
      expect(judgeAnswer('   ', 'glucose'), isFalse);
    });

    test('a meaningful contained term is accepted', () {
      expect(
        judgeAnswer('thylakoid', 'the thylakoid membrane of the chloroplast'),
        isTrue,
      );
    });

    test('a short contained fragment is rejected', () {
      // "the" is contained but too short to be a real answer.
      expect(judgeAnswer('the', 'the thylakoid membrane'), isFalse);
    });

    test('a wrong answer is rejected', () {
      expect(judgeAnswer('mitochondria', 'thylakoid membrane'), isFalse);
    });
  });

  group('gradeFor', () {
    test('incorrect is always grade 1', () {
      expect(gradeFor(correct: false, confidence: 0.1), 1);
      expect(gradeFor(correct: false, confidence: 0.9), 1);
    });

    test('correct with low confidence is grade 2 (hard)', () {
      expect(gradeFor(correct: true, confidence: 0.3), 2);
    });

    test('correct with normal confidence is grade 3 (good)', () {
      expect(gradeFor(correct: true, confidence: 0.8), 3);
    });
  });

  group('sessionVerdict', () {
    test('high success is under-challenged', () {
      expect(sessionVerdict(0.95).verdict, 'Under-challenged');
    });

    test('75-90% is the productive band', () {
      expect(sessionVerdict(0.80).verdict, 'In the productive band');
    });

    test('50-75% is struggling productively', () {
      expect(sessionVerdict(0.60).verdict, 'Struggling productively');
    });

    test('below 50% is over-loaded', () {
      expect(sessionVerdict(0.30).verdict, 'Over-loaded');
    });

    test('band boundaries are inclusive at the lower edge', () {
      expect(sessionVerdict(0.90).verdict, 'Under-challenged');
      expect(sessionVerdict(0.75).verdict, 'In the productive band');
      expect(sessionVerdict(0.50).verdict, 'Struggling productively');
    });
  });
}
