import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../../providers/auth_provider.dart';
import '../../providers/driver_provider.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  @override
  void initState() {
    super.initState();
    context.read<DriverProvider>().loadDashboard();
  }

  @override
  Widget build(BuildContext context) {
    final driver = context.watch<DriverProvider>();
    final dashboard = driver.dashboardData;
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Thronos Driver'),
        actions: [
          IconButton(icon: const Icon(Icons.person), onPressed: () => context.push('/profile')),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => driver.loadDashboard(),
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Online toggle
            Card(
              child: SwitchListTile(
                title: Text(driver.isOnline ? 'Online' : 'Offline',
                    style: TextStyle(fontWeight: FontWeight.bold, color: driver.isOnline ? Colors.green : Colors.grey)),
                subtitle: Text('Mode: ${driver.currentMode}'),
                value: driver.isOnline,
                onChanged: (v) => driver.toggleOnline(v),
                secondary: Icon(driver.isOnline ? Icons.wifi : Icons.wifi_off, color: driver.isOnline ? Colors.green : Colors.grey),
              ),
            ),
            const SizedBox(height: 16),

            // Stats
            if (dashboard != null) ...[
              Row(
                children: [
                  _StatCard(label: 'Today', value: '\$${dashboard['today_earnings'] ?? 0}', icon: Icons.attach_money, color: Colors.green),
                  const SizedBox(width: 8),
                  _StatCard(label: 'Rating', value: '${dashboard['rating'] ?? '-'}', icon: Icons.star, color: Colors.amber),
                  const SizedBox(width: 8),
                  _StatCard(label: 'Trips', value: '${dashboard['total_trips'] ?? 0}', icon: Icons.route, color: cs.primary),
                ],
              ),
              const SizedBox(height: 24),
            ],

            // Services
            Text('Services', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              children: [
                _ServiceCard(icon: Icons.local_taxi, label: 'Taxi', color: Colors.amber, onTap: () => context.push('/taxi')),
                _ServiceCard(icon: Icons.school, label: 'Driving School', color: Colors.blue, onTap: () => context.push('/school')),
                _ServiceCard(icon: Icons.local_shipping, label: 'Transport', color: Colors.orange, onTap: () => context.push('/transport')),
                _ServiceCard(icon: Icons.flight, label: 'Drone Delivery', color: Colors.purple, onTap: () => context.push('/drone')),
              ],
            ),
            const SizedBox(height: 24),

            // Quick actions
            Text('Quick Actions', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            ListTile(
              leading: const Icon(Icons.history),
              title: const Text('Trip History'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => context.push('/trips'),
            ),
            ListTile(
              leading: const Icon(Icons.account_balance_wallet),
              title: const Text('Earnings'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => context.push('/earnings'),
            ),
            ListTile(
              leading: const Icon(Icons.video_call),
              title: const Text('VerifyID Call Agent'),
              subtitle: const Text('WebRTC supervision'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => context.push('/video-call'),
            ),
          ],
        ),
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color color;

  const _StatCard({required this.label, required this.value, required this.icon, required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            children: [
              Icon(icon, color: color, size: 28),
              const SizedBox(height: 8),
              Text(value, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
              Text(label, style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
        ),
      ),
    );
  }
}

class _ServiceCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  const _ServiceCard({required this.icon, required this.label, required this.color, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(color: color.withOpacity(0.15), shape: BoxShape.circle),
              child: Icon(icon, color: color, size: 36),
            ),
            const SizedBox(height: 12),
            Text(label, style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600)),
          ],
        ),
      ),
    );
  }
}
