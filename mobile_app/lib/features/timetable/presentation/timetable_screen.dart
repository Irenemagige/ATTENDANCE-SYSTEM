import 'package:flutter/material.dart';
import 'package:mobile_app/features/timetable/data/timetable_service.dart';

class TimetableScreen extends StatefulWidget {
  const TimetableScreen({super.key});

  @override
  State<TimetableScreen> createState() => _TimetableScreenState();
}

class _TimetableScreenState extends State<TimetableScreen> {
  final TimetableService _service = TimetableService();

  bool _loading = true;
  String? _error;
  bool _showTimetable = false;

  Map<String, dynamic>? _course;
  List<dynamic> _entries = [];

  final List<String> _days = [
    'MON',
    'TUE',
    'WED',
    'THU',
    'FRI',
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
        _course = Map<String, dynamic>.from(
          result['course'] ?? {},
        );

        _entries = List<dynamic>.from(
          result['timetable'] ?? [],
        );

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

  List<String> _getTimeSlots() {
    final slots = <String>{};

    for (final item in _entries) {
      final startTime = item['start_time']?.toString() ?? '';
      final endTime = item['end_time']?.toString() ?? '';

      if (startTime.isNotEmpty && endTime.isNotEmpty) {
        slots.add('$startTime-$endTime');
      }
    }

    final result = slots.toList();

    result.sort((a, b) {
      final aStart = a.split('-').first;
      final bStart = b.split('-').first;

      return aStart.compareTo(bStart);
    });

    return result;
  }

  Map<String, dynamic>? _findEntry(
    String day,
    String timeSlot,
  ) {
    final parts = timeSlot.split('-');

    if (parts.length != 2) {
      return null;
    }

    final start = parts[0];
    final end = parts[1];

    for (final item in _entries) {
      if (item['day']?.toString() == day &&
          item['start_time']?.toString() == start &&
          item['end_time']?.toString() == end) {
        return Map<String, dynamic>.from(item);
      }
    }

    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Timetable'),
        centerTitle: true,
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
      return RefreshIndicator(
        onRefresh: _loadTimetable,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            SizedBox(
              height: MediaQuery.of(context).size.height * 0.3,
            ),
            const Icon(
              Icons.error_outline,
              size: 60,
            ),
            const SizedBox(height: 16),
            Center(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Text(
                  _error!,
                  textAlign: TextAlign.center,
                ),
              ),
            ),
          ],
        ),
      );
    }

    if (_entries.isEmpty) {
      return RefreshIndicator(
        onRefresh: _loadTimetable,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            SizedBox(
              height: MediaQuery.of(context).size.height * 0.3,
            ),
            const Icon(
              Icons.calendar_month_outlined,
              size: 60,
            ),
            const SizedBox(height: 16),
            const Center(
              child: Text(
                'No timetable has been assigned to your course.',
                textAlign: TextAlign.center,
              ),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadTimetable,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildCourseHeader(),

          if (_showTimetable) ...[
            const SizedBox(height: 16),
            _buildTimetableCard(),
          ],
        ],
      ),
    );
  }

  Widget _buildCourseHeader() {
    final courseName =
        _course?['name']?.toString() ?? 'My Course';

    final courseCode =
        _course?['code']?.toString() ?? '';

    return InkWell(
      onTap: () {
        setState(() {
          _showTimetable = !_showTimetable;
        });
      },
      borderRadius: BorderRadius.circular(20),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          gradient: const LinearGradient(
            colors: [
              Color(0xFF1565C0),
              Color(0xFF1976D2),
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          boxShadow: [
            BoxShadow(
              blurRadius: 8,
              offset: const Offset(0, 4),
              color: Colors.black12,
            ),
          ],
        ),
        child: Row(
          children: [
            Container(
              width: 52,
              height: 52,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.18),
                borderRadius: BorderRadius.circular(14),
              ),
              child: const Icon(
                Icons.calendar_month,
                color: Colors.white,
                size: 28,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'My Class Timetable',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 5),
                  Text(
                    courseName,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 15,
                    ),
                  ),
                  if (courseCode.isNotEmpty) ...[
                    const SizedBox(height: 3),
                    Text(
                      courseCode,
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.85),
                        fontSize: 13,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            Icon(
              _showTimetable
                  ? Icons.keyboard_arrow_up
                  : Icons.arrow_forward_ios,
              color: Colors.white,
              size: 20,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTimetableCard() {
    final timeSlots = _getTimeSlots();

    if (timeSlots.isEmpty) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(20),
          child: Center(
            child: Text(
              'No timetable entries available.',
            ),
          ),
        ),
      );
    }

    return Card(
      elevation: 3,
      clipBehavior: Clip.antiAlias,
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildHeaderRow(),

            ...timeSlots.map(
              (timeSlot) => _buildTimeRow(timeSlot),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeaderRow() {
    return Row(
      children: [
        _buildHeaderCell(
          'TIME',
          width: 110,
        ),
        ..._days.map(
          (day) => _buildHeaderCell(
            day,
            width: 150,
          ),
        ),
      ],
    );
  }

  Widget _buildHeaderCell(
    String text, {
    required double width,
  }) {
    return Container(
      width: width,
      height: 50,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: Colors.grey.shade200,
        border: Border.all(
          color: Colors.grey.shade300,
        ),
      ),
      child: Text(
        text,
        style: const TextStyle(
          fontWeight: FontWeight.bold,
          fontSize: 12,
        ),
      ),
    );
  }

  Widget _buildTimeRow(String timeSlot) {
    return Row(
      children: [
        Container(
          width: 110,
          height: 105,
          alignment: Alignment.center,
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: Colors.grey.shade100,
            border: Border.all(
              color: Colors.grey.shade300,
            ),
          ),
          child: Text(
            timeSlot,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontWeight: FontWeight.w600,
              fontSize: 12,
            ),
          ),
        ),

        ..._days.map(
          (day) {
            final entry = _findEntry(
              day,
              timeSlot,
            );

            return _buildSubjectCell(entry);
          },
        ),
      ],
    );
  }

  Widget _buildSubjectCell(
    Map<String, dynamic>? entry,
  ) {
    if (entry == null) {
      return Container(
        width: 150,
        height: 105,
        decoration: BoxDecoration(
          color: Colors.white,
          border: Border.all(
            color: Colors.grey.shade300,
          ),
        ),
        child: const Center(
          child: Text(
            '-',
            style: TextStyle(
              color: Colors.grey,
            ),
          ),
        ),
      );
    }

    final subject =
        Map<String, dynamic>.from(
      entry['subject'] ?? {},
    );

    final lecturer =
        Map<String, dynamic>.from(
      entry['lecturer'] ?? {},
    );

    final subjectName =
        subject['name']?.toString() ?? 'Subject';

    final subjectCode =
        subject['code']?.toString() ?? '';

    final lecturerName =
        lecturer['name']?.toString() ?? '';

    final room =
        entry['room']?.toString() ?? '';

    return Container(
      width: 150,
      height: 105,
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        border: Border.all(
          color: Colors.grey.shade300,
        ),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            subjectName,
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 13,
            ),
          ),

          if (subjectCode.isNotEmpty) ...[
            const SizedBox(height: 3),
            Text(
              subjectCode,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 11,
                color: Colors.grey.shade700,
              ),
            ),
          ],

          if (lecturerName.isNotEmpty) ...[
            const SizedBox(height: 5),
            Text(
              lecturerName,
              textAlign: TextAlign.center,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 11,
              ),
            ),
          ],

          if (room.isNotEmpty) ...[
            const SizedBox(height: 3),
            Text(
              'Room: $room',
              textAlign: TextAlign.center,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 10,
                color: Colors.grey.shade600,
              ),
            ),
          ],
        ],
      ),
    );
  }
}