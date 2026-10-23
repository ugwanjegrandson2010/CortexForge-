/// Data models mirroring the CortexForge server API.
///
/// Every model is immutable and parses from the JSON the Python server
/// returns. Unknown fields are ignored so the client keeps working when
/// the server adds fields.
library;

class HealthInfo {
  final bool ok;
  final String version;
  const HealthInfo({required this.ok, required this.version});

  factory HealthInfo.fromJson(Map<String, dynamic> j) => HealthInfo(
        ok: j['ok'] == true,
        version: (j['version'] ?? 'unknown').toString(),
      );
}

class Probe {
  final String probeId;
  final String name;
  final String purpose;
  final double minutes;
  final String kind;
  final String question;
  final List<String> options;
  final String taskId;

  const Probe({
    required this.probeId,
    required this.name,
    required this.purpose,
    required this.minutes,
    required this.kind,
    required this.question,
    required this.options,
    required this.taskId,
  });

  factory Probe.fromJson(Map<String, dynamic> j) => Probe(
        probeId: (j['probe_id'] ?? '').toString(),
        name: (j['name'] ?? '').toString(),
        purpose: (j['purpose'] ?? '').toString(),
        minutes: _toDouble(j['minutes']),
        kind: (j['kind'] ?? 'interview').toString(),
        question: (j['question'] ?? '').toString(),
        options: _toStringList(j['options']),
        taskId: (j['task_id'] ?? '').toString(),
      );

  bool get hasOptions => options.isNotEmpty;
}

class OnboardingProgress {
  final int complete;
  final int total;
  final double minutesLeft;
  const OnboardingProgress({
    required this.complete,
    required this.total,
    required this.minutesLeft,
  });

  factory OnboardingProgress.fromJson(Map<String, dynamic> j) =>
      OnboardingProgress(
        complete: _toInt(j['complete']),
        total: _toInt(j['total']),
        minutesLeft: _toDouble(j['minutes_left']),
      );

  double get fraction => total == 0 ? 0 : complete / total;
}

class SourceRef {
  final String sourceId;
  final String sha256;
  final int nChars;
  const SourceRef({
    required this.sourceId,
    required this.sha256,
    required this.nChars,
  });

  factory SourceRef.fromJson(Map<String, dynamic> j) => SourceRef(
        sourceId: (j['source_id'] ?? '').toString(),
        sha256: (j['sha256'] ?? '').toString(),
        nChars: _toInt(j['n_chars']),
      );
}

class Question {
  final String qid;
  final String style;
  final String prompt;
  final String answer;
  final String sourceSpan;
  final String skillId;
  final String bloomLevel;

  const Question({
    required this.qid,
    required this.style,
    required this.prompt,
    required this.answer,
    required this.sourceSpan,
    required this.skillId,
    required this.bloomLevel,
  });

  factory Question.fromJson(Map<String, dynamic> j) => Question(
        qid: (j['qid'] ?? '').toString(),
        style: (j['style'] ?? '').toString(),
        prompt: (j['prompt'] ?? '').toString(),
        answer: (j['answer'] ?? '').toString(),
        sourceSpan: (j['source_span'] ?? '').toString(),
        skillId: (j['skill_id'] ?? 'general').toString(),
        bloomLevel: (j['bloom'] ?? j['bloom_level'] ?? '').toString(),
      );
}

class GenerateResult {
  final int generated;
  final List<Question> questions;
  final Map<String, dynamic> provenance;
  const GenerateResult({
    required this.generated,
    required this.questions,
    required this.provenance,
  });

  factory GenerateResult.fromJson(Map<String, dynamic> j) => GenerateResult(
        generated: _toInt(j['generated']),
        questions: _toMapList(j['questions'])
            .map(Question.fromJson)
            .toList(growable: false),
        provenance: (j['provenance'] as Map?)?.cast<String, dynamic>() ?? {},
      );
}

class Forecast {
  final double meanRetrievability;
  final int dueNow;
  const Forecast({required this.meanRetrievability, required this.dueNow});

  factory Forecast.fromJson(Map<String, dynamic> j) => Forecast(
        meanRetrievability: _toDouble(j['mean_retrievability']),
        dueNow: _toInt(j['due_now']),
      );
}

class SessionData {
  final double day;
  final int nDue;
  final List<Question> items;
  final Forecast forecast;
  const SessionData({
    required this.day,
    required this.nDue,
    required this.items,
    required this.forecast,
  });

  factory SessionData.fromJson(Map<String, dynamic> j) => SessionData(
        day: _toDouble(j['day']),
        nDue: _toInt(j['n_due']),
        items: _toMapList(j['items'])
            .map(Question.fromJson)
            .toList(growable: false),
        forecast: Forecast.fromJson(
          (j['forecast'] as Map?)?.cast<String, dynamic>() ?? {},
        ),
      );
}

class AttemptResult {
  final double pKnown;
  final bool mastered;
  final double nextDueDay;
  const AttemptResult({
    required this.pKnown,
    required this.mastered,
    required this.nextDueDay,
  });

  factory AttemptResult.fromJson(Map<String, dynamic> j) => AttemptResult(
        pKnown: _toDouble(j['p_known']),
        mastered: j['mastered'] == true,
        nextDueDay: _toDouble(j['next_due_day']),
      );
}

class Observation {
  final String label;
  final String statement;
  final String action;
  final String confidence;
  final String caveat;
  const Observation({
    required this.label,
    required this.statement,
    required this.action,
    required this.confidence,
    required this.caveat,
  });

  factory Observation.fromJson(Map<String, dynamic> j) => Observation(
        label: (j['label'] ?? '').toString(),
        statement: (j['statement'] ?? '').toString(),
        action: (j['action'] ?? '').toString(),
        confidence: (j['confidence'] ?? '').toString(),
        caveat: (j['caveat'] ?? '').toString(),
      );
}

class ProfileData {
  final String role;
  final String studyShape;
  final List<String> limits;
  final List<Observation> observations;
  const ProfileData({
    required this.role,
    required this.studyShape,
    required this.limits,
    required this.observations,
  });

  factory ProfileData.fromJson(Map<String, dynamic> j) => ProfileData(
        role: (j['role'] ?? 'Unknown').toString(),
        studyShape: (j['study_shape'] ?? 'Unknown').toString(),
        limits: _toStringList(j['limits']),
        observations: _toMapList(j['observations'])
            .map(Observation.fromJson)
            .toList(growable: false),
      );
}

class CalibrationStats {
  final double bias;
  final double brier;
  final int n;
  const CalibrationStats({
    required this.bias,
    required this.brier,
    required this.n,
  });

  factory CalibrationStats.fromJson(Map<String, dynamic> j) => CalibrationStats(
        bias: _toDouble(j['bias']),
        brier: _toDouble(j['brier']),
        n: _toInt(j['n']),
      );

  bool get isEmpty => n == 0;
}

class ProfileResponse {
  final ProfileData profile;
  final CalibrationStats calibration;
  final int nAttempts;
  const ProfileResponse({
    required this.profile,
    required this.calibration,
    required this.nAttempts,
  });

  factory ProfileResponse.fromJson(Map<String, dynamic> j) {
    final session = (j['session'] as Map?)?.cast<String, dynamic>() ?? {};
    return ProfileResponse(
      profile: ProfileData.fromJson(
        (j['profile'] as Map?)?.cast<String, dynamic>() ?? {},
      ),
      calibration: CalibrationStats.fromJson(
        (session['calibration'] as Map?)?.cast<String, dynamic>() ?? {},
      ),
      nAttempts: _toInt(session['n_attempts']),
    );
  }
}

class McpServer {
  final String key;
  final String name;
  final String description;
  final String auth;
  final bool core;
  const McpServer({
    required this.key,
    required this.name,
    required this.description,
    required this.auth,
    required this.core,
  });

  factory McpServer.fromJson(Map<String, dynamic> j) => McpServer(
        key: (j['key'] ?? '').toString(),
        name: (j['name'] ?? j['key'] ?? '').toString(),
        description: (j['description'] ?? '').toString(),
        auth: (j['auth'] ?? j['auth_type'] ?? 'none').toString(),
        core: j['core'] == true,
      );
}

class AccountSession {
  final String learnerId;
  final String apiToken;
  final String? sessionToken;
  final String displayName;
  final String email;
  const AccountSession({
    required this.learnerId,
    required this.apiToken,
    required this.sessionToken,
    required this.displayName,
    required this.email,
  });

  factory AccountSession.fromJson(Map<String, dynamic> j) => AccountSession(
        learnerId: (j['learner_id'] ?? '').toString(),
        apiToken: (j['api_token'] ?? '').toString(),
        sessionToken: j['session_token']?.toString(),
        displayName: (j['display_name'] ?? '').toString(),
        email: (j['email'] ?? '').toString(),
      );
}

// --- parsing helpers -------------------------------------------------------

double _toDouble(dynamic v) {
  if (v is num) return v.toDouble();
  if (v is String) return double.tryParse(v) ?? 0;
  return 0;
}

int _toInt(dynamic v) {
  if (v is int) return v;
  if (v is num) return v.toInt();
  if (v is String) return int.tryParse(v) ?? 0;
  return 0;
}

List<String> _toStringList(dynamic v) {
  if (v is List) return v.map((e) => e.toString()).toList(growable: false);
  return const [];
}

List<Map<String, dynamic>> _toMapList(dynamic v) {
  if (v is List) {
    return v
        .whereType<Map<String, dynamic>>()
        .map((e) => e.cast<String, dynamic>())
        .toList(growable: false);
  }
  return const [];
}
