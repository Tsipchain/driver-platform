import 'package:flutter/material.dart';
import '../models/drone_model.dart';
import '../services/api_service.dart';

class DroneProvider extends ChangeNotifier {
  List<DroneModel> drones = [];
  List<DroneMission> activeMissions = [];
  DroneModel? selectedDrone;
  bool isLoading = false;

  Future<void> loadDashboard() async {
    isLoading = true;
    notifyListeners();
    try {
      final res = await ApiService.getDroneDashboard();
      drones = (res['drones'] as List?)
              ?.map((d) => DroneModel.fromJson(d))
              .toList() ??
          [];
      activeMissions = (res['active_missions'] as List?)
              ?.map((m) => DroneMission.fromJson(m))
              .toList() ??
          [];
    } catch (_) {}
    isLoading = false;
    notifyListeners();
  }

  Future<DroneMission?> createMission({
    required String droneId,
    required String pickupAddress,
    required String deliveryAddress,
    required double packageWeight,
    required String description,
  }) async {
    try {
      final res = await ApiService.createDroneMission({
        'drone_id': droneId,
        'pickup_address': pickupAddress,
        'delivery_address': deliveryAddress,
        'package_weight_kg': packageWeight,
        'description': description,
      });
      final mission = DroneMission.fromJson(res);
      activeMissions.add(mission);
      notifyListeners();
      return mission;
    } catch (_) {
      return null;
    }
  }

  Future<void> loadTelemetry(String droneId) async {
    try {
      final res = await ApiService.getDroneTelemetry(droneId);
      selectedDrone = DroneModel.fromJson(res);
      notifyListeners();
    } catch (_) {}
  }
}
