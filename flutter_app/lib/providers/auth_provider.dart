import 'package:flutter/material.dart';
import '../config/app_config.dart';
import '../models/user_model.dart';
import '../services/api_service.dart';

class AuthProvider extends ChangeNotifier {
  UserModel? user;
  bool isLoading = false;
  String? error;

  bool get isLoggedIn => user != null;

  Future<bool> requestOtp(String phone) async {
    isLoading = true;
    error = null;
    notifyListeners();
    try {
      await ApiService.requestOtp(phone);
      isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      error = e.toString();
      isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> login(String phone, String otp) async {
    isLoading = true;
    error = null;
    notifyListeners();
    try {
      final res = await ApiService.login(phone, otp);
      if (res['token'] != null) {
        await AppConfig.setAuthToken(res['token']);
        user = UserModel.fromJson(res['user']);
        isLoading = false;
        notifyListeners();
        return true;
      }
      error = res['detail'] ?? 'Login failed';
      isLoading = false;
      notifyListeners();
      return false;
    } catch (e) {
      error = e.toString();
      isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<void> logout() async {
    await AppConfig.clearAuth();
    user = null;
    notifyListeners();
  }

  Future<bool> checkSession() async {
    final token = await AppConfig.getAuthToken();
    return token != null;
  }
}
