import 'dart:convert';

import 'package:http/http.dart' as http;

import 'package:mobile_app/core/storage/storage_service.dart';

class TimetableService {
  

  Future<Map<String, dynamic>> fetchMyTimetable() async {
    final token = await StorageService.getAccessToken();

    final response = await http.get(
      Uri.parse(
        'https://attendance-system-production-5479.up.railway.app/api/courses/timetable/my/',
      ),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }

    if (response.statusCode == 401) {
      throw Exception('Authentication expired. Please log in again.');
    }

    throw Exception(
      'Failed to load timetable. Status: ${response.statusCode}',
    );
  }
}