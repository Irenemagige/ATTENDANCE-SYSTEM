import 'package:flutter/material.dart';

import 'package:mobile_app/features/timetable/data/timetable_service.dart';

const _primary = Color(0xFF2563EB);
const _primaryDark = Color(0xFF0F172A);
const _surface = Color(0xFFF8FAFC);

class TimetableScreen extends StatefulWidget {
  const TimetableScreen({super.key});

  @override
  State<TimetableScreen> createState() => _TimetableScreenState();
}

class _TimetableScreenState extends State<TimetableScreen> {
  final TimetableService _service = TimetableService();

  bool _loading = true;
  String? _error;

  Map<String, dynamic>? _course;
  List<dynamic> _entries = [];

  final List<String> _days = [
    'MON',
    'TUE',
    'WED',
    'THU',
    'FRI',
  ];

  final Map<String, String> _dayNames = {
    'MON': 'Monday',
    'TUE': 'Tuesday',
    'WED': 'Wednesday',
    'THU': 'Thursday',
    'FRI': 'Friday',
  };

  final List<String> _timeSlots = [
    '07:00-09:00',
    '09:00-11:00',
    '11:00-13:00',
    '13:00-15:00',
    '15:00-17:00',
    '17:00-19:00',
    '19:00-20:00',
  ];

  @override
  void initState() {
    super.initState();
    _loadTimetable();
  }

  Future<void> _loadTimetable() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final result = await _service.fetchMyTimetable();

      if (!mounted) return;

      setState(() {
        _course = Map<String, dynamic>.from(result['course'] ?? {});
        _entries = List<dynamic>.from(result['timetable'] ?? []);
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _loading = false;
        _error = e.toString().replaceFirst('Exception: ', '');
      });
    }
  }

  dynamic _findEntry(String day, String timeSlot) {
    final parts = timeSlot.split('-');

    if (parts.length != 2) return null;

    final start = parts[0];
    final end = parts[1];

    for (final item in _entries) {
      final entry = Map<String, dynamic>.from(item);

      if (entry['day'] == day &&
          entry['start_time'] == start &&
          entry['end_time'] == end) {
        return entry;
      }
    }

    return null;
  }

  Color _subjectColor(String subject) {
    final name = subject.toLowerCase();

    if (name.contains('server')) {
      return const Color(0xFFE0F2FE);
    }

    if (name.contains('analytics')) {
      return const Color(0xFFDCFCE7);
    }

    if (name.contains('cloud')) {
      return const Color(0xFFFEF3C7);
    }

    if (name.contains('law')) {
      return const Color(0xFFFCE7F3);
    }

    return const Color(0xFFEDE9FE);
  }

  Color _subjectAccent(String subject) {
    final name = subject.toLowerCase();

    if (name.contains('server')) {
      return const Color(0xFF0284C7);
    }

    if (name.contains('analytics')) {
      return const Color(0xFF16A34A);
    }

    if (name.contains('cloud')) {
      return const Color(0xFFD97706);
    }

    if (name.contains('law')) {
      return const Color(0xFFDB2777);
    }

    return const Color(0xFF7C3AED);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _surface,
      appBar: AppBar(
        backgroundColor: _primaryDark,
        foregroundColor: Colors.white,
        elevation: 0,
        title: const Text(
          'My Timetable',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        actions: [
          IconButton(
            tooltip: 'Refresh timetable',
            onPressed: _loading ? null : _loadTimetable,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const Center(
        child: CircularProgressIndicator(),
      );
    }

    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.error_outline,
                size: 52,
                color: Colors.redAccent,
              ),
              const SizedBox(height: 12),
              const Text(
                'Unable to load timetable',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                _error!,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _loadTimetable,
                icon: const Icon(Icons.refresh),
                label: const Text('Try Again'),
              ),
            ],
          ),
        ),
      );
    }

    if (_entries.isEmpty) {
      return const Center(
        child: Text(
          'No timetable has been assigned to your course.',
          textAlign: TextAlign.center,
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadTimetable,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildCourseHeader(),
          const SizedBox(height: 16),
          _buildTimetableCard(),
        ],
      ),
    );
  }

  Widget _buildCourseHeader() {
    final courseName = _course?['name']?.toString() ?? 'My Course';
    final courseCode = _course?['code']?.toString() ?? '';

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [
            _primary,
            _primaryDark,
          ],
        ),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(15),
            ),
            child: const Icon(
              Icons.calendar_month,
              color: Colors.white,
              size: 28,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'My Class Timetable',
                  style: TextStyle(
                    color: Colors.white70,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  courseName,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                if (courseCode.isNotEmpty)
                  Text(
                    courseCode,
                    style: const TextStyle(
                      color: Colors.white70,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTimetableCard() {
    return Card(
      elevation: 0,
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(18),
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildHeaderRow(),
              ..._timeSlots.map(_buildTimeRow),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeaderRow() {
    return Row(
      children: [
        _headerCell(
          'TIME',
          width: 92,
        ),
        ..._days.map(
          (day) => _headerCell(
            _dayNames[day]!,
            width: 142,
          ),
        ),
      ],
    );
  }

  Widget _headerCell(
    String text, {
    required double width,
  }) {
    return Container(
      width: width,
      height: 58,
      alignment: Alignment.center,
      decoration: const BoxDecoration(
        color: _primaryDark,
      ),
      child: Text(
        text,
        textAlign: TextAlign.center,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 12,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }

  Widget _buildTimeRow(String timeSlot) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          width: 92,
          height: 105,
          padding: const EdgeInsets.all(8),
          alignment: Alignment.center,
          decoration: const BoxDecoration(
            color: Color(0xFFF1F5F9),
            border: Border(
              right: BorderSide(
                color: Color(0xFFE2E8F0),
              ),
              bottom: BorderSide(
                color: Color(0xFFE2E8F0),
              ),
            ),
          ),
          child: Text(
            timeSlot,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w700,
              color: _primaryDark,
            ),
          ),
        ),
        ..._days.map(
          (day) => _buildSubjectCell(
            _findEntry(day, timeSlot),
          ),
        ),
      ],
    );
  }

  Widget _buildSubjectCell(dynamic item) {
    if (item == null) {
      return Container(
        width: 142,
        height: 105,
        decoration: const BoxDecoration(
          color: Colors.white,
          border: Border(
            right: BorderSide(
              color: Color(0xFFE2E8F0),
            ),
            bottom: BorderSide(
              color: Color(0xFFE2E8F0),
            ),
          ),
        ),
        child: const Center(
          child: Text(
            '—',
            style: TextStyle(
              color: Color(0xFFCBD5E1),
              fontSize: 18,
            ),
          ),
        ),
      );
    }

    final entry = Map<String, dynamic>.from(item);

    final subject = Map<String, dynamic>.from(
      entry['subject'] ?? {},
    );

    final lecturer = Map<String, dynamic>.from(
      entry['lecturer'] ?? {},
    );

    final subjectName =
        subject['name']?.toString() ?? 'Subject';

    final lecturerName =
        lecturer['name']?.toString() ?? 'Lecturer';

    final background = _subjectColor(subjectName);
    final accent = _subjectAccent(subjectName);

    return Container(
      width: 142,
      height: 105,
      padding: const EdgeInsets.all(7),
      decoration: BoxDecoration(
        color: background,
        border: Border(
          right: BorderSide(
            color: Colors.white.withValues(alpha: 0.8),
          ),
          bottom: const BorderSide(
            color: Color(0xFFE2E8F0),
          ),
        ),
      ),
      child: Container(
        padding: const EdgeInsets.all(9),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(10),
          border: Border(
            left: BorderSide(
              color: accent,
              width: 4,
            ),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              subjectName,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: _primaryDark,
                fontSize: 11,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 6),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.person_outline,
                  size: 13,
                  color: accent,
                ),
                const SizedBox(width: 3),
                Expanded(
                  child: Text(
                    lecturerName,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: accent,
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}