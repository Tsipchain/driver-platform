class DroneModel {
  final String id;
  final double batteryLevel;
  final double altitude;
  final double speed;
  final double lat;
  final double lng;
  final String status;

  DroneModel({
    required this.id,
    required this.batteryLevel,
    required this.altitude,
    required this.speed,
    required this.lat,
    required this.lng,
    required this.status,
  });

  factory DroneModel.fromJson(Map<String, dynamic> json) {
    return DroneModel(
      id: json['drone_id'] ?? json['id'] ?? '',
      batteryLevel: (json['battery_level'] as num?)?.toDouble() ?? 0,
      altitude: (json['altitude'] as num?)?.toDouble() ?? 0,
      speed: (json['speed'] as num?)?.toDouble() ?? 0,
      lat: (json['lat'] as num?)?.toDouble() ?? 0,
      lng: (json['lng'] as num?)?.toDouble() ?? 0,
      status: json['status'] ?? 'unknown',
    );
  }
}

class DroneMission {
  final String id;
  final String droneId;
  final String status;
  final double? estimatedMinutes;
  final String? txHash;

  DroneMission({
    required this.id,
    required this.droneId,
    required this.status,
    this.estimatedMinutes,
    this.txHash,
  });

  factory DroneMission.fromJson(Map<String, dynamic> json) {
    return DroneMission(
      id: json['mission_id'] ?? json['id'] ?? '',
      droneId: json['drone_id'] ?? '',
      status: json['status'] ?? 'pending',
      estimatedMinutes: (json['estimated_minutes'] as num?)?.toDouble(),
      txHash: json['tx_hash'],
    );
  }
}
