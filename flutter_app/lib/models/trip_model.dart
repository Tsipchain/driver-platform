class TripModel {
  final String id;
  final String type;
  final String status;
  final String? driverId;
  final TripLocation? pickup;
  final TripLocation? dropoff;
  final double? fare;
  final double? distance;
  final int? duration;
  final String? txHash;
  final DateTime? createdAt;
  final DateTime? completedAt;

  TripModel({
    required this.id,
    required this.type,
    required this.status,
    this.driverId,
    this.pickup,
    this.dropoff,
    this.fare,
    this.distance,
    this.duration,
    this.txHash,
    this.createdAt,
    this.completedAt,
  });

  factory TripModel.fromJson(Map<String, dynamic> json) {
    return TripModel(
      id: json['id']?.toString() ?? '',
      type: json['type'] ?? 'taxi',
      status: json['status'] ?? 'unknown',
      driverId: json['driver_id']?.toString(),
      pickup: json['pickup'] != null ? TripLocation.fromJson(json['pickup']) : null,
      dropoff: json['dropoff'] != null ? TripLocation.fromJson(json['dropoff']) : null,
      fare: (json['fare'] as num?)?.toDouble(),
      distance: (json['distance'] as num?)?.toDouble(),
      duration: json['duration'],
      txHash: json['tx_hash'],
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at']) : null,
      completedAt: json['completed_at'] != null ? DateTime.tryParse(json['completed_at']) : null,
    );
  }
}

class TripLocation {
  final double lat;
  final double lng;
  final String? address;

  TripLocation({required this.lat, required this.lng, this.address});

  factory TripLocation.fromJson(Map<String, dynamic> json) {
    return TripLocation(
      lat: (json['lat'] as num).toDouble(),
      lng: (json['lng'] as num).toDouble(),
      address: json['address'],
    );
  }
}
