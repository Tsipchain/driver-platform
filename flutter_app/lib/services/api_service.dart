import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/app_config.dart';

class ApiService {
  static final _client = http.Client();

  static Future<Map<String, String>> _headers() async {
    final token = await AppConfig.getAuthToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  // Auth
  static Future<Map<String, dynamic>> requestOtp(String phone) async {
    final res = await _client.post(
      Uri.parse('${AppConfig.apiBase}/api/auth/request-otp'),
      headers: await _headers(),
      body: jsonEncode({'phone': phone}),
    );
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> login(String phone, String otp) async {
    final res = await _client.post(
      Uri.parse('${AppConfig.apiBase}/api/auth/login'),
      headers: await _headers(),
      body: jsonEncode({'phone': phone, 'otp': otp}),
    );
    return jsonDecode(res.body);
  }

  // Driver
  static Future<Map<String, dynamic>> getDashboard() async {
    final res = await _client.get(
      Uri.parse('${AppConfig.apiBase}/api/driver/dashboard'),
      headers: await _headers(),
    );
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> updateStatus(bool online, String mode) async {
    final res = await _client.post(
      Uri.parse('${AppConfig.apiBase}/api/driver/status'),
      headers: await _headers(),
      body: jsonEncode({'online': online, 'mode': mode}),
    );
    return jsonDecode(res.body);
  }

  // Trips
  static Future<Map<String, dynamic>> getAvailableTrips(String mode) async {
    final res = await _client.get(
      Uri.parse('${AppConfig.apiBase}/api/trips/available?mode=$mode'),
      headers: await _headers(),
    );
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> acceptTrip(String tripId) async {
    final res = await _client.post(
      Uri.parse('${AppConfig.apiBase}/api/trips/$tripId/accept'),
      headers: await _headers(),
    );
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> startTrip(String tripId) async {
    final res = await _client.post(
      Uri.parse('${AppConfig.apiBase}/api/trips/$tripId/start'),
      headers: await _headers(),
    );
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> completeTrip(String tripId) async {
    final res = await _client.post(
      Uri.parse('${AppConfig.apiBase}/api/trips/$tripId/complete'),
      headers: await _headers(),
    );
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> getTripHistory() async {
    final res = await _client.get(
      Uri.parse('${AppConfig.apiBase}/api/trips/history'),
      headers: await _headers(),
    );
    return jsonDecode(res.body);
  }

  // School
  static Future<Map<String, dynamic>> getSchoolDashboard() async {
    final res = await _client.get(
      Uri.parse('${AppConfig.apiBase}/api/school/dashboard'),
      headers: await _headers(),
    );
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> enrollStudent(String name, String phone, String email) async {
    final res = await _client.post(
      Uri.parse('${AppConfig.apiBase}/api/school/students/enroll'),
      headers: await _headers(),
      body: jsonEncode({'name': name, 'phone': phone, 'email': email}),
    );
    return jsonDecode(res.body);
  }

  // Transport
  static Future<Map<String, dynamic>> getTransportJobs() async {
    final res = await _client.get(
      Uri.parse('${AppConfig.apiBase}/api/transport/jobs'),
      headers: await _headers(),
    );
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> createTransportJob(Map<String, dynamic> data) async {
    final res = await _client.post(
      Uri.parse('${AppConfig.apiBase}/api/transport/jobs/create'),
      headers: await _headers(),
      body: jsonEncode(data),
    );
    return jsonDecode(res.body);
  }

  // Drone
  static Future<Map<String, dynamic>> getDroneDashboard() async {
    final res = await _client.get(
      Uri.parse('${AppConfig.apiBase}/api/drone/dashboard'),
      headers: await _headers(),
    );
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> createDroneMission(Map<String, dynamic> data) async {
    final res = await _client.post(
      Uri.parse('${AppConfig.apiBase}/api/drone/missions/create'),
      headers: await _headers(),
      body: jsonEncode(data),
    );
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> getDroneTelemetry(String droneId) async {
    final res = await _client.get(
      Uri.parse('${AppConfig.apiBase}/api/drone/$droneId/telemetry'),
      headers: await _headers(),
    );
    return jsonDecode(res.body);
  }
}
