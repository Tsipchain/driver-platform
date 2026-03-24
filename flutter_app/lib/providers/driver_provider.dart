import 'package:flutter/material.dart';
import '../models/trip_model.dart';
import '../services/api_service.dart';

class DriverProvider extends ChangeNotifier {
  bool isOnline = false;
  String currentMode = 'taxi';
  Map<String, dynamic>? dashboardData;
  List<TripModel> availableTrips = [];
  TripModel? activeTrip;
  bool isLoading = false;

  Future<void> loadDashboard() async {
    isLoading = true;
    notifyListeners();
    try {
      dashboardData = await ApiService.getDashboard();
    } catch (_) {}
    isLoading = false;
    notifyListeners();
  }

  Future<void> toggleOnline(bool online) async {
    try {
      await ApiService.updateStatus(online, currentMode);
      isOnline = online;
      notifyListeners();
    } catch (_) {}
  }

  void setMode(String mode) {
    currentMode = mode;
    notifyListeners();
  }

  Future<void> loadAvailableTrips() async {
    try {
      final res = await ApiService.getAvailableTrips(currentMode);
      availableTrips = (res['trips'] as List?)
              ?.map((t) => TripModel.fromJson(t))
              .toList() ??
          [];
      notifyListeners();
    } catch (_) {}
  }

  Future<void> acceptTrip(String tripId) async {
    try {
      final res = await ApiService.acceptTrip(tripId);
      activeTrip = TripModel.fromJson(res['trip']);
      notifyListeners();
    } catch (_) {}
  }

  Future<void> completeTrip(String tripId) async {
    try {
      final res = await ApiService.completeTrip(tripId);
      activeTrip = TripModel.fromJson(res['trip']);
      notifyListeners();
    } catch (_) {}
  }
}
