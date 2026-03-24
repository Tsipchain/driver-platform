class UserModel {
  final String id;
  final String phone;
  final String? email;
  final String? fullName;
  final String role;
  final bool isVerified;
  final String? walletAddress;
  final int? organizationId;
  final String? kycStatus;
  final double? ratingAvg;
  final int ratingCount;

  UserModel({
    required this.id,
    required this.phone,
    this.email,
    this.fullName,
    this.role = 'driver',
    this.isVerified = false,
    this.walletAddress,
    this.organizationId,
    this.kycStatus,
    this.ratingAvg,
    this.ratingCount = 0,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id']?.toString() ?? '',
      phone: json['phone'] ?? '',
      email: json['email'],
      fullName: json['full_name'] ?? json['name'],
      role: json['role'] ?? 'driver',
      isVerified: json['is_verified'] == true || json['is_verified'] == 1,
      walletAddress: json['wallet_address'],
      organizationId: json['organization_id'],
      kycStatus: json['kyc_status'],
      ratingAvg: (json['rating_avg'] as num?)?.toDouble(),
      ratingCount: json['rating_count'] ?? 0,
    );
  }
}
