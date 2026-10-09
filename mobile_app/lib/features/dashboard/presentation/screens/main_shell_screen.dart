import 'dart:async';

import 'package:flutter/material.dart';
import 'package:mobile_app/core/storage/storage_service.dart';
import 'package:mobile_app/features/attendance/data/attendance_service.dart';
import 'package:mobile_app/features/attendance/data/security_validation_service.dart';
import 'package:mobile_app/features/dashboard/data/dashboard_service.dart';
import 'package:mobile_app/services/auth_service.dart';
import 'package:mobile_app/features/notifications/presentation/notification_screen.dart';
import 'package:mobile_app/features/attendance/presentation/screens/fingerprint_scan_screen.dart';
import 'package:mobile_app/features/attendance/presentation/screens/attendance_history_screen.dart';
import 'package:mobile_app/features/timetable/presentation/timetable_screen.dart';

const _primary = Color(0xFF2563EB);
const _primaryDark = Color(0xFF0F172A);
const _surface = Color(0xFFF8FAFC);

enum AttendanceFlowState { notCheckedIn, checkedIn, checkedOut }

class MainShellScreen extends StatefulWidget {
  const MainShellScreen({super.key});

  @override
  State<MainShellScreen> createState() => _MainShellScreenState();
}

class _MainShellScreenState extends State<MainShellScreen>
    with WidgetsBindingObserver {
  int currentIndex = 0;
  int unreadNotificationCount = 0;
  bool _notificationsOpened = false;

  bool isLoading = true;
  bool isSecurityLoading = false;
  bool _securityEvaluationRunning = false;
  bool fingerprintPassed = false;
  bool otpVerified = false;
  bool checkoutIdentityVerified = false;
  int fingerprintAttempts = 0;
  bool _routeArgsApplied = false;
  Timer? _sessionTimer;

  Map<String, dynamic>? user;
  Map<String, dynamic>? activeSession;
  Map<String, dynamic>? attendanceStats;
  AttendanceFlowState attendanceState = AttendanceFlowState.notCheckedIn;
  AttendanceSecuritySnapshot? securitySnapshot;

  final attendanceService = AttendanceService();
  final dashboardService = DashboardService();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _loadInitialData();
    _sessionTimer = Timer.periodic(const Duration(seconds: 15), (_) {
    _loadInitialData();
  });

  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _sessionTimer?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _loadInitialData();
    }

  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_routeArgsApplied) return;
    final args =
        ModalRoute.of(context)?.settings.arguments as Map<String, dynamic>?;
    if (args == null) return;

    final attempts = args['fingerprintAttempts'];
    if (args['fingerprintPassed'] == true ||
        args['otpVerified'] == true ||
        attempts is int) {
      _routeArgsApplied = true;
      setState(() {
        if (args['fingerprintPassed'] == true) fingerprintPassed = true;
        if (args['otpVerified'] == true) otpVerified = true;
        if (attempts is int) fingerprintAttempts = attempts;
      });
    }
  }

  Future<void> _loadInitialData() async {
    await loadUser();
    await refreshSessionStatus(showSnack: false);
    await evaluateSecurity();


if (attendanceState == AttendanceFlowState.checkedIn &&
    (activeSession?['session_active'] == true ||
        activeSession?['can_check_out'] == true) &&
    securitySnapshot != null) {
  await attendanceService.updateLocation(
    latitude: securitySnapshot!.latitude,
    longitude: securitySnapshot!.longitude,
  );
}

    await loadAttendanceStats();
    await loadUnreadNotificationCount();



    if (mounted) {
    setState(() => isLoading = false);
    }
  }

  Future<void> loadUser() async {
    final result = await AuthService().fetchCurrentUser();
    if (!mounted) return;
    if (result['success'] == true) {
      setState(() => user = Map<String, dynamic>.from(result['user']));
      return;
    }
    await StorageService.clearSession();
    if (!mounted) return;
    Navigator.pushReplacementNamed(context, '/login');
  }

  Future<void> loadAttendanceStats() async {
  final token = await StorageService.getAccessToken();
  if (token == null) return;

  final result = await dashboardService.getStudentDashboard(token);

  if (!mounted) return;

  final data = Map<String, dynamic>.from(result['data'] ?? result);
  final dashboardData = Map<String, dynamic>.from(data['data'] ?? data);

  if (attendanceState == AttendanceFlowState.checkedIn &&
      dashboardData['session_active'] != true) {

    setState(() {
      attendanceStats = dashboardData;
});

    return;
  }

  setState(() {
    attendanceStats = dashboardData;
  });
}


  Future<void> evaluateSecurity() async {
  if (!mounted) return;

  // Prevent multiple GPS/security evaluations from running
  // at the same time.
  if (_securityEvaluationRunning) {
    print('SECURITY EVALUATION SKIPPED: already running');
    return;
  }

  _securityEvaluationRunning = true;

  setState(() => isSecurityLoading = true);

  try {
    final rawStart = activeSession?['start_time'];
    final rawEnd = activeSession?['end_time'];

    final DateTime? sessionStartTime =
        rawStart != null
            ? DateTime.tryParse(rawStart.toString())
            : null;

    final DateTime? sessionEndTime =
        rawEnd != null
            ? DateTime.tryParse(rawEnd.toString())
            : null;

    final snapshot = await AttendanceSecurityService.evaluate(
      detectedBeaconId: activeSession?['beacon_id'],

      sessionActive: activeSession?['session_active'] == true,

      sessionEnded: activeSession?['session_ended'] == true,

      canCheckOut: activeSession?['can_check_out'] == true,

      radiusMeters:
          (activeSession?['radius_meters'] as num?)?.toDouble() ?? 0,

      sessionLatitude:
          (activeSession?['latitude'] as num?)?.toDouble(),

      sessionLongitude:
          (activeSession?['longitude'] as num?)?.toDouble(),

      sessionStartTime: sessionStartTime,
      sessionEndTime: sessionEndTime,
    );

    if (!mounted) return;

    setState(() {
      securitySnapshot = snapshot;
      isSecurityLoading = false;
    });
  } catch (e) {
    if (!mounted) return;

    setState(() {
      isSecurityLoading = false;
    });

    print('SECURITY EVALUATION ERROR: $e');
  } finally {
    _securityEvaluationRunning = false;
  }
}

  Future<void> refreshSessionStatus({bool showSnack = true}) async {
  final result = await attendanceService.getActiveSession();

  if (!mounted) return;

  if (result['success'] != true) {
    setState(() {
      activeSession = null;
      attendanceState = AttendanceFlowState.notCheckedIn;
    });

    if (showSnack) {
      _snack('No attendance session available');
    }

    return;
  }

  final data = Map<String, dynamic>.from(
    result['data'] ?? {},
  );

  final sessionId = data['session_id'];

  final sessionExists = sessionId != null;

  final checkedIn =
      data['checked_in'] == true;

  final checkedOut =
      data['checked_out'] == true;

  // ============================================
// NO SESSION
// ============================================

if (!sessionExists) {
  setState(() {
    activeSession = null;
  });

  if (showSnack) {
    _snack(
      data['message']?.toString() ??
          'No attendance session available',
    );
  }

  return;
}

  // ============================================
  // SESSION EXISTS
  // Keep it even when lecturer ended it.
  // ============================================

  setState(() {
  activeSession = data;

  if (checkedOut) {
  attendanceState = AttendanceFlowState.checkedOut;

  // Do NOT reset checkoutIdentityVerified here.
  // It is cleared only after the local checkout flow
  // successfully completes.
}
   else if (checkedIn) {
  attendanceState = AttendanceFlowState.checkedIn;

  // Do NOT reset checkoutIdentityVerified here.
  //
  // The student may have already successfully
  // verified their identity for checkout.
  //
  // Background session refreshes must not invalidate
  // a successful verification.
}
  else {
    attendanceState = AttendanceFlowState.notCheckedIn;
  }
});
}
  int? get activeSessionId {
  final raw = activeSession?['session_id'];

  if (raw is int) {
    return raw;
  }

  return int.tryParse(raw?.toString() ?? '');
}
  bool get identitySessionAvailable {
  return activeSession?['session_id'] != null &&
      (
        activeSession?['session_active'] == true ||
        activeSession?['can_check_out'] == true
      );
}

  bool get hasActiveSession {
    return activeSessionId != null &&
      activeSession?['session_active'] == true;
}

  bool get hasEndedCheckoutSession {
    return activeSessionId != null &&
      activeSession?['session_ended'] == true &&
      activeSession?['can_check_out'] == true;
}

  bool get hasOpenSessionForCheckout {
    return hasActiveSession || hasEndedCheckoutSession;
}

  bool get identityVerified {
    return fingerprintPassed || otpVerified;
}
  bool canCheckOut() {
  final session = activeSession;

  if (session == null) {
    return false;
  }

  final checkedIn =
      session['checked_in'] == true ||
      attendanceState == AttendanceFlowState.checkedIn;

  final sessionEnded = session['session_ended'] == true;
  final canCheckout = session['can_check_out'] == true;

  return checkedIn && sessionEnded && canCheckout;
}

  // Once checked in, don't allow another check-in.
  bool canCheckIn() {
  if (!hasActiveSession) return false;

  if (attendanceState == AttendanceFlowState.checkedIn) {
    return false;
  }

  final snapshot = securitySnapshot;

  if (snapshot == null) return false;

  if (!snapshot.gpsValid) return false;
  if (!snapshot.geofenceValid) return false;
  if (snapshot.wifiStatus != 'Trusted') return false;
  if (!snapshot.bleDetected) return false;
  if (!snapshot.timeWindowValid) return false;

  return true;
}
double? distanceFromClassroom;

  List<String> missingSecuritySteps({required bool forCheckout}) {
    final snapshot = securitySnapshot;
    final missing = <String>[];
    if (snapshot == null) {
      missing.add('GPS validation has not completed');
      return missing;
    }
    if (!snapshot.gpsValid) {
      missing.add('GPS validation');
    }
    if (!snapshot.geofenceValid) {
      missing.add('Geofence validation');
    }
    if (snapshot.wifiStatus != 'Trusted') {
      missing.add('WiFi validation (ARUSOPASUANET)');
    }
    if (!snapshot.bleDetected) {
      if (!snapshot.bleDetected) {
  missing.add(
    'BLE validation (${activeSession?['beacon_id'] ?? 'class beacon'})',
  );
}
    }
    if (!snapshot.timeWindowValid) {
      missing.add('Valid attendance time window');
    }
    if (forCheckout) {
      if (!hasOpenSessionForCheckout) {
        missing.add('Active or open attendance session');
      }
    } else if (!hasActiveSession) {
      missing.add('Active attendance session');
    }
    if (forCheckout && !checkoutIdentityVerified ||
        !forCheckout && !identityVerified) {
      missing.add('Fingerprint success or OTP fallback verification');
    }
    return missing;
  }

  Future<void> openFingerprintScan({
  bool forCheckout = false,
}) async {
  if (!mounted) return;
  final snapshot = securitySnapshot;

if (snapshot == null ||
    !snapshot.gpsValid ||
    !snapshot.geofenceValid ||
    snapshot.wifiStatus != 'Trusted' ||
    !snapshot.bleDetected ||
    !snapshot.timeWindowValid) {
  _snack(
    'Complete GPS, geofence, Wi-Fi, BLE and time validation first.',
  );
  return;
}

  // BLOCK RE-SCANNING AFTER SUCCESSFUL VERIFICATION
  if (!forCheckout && (fingerprintPassed || otpVerified)) {
    return;
  }

  if (forCheckout && checkoutIdentityVerified) {
    return;
  }

  final verified = await Navigator.push<bool>(
    context,
    MaterialPageRoute<bool>(
      builder: (_) => const FingerprintScanScreen(),
      settings: RouteSettings(
        arguments: {
          'fingerprintAttempts': fingerprintAttempts,
        },
      ),
    ),
  );

  if (!mounted || verified != true) return;

  final verification =
      await AttendanceSecurityService().verifyFingerprint(
    success: true,
  );

  if (!mounted) return;

  if (verification['success'] == true) {
    setState(() {
      if (forCheckout) {
        checkoutIdentityVerified = true;
      } else {
        fingerprintPassed = true;
        otpVerified = false;
      }
    });

    _snack(
      forCheckout
          ? 'Checkout identity verified successfully'
          : 'Identity verified successfully',
    );
  } else {
    _snack('Fingerprint verification failed');
  }
}

  Future<void> startCheckIn() async {
  print("========== START CHECK IN ==========");

  await refreshSessionStatus(showSnack: false);

  if (!mounted) return;

  // 1. SECURITY
  await evaluateSecurity();

  if (!mounted) return;

  final snapshot = securitySnapshot;

  if (snapshot == null ||
      !snapshot.gpsValid ||
      !snapshot.geofenceValid ||
      snapshot.wifiStatus != 'Trusted' ||
      !snapshot.bleDetected ||
      !snapshot.timeWindowValid ||
      !hasActiveSession) {
    await showSecurityDialog(forCheckout: false);
    return;
  }

  print("SECURITY CHECKS PASSED");

  // 2. IDENTITY VERIFICATION
final identityVerified = fingerprintPassed || otpVerified;

print("FINGERPRINT PASSED: $fingerprintPassed");
print("OTP VERIFIED: $otpVerified");
print("IDENTITY VERIFIED: $identityVerified");

if (!identityVerified) {
  _snack('Fingerprint verification required');
  return;
}

  // 3. CHECK-IN
  final sessionId = activeSessionId;

  if (sessionId == null) {
    _snack('No attendance session available');
    return;
  }

  final result = await attendanceService.checkIn(
    sessionId: sessionId,
    latitude: snapshot.latitude,
    longitude: snapshot.longitude,
  );

  if (!mounted) return;

  print("CHECK-IN RESPONSE: $result");

  if (result['success'] == true) {
    setState(() {
      attendanceState = AttendanceFlowState.checkedIn;
    });

    _snack('Checked-in successfully');

    await refreshSessionStatus(showSnack: false);
    await loadAttendanceStats();

    return;
  }

  final data = result['data'];

  _snack(
    data is Map && data['error'] != null
        ? data['error'].toString()
        : 'Check-in failed',
  );
}
  Future<void> startCheckOut() async {
  if (!mounted) return;

  try {
    // =========================================================
    // 1. REFRESH SESSION
    // =========================================================

    await refreshSessionStatus(showSnack: false);

    if (!mounted) return;

    // =========================================================
    // 2. VERIFY THAT THE BACKEND ALLOWS CHECKOUT
    // =========================================================

    final session = activeSession;

    if (session == null) {
      _snack('No attendance session available');
      return;
    }

    final sessionId = session['session_id'];

    final checkedIn = session['checked_in'] == true;
    final checkedOut = session['checked_out'] == true;
    final canCheckout = session['can_check_out'] == true;
    final sessionEnded = session['session_ended'] == true;

    if (!checkedIn) {
      _snack('You are not checked in to this session');
      return;
    }

    if (checkedOut) {
      _snack('You have already checked out');
      return;
    }

    if (!sessionEnded || !canCheckout) {
      _snack('Checkout is only available after the lecturer ends the session');
      return;
    }

    if (sessionId == null) {
      _snack('Attendance session ID is missing');
      return;
    }

    // =========================================================
    // 3. GET CURRENT GPS
    // =========================================================

    await evaluateSecurity();

    if (!mounted) return;

    final snapshot = securitySnapshot;

    if (snapshot == null) {
      _snack('Unable to validate your location');
      return;
    }

    if (!snapshot.gpsValid) {
      _snack(snapshot.gpsMessage);
      return;
    }

    if (!snapshot.geofenceValid) {
      _snack(
        'You are outside the attendance area '
        '(${snapshot.distanceMeters.toStringAsFixed(1)} m away)',
      );
      return;
    }

    // =========================================================
    // 4. CHECKOUT SECURITY CONDITIONS
    // =========================================================

    if (snapshot.wifiStatus != 'Trusted') {
      _snack('Required WiFi validation failed');
      return;
    }

    if (!snapshot.bleDetected) {
      _snack('Required classroom beacon was not detected');
      return;
    }

    if (!snapshot.timeWindowValid) {
      _snack(snapshot.timeWindowMessage);
      return;
    }

    // =========================================================
// 5. FINGERPRINT MUST ALREADY BE VERIFIED
// =========================================================

    if (!checkoutIdentityVerified) {
        _snack('Please scan your fingerprint first');
        return;
    }

    // =========================================================
    // 6. SEND CHECKOUT REQUEST
    // =========================================================

    final result = await attendanceService.checkOut(
      sessionId: sessionId as int,
      latitude: snapshot.latitude,
      longitude: snapshot.longitude,
    );

    if (!mounted) return;

    // =========================================================
    // 7. HANDLE RESPONSE
    // =========================================================

    if (result['success'] == true) {
      setState(() {
        attendanceState = AttendanceFlowState.checkedOut;
        checkoutIdentityVerified = false;
      });

      _snack('Checked-out successfully');

      await Future.wait([
        refreshSessionStatus(showSnack: false),
        loadAttendanceStats(),
      ]);

      return;
    }

    final data = Map<String, dynamic>.from(
      result['data'] ?? {},
    );

    _snack(
      data['detail']?.toString() ??
          data['error']?.toString() ??
          data['message']?.toString() ??
          'Check-out failed',
    );
  } catch (error) {
    if (!mounted) return;

    _snack(
      error
          .toString()
          .replaceFirst('Exception: ', ''),
    );
  }
}


  Future<void> loadUnreadNotificationCount() async {
  final token = await StorageService.getAccessToken();

  if (token == null) return;

  final result = await dashboardService.getNotifications(token);

  if (!mounted) return;

  if (result['success'] == true) {
    final data = Map<String, dynamic>.from(
      result['data'] ?? {},
    );

    final count = data['unread_count'] ?? 0;

    // If the user has already opened notifications,
    // do not bring back the old unread count.
    if (_notificationsOpened && count > 0) {
      return;
    }

    setState(() {
      unreadNotificationCount = count;
    });
  }
}


  Future<void> showSecurityDialog({required bool forCheckout}) async {
    final missing = missingSecuritySteps(forCheckout: forCheckout);
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          missing.isEmpty
              ? 'Security checks complete'
              : 'Security checks pending',
        ),
        content: missing.isEmpty
            ? const Text(
                'All required checks passed. Attendance actions are enabled.',
              )
            : Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Complete these steps first:'),
                  const SizedBox(height: 12),
                  for (final step in missing)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Row(
                        children: [
                          const Icon(
                            Icons.error_outline,
                            color: Colors.orange,
                            size: 18,
                          ),
                          const SizedBox(width: 8),
                          Expanded(child: Text(step)),
                        ],
                      ),
                    ),
                ],
              ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
          if ((forCheckout ? !checkoutIdentityVerified : !identityVerified) &&
    activeSessionId != null)
  FilledButton(
    onPressed: () {
      Navigator.pop(context);
      openFingerprintScan(forCheckout: forCheckout);
    },
    child: const Text('Scan Fingerprint'),
  ),
        ],
      ),
    );
  }

  Future<void> refreshAll() async {
  await refreshSessionStatus(showSnack: false);
  await evaluateSecurity();
  await loadAttendanceStats();
}

  void _snack(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final tabs = [
      HomeTab(
        user: user,
        stats: attendanceStats,
        securitySnapshot: securitySnapshot,
        activeSession: activeSession,
        sessionAvailable: identitySessionAvailable,
        checkoutSessionOpen: hasEndedCheckoutSession,
        attendanceState: attendanceState,
        fingerprintPassed: fingerprintPassed,
        otpVerified: otpVerified,
        checkoutIdentityVerified: checkoutIdentityVerified,
        canCheckIn: canCheckIn(),
        canCheckOut: canCheckOut(),
        isSecurityLoading: isSecurityLoading,
        distanceFromClassroom: distanceFromClassroom,
        onRefresh: refreshAll,
        onFingerprint: openFingerprintScan,
        onCheckIn: startCheckIn,
        onCheckOut: startCheckOut,

      ),
      const TimetableScreen(),
      const AttendanceHistoryScreen(),
      NotificationScreen(
      onNotificationsRead: () {
    if (!mounted) return;

    setState(() {
      unreadNotificationCount = 0;
      _notificationsOpened = true;

    });
  },
),
      ProfileTab(user: user, onRefresh: loadUser),
    ];

    return Scaffold(
      backgroundColor: _surface,
      appBar: AppBar(
        title: const Text('GeoAttend'),
        backgroundColor: _primaryDark,
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : tabs[currentIndex],
      floatingActionButton: FloatingActionButton(
        backgroundColor: _primary,
        foregroundColor: Colors.white,
        tooltip: 'Security status check',
        onPressed: () => showSecurityDialog(
          forCheckout: attendanceState == AttendanceFlowState.checkedIn,
        ),
        child: const Icon(Icons.security_outlined),
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: currentIndex,
        selectedItemColor: _primary,
        unselectedItemColor: const Color(0xFF6B7D78),
        type: BottomNavigationBarType.fixed,
        onTap: (index) {
  setState(() {
    currentIndex = index;
  });
},
        items:[
          BottomNavigationBarItem(
            icon: Icon(Icons.home_outlined),
            label: 'Home',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.calendar_month_outlined),
            label: 'Timetable',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.fact_check_outlined),
            label: 'Attendance',
          ),
          BottomNavigationBarItem(
          icon: unreadNotificationCount > 0
      ? Badge(
          label: Text(
            unreadNotificationCount > 99
                ? '99+'
                : unreadNotificationCount.toString(),
          ),
          child: const Icon(
            Icons.notifications_active_outlined,
          ),
        )
      : const Icon(
          Icons.notifications_active_outlined,
        ),
  label: 'Notifications',
),
          BottomNavigationBarItem(
            icon: Icon(Icons.person_outline),
            label: 'Profile',
          ),
        ],
      ),
    );
  }
}

class HomeTab extends StatelessWidget {
  HomeTab({
    super.key,
    required this.user,
    required this.stats,
    required this.securitySnapshot,
    required this.activeSession,
    required this.sessionAvailable,
    required this.attendanceState,
    required this.fingerprintPassed,
    required this.otpVerified,
    required this.checkoutIdentityVerified,
    required this.checkoutSessionOpen,
    required this.canCheckIn,
    required this.canCheckOut,
    required this.isSecurityLoading,
    required this.onRefresh,
    required this.onFingerprint,
    required this.onCheckIn,
    required this.onCheckOut,
    required this.distanceFromClassroom,
  });

  final Map<String, dynamic>? user;
  final Map<String, dynamic>? stats;
  final AttendanceSecuritySnapshot? securitySnapshot;
  final bool sessionAvailable;
  final Map<String, dynamic>? activeSession;
  final AttendanceFlowState attendanceState;
  final bool fingerprintPassed;
  final bool otpVerified;
  final bool checkoutIdentityVerified;
  final bool checkoutSessionOpen;
  final bool canCheckIn;
  final bool canCheckOut;
  final bool isSecurityLoading;
  final double? distanceFromClassroom;
  final Future<void> Function() onRefresh;
  final Future<void> Function({
  bool forCheckout,
  }) onFingerprint;
  final VoidCallback onCheckIn;
  final VoidCallback onCheckOut;


  @override
  Widget build(BuildContext context) {
    final name = _fullName(user, stats);
    final statusLabel = _sessionStatusLabel(activeSession);
    final statusColor = _sessionStatusColor(statusLabel);
    final attendancePercent = _asDouble(stats?['percentage']);
    final attendanceStatus =
        stats?['status']?.toString() ??
        (attendancePercent >= 75 ? 'Fine' : 'Critical');
    final attendanceColor = attendanceStatus == 'Fine'
        ? Colors.green
        : Colors.redAccent;



    return RefreshIndicator(
      onRefresh: onRefresh,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              gradient: const LinearGradient(colors: [_primary, _primaryDark]),
              borderRadius: BorderRadius.circular(24),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const CircleAvatar(
                      backgroundColor: Colors.white24,
                      child: Icon(Icons.school_outlined, color: Colors.white),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'Hello, $name',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: _SummaryTile(
            label: 'Session',
                        value: statusLabel,
                        accent: statusColor,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _SummaryTile(
                        label: 'Attendance',
                        value: '${attendancePercent.toStringAsFixed(1)}%',
                        accent: attendanceColor,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          _AttendanceStatsCard(
            stats: stats,
            status: attendanceStatus,
            color: attendanceColor,
          ),
          const SizedBox(height: 12),
          _SessionCard(
            session: activeSession,
            statusLabel: statusLabel,
            statusColor: statusColor,
            attendanceState: attendanceState,
          ),
          const SizedBox(height: 12),
          _GeoAttendStatusCard(
          snapshot: securitySnapshot,
          isLoading: isSecurityLoading,
          distanceFromClassroom: securitySnapshot?.distanceMeters,
          hasActiveSession: sessionAvailable,
          attendanceState: attendanceState,
          hasOpenSessionForCheckout:
          activeSession?['session_id'] != null &&
          (
          activeSession?['session_active'] == true ||
          (
          activeSession?['session_ended'] == true &&
          activeSession?['can_check_out'] == true
          )
        ),
    ),
          const SizedBox(height: 12),
          _ConnectivityStatusCard(
            snapshot: securitySnapshot,
            sessionAvailable: activeSession != null,
          ),
          const SizedBox(height: 12),
        _IdentityVerificationCard(
  snapshot: securitySnapshot,
  sessionAvailable: sessionAvailable,

  // Once checkout fingerprint succeeds, remain in checkout
  // verification mode until checkout is completed.
  checkoutMode: checkoutSessionOpen || checkoutIdentityVerified,

  verified: checkoutIdentityVerified ||
      (!checkoutIdentityVerified &&
          !checkoutSessionOpen &&
          (fingerprintPassed || otpVerified)),

  verifiedByOtp: !checkoutIdentityVerified &&
      !checkoutSessionOpen &&
      otpVerified,

  onFingerprint: onFingerprint,
),

          const SizedBox(height: 12),
          _AttendanceOverviewCard(
            canCheckIn: canCheckIn,
            canCheckOut: canCheckOut,
            onCheckIn: onCheckIn,
            onCheckOut: onCheckOut,
          ),
        ],
      ),
    );
  }
}

class AttendanceTab extends StatelessWidget {
  const AttendanceTab({
    super.key,
    required this.onCheckIn,
    required this.onCheckOut,
    required this.canCheckIn,
    required this.canCheckOut,
  });
  final VoidCallback onCheckIn;
  final VoidCallback onCheckOut;
  final bool canCheckIn;
  final bool canCheckOut;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _AttendanceOverviewCard(
          canCheckIn: canCheckIn,
          canCheckOut: canCheckOut,
          onCheckIn: onCheckIn,
          onCheckOut: onCheckOut,
        ),
      ],
    );
  }
}


class ProfileTab extends StatelessWidget {
  const ProfileTab({super.key, required this.user, required this.onRefresh});
  final Map<String, dynamic>? user;
  final Future<void> Function() onRefresh;
  @override
  Widget build(BuildContext context) {
    final profile = Map<String, dynamic>.from(user?['profile'] ?? {});
    String value(String key, [String fallback = '-']) =>
        (profile[key] ?? user?[key])?.toString() ?? fallback;
    return ListView(
    padding: const EdgeInsets.all(16),
    children: [
      _GlassCard(
        title: 'Profile',
        icon: Icons.person_outline,
        accent: _primary,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _fullName(user, null),
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            Text(user?['email']?.toString() ?? ''),
            const SizedBox(height: 16),
            _MetricRow(label: 'Registration Number', value: value('reg_number')),
            _MetricRow(label: 'Email', value: value('email')),
            _MetricRow(label: 'Course', value: value('course')),
            _MetricRow(label: 'Department', value: value('department')),
            _MetricRow(label: 'Phone Number', value: value('phone_number')),
            const SizedBox(height: 8),
            FilledButton.icon(
              onPressed: onRefresh,
              icon: const Icon(Icons.refresh),
              label: const Text('Refresh profile'),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: () async {
                await AuthService().logout();
                if (context.mounted) {
                  Navigator.pushReplacementNamed(context, '/login');
                }
              },
              icon: const Icon(Icons.logout),
              label: const Text('Logout'),
            ),
          ],
        ),
      ),
    ],
  );
  }
}

class _AttendanceStatsCard extends StatelessWidget {
  const _AttendanceStatsCard({
    required this.stats,
    required this.status,
    required this.color,
  });
  final Map<String, dynamic>? stats;
  final String status;
  final Color color;
  @override
  Widget build(BuildContext context) {
    return _GlassCard(
      title: 'Attendance Status',
      icon: Icons.bar_chart_outlined,
      accent: color,
      child: Column(
        children: [
          _MetricRow(
            label: 'Attendance Percentage',
            value: '${_asDouble(stats?['percentage']).toStringAsFixed(1)}%',
            valueColor: color,
          ),
          _MetricRow(label: 'Status', value: status, valueColor: color),
          _MetricRow(
            label: 'Total Sessions',
            value: (stats?['total_sessions'] ?? 0).toString(),
          ),
          _MetricRow(
            label: 'Attended Sessions',
            value: (stats?['attended_sessions'] ?? stats?['present'] ?? 0)
                .toString(),
          ),
        ],
      ),
    );
  }
}

class _SessionCard extends StatelessWidget {
  const _SessionCard({
    required this.session,
    required this.statusLabel,
    required this.statusColor,
    required this.attendanceState,
  });
  final Map<String, dynamic>? session;
  final String statusLabel;
  final Color statusColor;
  final AttendanceFlowState attendanceState;
  @override
  Widget build(BuildContext context) {
    return _GlassCard(
      title: 'Session Status',
      icon: Icons.event_available_outlined,
      accent: statusColor,
      child: Column(
        children: [
          _MetricRow(
            label: 'Current session',
            value: statusLabel,
            valueColor: statusColor,
          ),
          _MetricRow(
            label: 'Subject',
            value:
                session?['subject']?.toString() ??
                'No active attendance session available',
          ),
          _MetricRow(
            label: 'Course',
            value: session?['course']?.toString() ?? '-',
          ),
          _MetricRow(
            label: 'Your state',
            value: _attendanceStateLabel(attendanceState),
          ),
        ],
      ),
    );
  }
}

class _GeoAttendStatusCard extends StatelessWidget {
  const _GeoAttendStatusCard({
    required this.snapshot,
    required this.isLoading,
    required this.distanceFromClassroom,
    required this.hasActiveSession,
    required this.hasOpenSessionForCheckout,
    required this.attendanceState,
  });

  final AttendanceSecuritySnapshot? snapshot;
  final bool isLoading;
  final double? distanceFromClassroom;
  final bool hasActiveSession;
  final bool hasOpenSessionForCheckout;
  final AttendanceFlowState attendanceState;

  @override
  Widget build(BuildContext context) {
    final hasEndedCheckout =
        snapshot?.sessionEnded == true &&
        snapshot?.canCheckOut == true;

    // A session can be either:
    // 1. currently active, OR
    // 2. ended but still available for student checkout.
    final sessionAvailable =
        hasActiveSession || hasOpenSessionForCheckout;

    final valid =
        sessionAvailable &&
        snapshot?.gpsValid == true &&
        snapshot?.geofenceValid == true;

    String geofenceStatus;

if (attendanceState == AttendanceFlowState.checkedOut) {
  geofenceStatus = '-';
} else if (snapshot == null) {
  geofenceStatus = 'Checking location...';
} else if (!snapshot!.gpsValid) {
  geofenceStatus = 'GPS validation pending';
} else if (!sessionAvailable) {
  geofenceStatus = 'No attendance session';
} else if (!snapshot!.geofenceValid) {
  geofenceStatus = 'Outside geofence';
} else if (hasEndedCheckout) {
  geofenceStatus = 'Inside Geofence - Checkout available';
} else {
  geofenceStatus = 'Inside Geofence confirmed';
}

    return _GlassCard(
      title: 'Geo Attend Status',
      icon: Icons.location_on_outlined,
      accent: valid ? Colors.green : Colors.orange,
      child: isLoading
          ? const Center(
              child: CircularProgressIndicator(),
            )
          : Column(
              children: [
                _MetricRow(
                  label: 'Distance',
                  value: attendanceState == AttendanceFlowState.checkedOut
                  ? '-'
                  : snapshot != null
                   ? '${snapshot!.distanceMeters.toStringAsFixed(1)} m'
                    : '-',
         ),

                _MetricRow(
                    label: 'Radius',
                    value: attendanceState == AttendanceFlowState.checkedOut
                    ? '-'
                    : snapshot != null
                    ? '${snapshot!.radiusMeters.toStringAsFixed(0)} m'
                    : '-',
                  ),

                _MetricRow(
                  label: 'Geofence status',
                  value: geofenceStatus,
                  valueColor: valid
                      ? Colors.green
                      : Colors.redAccent,
                ),
              ],
            ),
    );
  }
}

class _ConnectivityStatusCard extends StatelessWidget {
  const _ConnectivityStatusCard({
    required this.snapshot,
    required this.sessionAvailable,
  });

  final AttendanceSecuritySnapshot? snapshot;
  final bool sessionAvailable;

  @override
  Widget build(BuildContext context) {

    final wifiValid =
        sessionAvailable &&
        snapshot?.wifiStatus == 'Trusted';

    return _GlassCard(
      title: 'Campus Network',
      icon: Icons.wifi_outlined,
      accent: wifiValid ? Colors.green : Colors.orange,
      child: Column(
        children: [
          _MetricRow(
            label: 'WiFi',
            value: !sessionAvailable
                ? 'Waiting for session'
                : snapshot?.wifiLabel ?? 'Campus network',
          ),

          _MetricRow(
            label: 'Status',
            value: !sessionAvailable
                ? 'Waiting for session'
                : snapshot?.wifiStatus ?? 'Checking',
            valueColor: wifiValid
                ? Colors.green
                : Colors.orange,
          ),
        ],
      ),
    );
  }
}

class _IdentityVerificationCard extends StatelessWidget {
const _IdentityVerificationCard({
required this.snapshot,
required this.sessionAvailable,
required this.checkoutMode,
required this.verified,
required this.verifiedByOtp,
required this.onFingerprint,
});

final AttendanceSecuritySnapshot? snapshot;
final bool sessionAvailable;
final bool checkoutMode;
final bool verified;
final bool verifiedByOtp;
final Future<void> Function({
  bool forCheckout,
}) onFingerprint;

@override
Widget build(BuildContext context) {
final securityReady =
sessionAvailable &&
snapshot?.geofenceValid == true &&
snapshot?.wifiStatus == 'Trusted' &&
snapshot?.bleDetected == true;


return _GlassCard(
  title: 'Security Verification',
  icon: Icons.verified_user_outlined,
  accent: verified ? Colors.green : Colors.amber,
  child: Column(
    children: [
      _MetricRow(
        label: 'GPS',
        value: !sessionAvailable
            ? 'Waiting for session'
            : snapshot?.gpsValid == true
                ? 'Confirmed'
                : 'Pending',
        valueColor:
            sessionAvailable && snapshot?.gpsValid == true
                ? Colors.green
                : Colors.orange,
      ),

      _MetricRow(
        label: 'WiFi',
        value: !sessionAvailable
            ? 'Waiting for session'
            : snapshot?.wifiLabel ?? 'Pending',
        valueColor:
            sessionAvailable &&
                    snapshot?.wifiStatus == 'Trusted'
                ? Colors.green
                : Colors.orange,
      ),

      _MetricRow(
        label: 'BLE',
        value: !sessionAvailable
            ? 'Waiting for session'
            : snapshot?.bleStatus ?? 'Pending',
        valueColor:
            snapshot?.bleDetected == true
                ? Colors.green
                : Colors.orange,
      ),

      _MetricRow(
  label: 'Biometrics',
  value: !sessionAvailable
      ? 'Not required'
      : verified
          ? (verifiedByOtp
              ? 'OTP verified'
              : 'Fingerprint verified')
          : 'Pending',
  valueColor: !sessionAvailable
      ? Colors.grey
      : verified
          ? Colors.green
          : Colors.orange,
),

      const SizedBox(height: 14),

      SizedBox(
        width: 128,
        height: 128,
        child: FilledButton(
          style: FilledButton.styleFrom(
            backgroundColor:
                verified ? Colors.green : _primary,
            foregroundColor: Colors.white,
            shape: const CircleBorder(),
          ),

          // Do NOT open fingerprint again after verification.
          onPressed: securityReady && !verified
          ? () async {
          await onFingerprint(
          forCheckout: checkoutMode,
        );
      }
    : null,

          child: Icon(
  !sessionAvailable
      ? Icons.event_busy
      : verifiedByOtp
          ? Icons.sms_outlined
          : verified
              ? Icons.verified
              : Icons.fingerprint,
  size: 64,
),
        ),
      ),

      const SizedBox(height: 12),

      FilledButton.icon(
        onPressed: securityReady && !verified
        ? () async {
        await onFingerprint(
          forCheckout: checkoutMode,
        );
      }
    : null,
        icon: Icon(
          verified
              ? Icons.check_circle
              : Icons.fingerprint,
        ),
        label: Text(
  !sessionAvailable
      ? 'No Session Available'
      : verified
          ? 'Identity Verified'
          : 'Scan Fingerprint',
),
      ),
    ],
  ),
);

}
}


class _AttendanceOverviewCard extends StatelessWidget {
  const _AttendanceOverviewCard({
    required this.canCheckIn,
    required this.canCheckOut,
    required this.onCheckIn,
    required this.onCheckOut,
  });
  final bool canCheckIn;
  final bool canCheckOut;
  final VoidCallback onCheckIn;
  final VoidCallback onCheckOut;
  @override
  Widget build(BuildContext context) {
    return _GlassCard(
      title: 'Attendance Actions',
      icon: Icons.touch_app_outlined,
      accent: _primary,
      child: Row(
        children: [
          Expanded(
            child: FilledButton.icon(
              onPressed: canCheckIn ? onCheckIn : null,
              icon: const Icon(Icons.login),
              label: const Text('Check In'),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: OutlinedButton.icon(
              onPressed: canCheckOut ? onCheckOut : null,
              icon: const Icon(Icons.logout),
              label: const Text('Check Out'),
            ),
          ),
        ],
      ),
    );
  }
}

class _GlassCard extends StatelessWidget {
  const _GlassCard({
    required this.title,
    required this.icon,
    required this.accent,
    required this.child,
  });
  final String title;
  final IconData icon;
  final Color accent;
  final Widget child;
  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      color: Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  backgroundColor: accent.withValues(alpha: 0.12),
                  child: Icon(icon, color: accent, size: 20),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    title,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            child,
          ],
        ),
      ),
    );
  }
}

class _MetricRow extends StatelessWidget {
  const _MetricRow({required this.label, required this.value, this.valueColor});
  final String label;
  final String value;
  final Color? valueColor;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: const TextStyle(color: Color(0xFF64748B)),
            ),
          ),
          Flexible(
            child: Text(
              value,
              textAlign: TextAlign.right,
              style: TextStyle(
                fontWeight: FontWeight.w700,
                color: valueColor ?? const Color(0xFF0F172A),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SummaryTile extends StatelessWidget {
  const _SummaryTile({
    required this.label,
    required this.value,
    required this.accent,
  });
  final String label;
  final String value;
  final Color accent;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(color: Color(0xFFE2E8F0), fontSize: 12),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              color: accent == Colors.green
                  ? const Color(0xFFBBF7D0)
                  : Colors.white,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

String _fullName(Map<String, dynamic>? user, Map<String, dynamic>? stats) {
  final statName = stats?['name']?.toString() ?? '';
  if (statName.trim().isNotEmpty) return statName;
  final fullName = user?['full_name']?.toString() ?? '';
  if (fullName.trim().isNotEmpty) return fullName;
  return user?['username']?.toString() ?? 'User';
}

String _sessionStatusLabel(
  Map<String, dynamic>? session,
) {
  if (session == null) {
    return 'No Session';
  }

  if (session['session_ended'] == true &&
      session['can_check_out'] == true) {
    return 'Ended';
  }

  if (session['session_active'] == true) {
    return 'Active';
  }

  if (session['session_ended'] == true) {
    return 'Ended';
  }

  return 'No Session';
}

Color _sessionStatusColor(String label) {
  if (label == 'Active') {
    return Colors.green;
  }

  if (label == 'Ended') {
    return Colors.orange;
  }

  if (label == 'No Session') {
    return Colors.redAccent;
  }

  return Colors.orange;
}

String _attendanceStateLabel(AttendanceFlowState state) {
  switch (state) {
    case AttendanceFlowState.checkedIn:
      return 'Checked In';
    case AttendanceFlowState.checkedOut:
      return 'Checked Out';
    case AttendanceFlowState.notCheckedIn:
      return 'Pending';
  }
}

double _asDouble(dynamic value) {
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '') ?? 0;
}
