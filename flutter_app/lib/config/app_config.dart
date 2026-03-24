import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AppConfig {
  static late SharedPreferences prefs;
  static const storage = FlutterSecureStorage();

  static const String apiBase = 'https://driver-platform-production.up.railway.app';
  static const String verifyApiBase = 'https://thronos-verifyid-production.up.railway.app';
  static const String wsEndpoint = 'wss://thronos-verifyid-production.up.railway.app/api/v1/video-calls/ws';
  static const String blockchainRpcUrl = 'https://rpc.thronos.io';
  static const String tokenSymbol = 'THR';

  static Future<void> init() async {
    prefs = await SharedPreferences.getInstance();
  }

  static Future<String?> getAuthToken() async {
    return await storage.read(key: 'auth_token');
  }

  static Future<void> setAuthToken(String token) async {
    await storage.write(key: 'auth_token', value: token);
  }

  static Future<void> clearAuth() async {
    await storage.deleteAll();
  }
}
