
import 'dart:convert';


import 'package:http/http.dart' as http;
import 'package:mobile_app/core/constants/api_constants.dart';
import 'package:mobile_app/core/storage/storage_service.dart';

class AttendanceService {
  Map<String, dynamic> _decode(String body) {
    if (body.trim().isEmpty) {
      return {};
    }

    try {
      final decoded = jsonDecode(body);

      if (decoded is Map<String, dynamic>) {
        return decoded;
      }

      return {'data': decoded};
    } catch (e) {
      print("JSON DECODE ERROR: $e");
      print("RESPONSE WAS: ${body.substring(0, body.length > 500 ? 500 : body.length)}");

      return {
        "error": "Server returned invalid JSON",
        "raw_response":
            body.substring(0, body.length > 500 ? 500 : body.length),
      };
    }
  }

  Future<Map<String, dynamic>> getActiveSession() async {
    final token = await StorageService.getToken();

    final url =
        "${ApiConstants.baseUrl}attendance/active-session/";

    print("ACTIVE SESSION URL: $url");
    print("ACTIVE SESSION TOKEN EXISTS: ${token != null && token.isNotEmpty}");

    final response = await http.get(
      Uri.parse(url),
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer $token",
        "Accept": "application/json",
      },
    );

    print("ACTIVE SESSION STATUS: ${response.statusCode}");
    print(
      "ACTIVE SESSION BODY: ${response.body.substring(0, response.body.length > 500 ? 500 : response.body.length)}",
    );

    return {
      "success": response.statusCode >= 200 &&
          response.statusCode < 300,
      "statusCode": response.statusCode,
      "data": _decode(response.body),
    };
  }

  Future<Map<String, dynamic>> checkIn({
    required int sessionId,
    required double latitude,
    required double longitude,
  }) async {
    final token = await StorageService.getToken();

    final response = await http.post(
      Uri.parse("${ApiConstants.baseUrl}attendance/check-in/"),
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer $token",
        "Accept": "application/json",
      },
      body: jsonEncode({
        "session_id": sessionId,
        "latitude": latitude,
        "longitude": longitude,
        "wifi_bssid": "ARUSOPASUANET",
        "beacon_id": "Beacon 1C",
      }),
    );

    print("CHECK-IN STATUS: ${response.statusCode}");
    print("CHECK-IN BODY: ${response.body}");

    return {
      "success": response.statusCode >= 200 &&
          response.statusCode < 300,
      "statusCode": response.statusCode,
      "data": _decode(response.body),
    };
  }

  Future<Map<String, dynamic>> verifyFingerprint({
    required bool success,
  }) async {
    final token = await StorageService.getToken();

    final response = await http.post(
      Uri.parse(
        "${ApiConstants.baseUrl}auth/fingerprint/verify/",
      ),
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer $token",
        "Accept": "application/json",
      },
      body: jsonEncode({
        "success": success,
      }),
    );

    print("FINGERPRINT STATUS: ${response.statusCode}");
    print("FINGERPRINT BODY: ${response.body}");

    return {
      "success": response.statusCode >= 200 &&
          response.statusCode < 300,
      "statusCode": response.statusCode,
      "data": _decode(response.body),
    };
  }

  Future<Map<String, dynamic>> checkOut({
    required int sessionId,
    required double latitude,
    required double longitude,
  }) async {
    final token = await StorageService.getToken();

    final response = await http.post(
      Uri.parse("${ApiConstants.baseUrl}attendance/check-out/"),
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer $token",
        "Accept": "application/json",
      },
      body: jsonEncode({
        "session_id": sessionId,
        "latitude": latitude,
        "longitude": longitude,
        "wifi_bssid": "ARUSOPASUANET",
        "beacon_id": "Beacon 1C",
      }),
    );

    print("CHECK-OUT STATUS: ${response.statusCode}");
    print("CHECK-OUT BODY: ${response.body}");

    return {
      "success": response.statusCode >= 200 &&
          response.statusCode < 300,
      "statusCode": response.statusCode,
      "data": _decode(response.body),
    };
  }

    Future<Map<String, dynamic>> updateLocation({
    required double latitude,
    required double longitude,
  }) async {
    final token = await StorageService.getToken();

    final response = await http.post(
      Uri.parse(
        "${ApiConstants.baseUrl}attendance/location-update/",
      ),
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer $token",
        "Accept": "application/json",
      },
      body: jsonEncode({
        "latitude": latitude,
        "longitude": longitude,
        "wifi_valid": true,
        "beacon_valid": true,
      }),
    );

    print("LOCATION UPDATE STATUS: ${response.statusCode}");
    print("LOCATION UPDATE BODY: ${response.body}");

    return {
      "success": response.statusCode >= 200 &&
          response.statusCode < 300,
      "statusCode": response.statusCode,
      "data": _decode(response.body),
    };
  }

  Future<Map<String, dynamic>> markAttendance({
    required int sessionId,
  }) async {
    final token = await StorageService.getToken();

    final response = await http.post(
      Uri.parse("${ApiConstants.baseUrl}attendance/mark/"),
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer $token",
        "Accept": "application/json",
      },
      body: jsonEncode({
        "session_id": sessionId,
      }),
    );

    print("MARK ATTENDANCE STATUS: ${response.statusCode}");
    print("MARK ATTENDANCE BODY: ${response.body}");

    return {
      "success": response.statusCode >= 200 &&
          response.statusCode < 300,
      "statusCode": response.statusCode,
      "data": _decode(response.body),
    };
  }
}

Future<Map<String, dynamic>> getAttendanceHistory() async {

  try {

    final token = await StorageService.getAccessToken();

    if (token == null) {
      return {
        "success": false,
        "error": "No authentication token found",
      };
    }


    final url = Uri.parse(
      "${ApiConstants.baseUrl}attendance/history/",
    );


    final response = await http.get(
      url,
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer $token",
      },
    );


    final body = response.body.isEmpty
        ? {}
        : jsonDecode(response.body);


    return {
      "success": response.statusCode == 200,
      "data": body,
    };


  } catch (e) {

    return {
      "success": false,
      "error": e.toString(),
    };

  }

}

