import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../../providers/auth_provider.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final user = auth.user;

    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const CircleAvatar(radius: 48, child: Icon(Icons.person, size: 48)),
          const SizedBox(height: 16),
          Text(user?.fullName ?? 'Driver', textAlign: TextAlign.center, style: Theme.of(context).textTheme.headlineSmall),
          Text(user?.phone ?? '', textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.grey)),
          const SizedBox(height: 24),
          Card(
            child: Column(
              children: [
                ListTile(title: const Text('Role'), trailing: Text(user?.role ?? 'driver')),
                ListTile(title: const Text('KYC Status'), trailing: Text(user?.kycStatus ?? 'Not verified')),
                ListTile(title: const Text('Rating'), trailing: Text(user?.ratingAvg?.toStringAsFixed(1) ?? '-')),
                if (user?.walletAddress != null)
                  ListTile(title: const Text('Wallet'), subtitle: Text(user!.walletAddress!, overflow: TextOverflow.ellipsis)),
              ],
            ),
          ),
          const SizedBox(height: 24),
          OutlinedButton.icon(
            onPressed: () async {
              await auth.logout();
              if (context.mounted) context.go('/login');
            },
            icon: const Icon(Icons.logout),
            label: const Text('Logout'),
          ),
        ],
      ),
    );
  }
}
