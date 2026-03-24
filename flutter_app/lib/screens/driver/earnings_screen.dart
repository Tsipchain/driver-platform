import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/driver_provider.dart';

class EarningsScreen extends StatelessWidget {
  const EarningsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final driver = context.watch<DriverProvider>();
    final dashboard = driver.dashboardData;

    return Scaffold(
      appBar: AppBar(title: const Text('Earnings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                children: [
                  Text('Today', style: Theme.of(context).textTheme.bodyLarge),
                  const SizedBox(height: 8),
                  Text('\$${dashboard?['today_earnings'] ?? 0}',
                      style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.bold, color: Colors.green)),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                children: [
                  Text('This Week', style: Theme.of(context).textTheme.bodyLarge),
                  const SizedBox(height: 8),
                  Text('\$${dashboard?['weekly_earnings'] ?? 0}',
                      style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold)),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          Card(
            child: Column(
              children: [
                ListTile(title: const Text('Total Trips'), trailing: Text('${dashboard?['total_trips'] ?? 0}')),
                ListTile(title: const Text('Rating'), trailing: Text('${dashboard?['rating'] ?? '-'}')),
                const ListTile(title: Text('Blockchain'), trailing: Text('Thronos V3.6')),
                const ListTile(title: Text('Token'), trailing: Text('THR')),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
