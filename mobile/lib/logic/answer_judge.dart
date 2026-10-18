/// Pure answer-grading helpers.
///
/// Kept free of Flutter imports so the logic can be unit-tested directly and
/// reused by any client surface.
library;

/// Normalises an answer for comparison: lower-case, collapse whitespace,
/// strip surrounding punctuation.
String normaliseAnswer(String s) {
  return s
      .toLowerCase()
      .replaceAll(RegExp(r'\s+'), ' ')
      .replaceAll(RegExp(r'^[^\w]+|[^\w]+$'), '')
      .trim();
}

/// Grades a learner's typed answer against the canonical answer.
///
/// Exact normalised match counts as correct. A shorter answer that appears
/// verbatim inside the canonical answer also counts, provided it is at least
/// four characters — this accepts a key term where the full sentence was
/// stored, without accepting single-letter guesses.
bool judgeAnswer(String given, String expected) {
  final g = normaliseAnswer(given);
  final e = normaliseAnswer(expected);
  if (g.isEmpty) return false;
  if (g == e) return true;
  return e.contains(g) && g.length >= 4;
}

/// Maps a correctness verdict and confidence to an FSRS-style grade (1–4).
///
/// Correct-and-fast with no hints is a 4 (easy); correct is a 3 (good);
/// incorrect is a 1 (again). A grade of 2 (hard) is reserved for a correct
/// answer the learner was not confident about.
int gradeFor({
  required bool correct,
  double confidence = 1.0,
}) {
  if (!correct) return 1;
  if (confidence < 0.5) return 2;
  return 3;
}

/// Human-readable success verdict for a finished session.
///
/// Mirrors the server's four honest bands so the client never invents its own
/// interpretation of the numbers.
({String verdict, String explanation}) sessionVerdict(double successRate) {
  if (successRate >= 0.90) {
    return (
      verdict: 'Under-challenged',
      explanation:
          'This set was too easy to produce much learning. The next session should be harder.',
    );
  }
  if (successRate >= 0.75) {
    return (
      verdict: 'In the productive band',
      explanation: 'This is where learning is fastest. Keep it here.',
    );
  }
  if (successRate >= 0.50) {
    return (
      verdict: 'Struggling productively',
      explanation:
          'Hard, but you are still generating answers. That is the useful kind of hard.',
    );
  }
  return (
    verdict: 'Over-loaded',
    explanation:
        'This was too hard to learn much from. Reduce the load and rebuild the basics.',
  );
}
