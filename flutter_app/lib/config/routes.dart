import 'package:go_router/go_router.dart';
import '../screens/shared/splash_screen.dart';
import '../screens/shared/login_screen.dart';
import '../screens/shared/home_screen.dart';
import '../screens/shared/profile_screen.dart';
import '../screens/driver/taxi_screen.dart';
import '../screens/driver/driving_school_screen.dart';
import '../screens/driver/transport_screen.dart';
import '../screens/driver/drone_delivery_screen.dart';
import '../screens/driver/trip_history_screen.dart';
import '../screens/driver/earnings_screen.dart';
import '../screens/verify/video_call_screen.dart';
import '../screens/verify/supervision_screen.dart';

class AppRouter {
  static final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(path: '/', builder: (_, __) => const SplashScreen()),
      GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
      GoRoute(path: '/home', builder: (_, __) => const HomeScreen()),
      GoRoute(path: '/profile', builder: (_, __) => const ProfileScreen()),
      // Driver services
      GoRoute(path: '/taxi', builder: (_, __) => const TaxiScreen()),
      GoRoute(path: '/school', builder: (_, __) => const DrivingSchoolScreen()),
      GoRoute(path: '/transport', builder: (_, __) => const TransportScreen()),
      GoRoute(path: '/drone', builder: (_, __) => const DroneDeliveryScreen()),
      GoRoute(path: '/trips', builder: (_, __) => const TripHistoryScreen()),
      GoRoute(path: '/earnings', builder: (_, __) => const EarningsScreen()),
      // Verify ID
      GoRoute(path: '/video-call', builder: (_, __) => const VideoCallScreen()),
      GoRoute(path: '/supervision', builder: (_, __) => const SupervisionScreen()),
    ],
  );
}
