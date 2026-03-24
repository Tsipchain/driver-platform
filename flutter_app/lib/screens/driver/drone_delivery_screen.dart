import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../../providers/drone_provider.dart';

class DroneDeliveryScreen extends StatefulWidget {
  const DroneDeliveryScreen({super.key});

  @override
  State<DroneDeliveryScreen> createState() => _DroneDeliveryScreenState();
}

class _DroneDeliveryScreenState extends State<DroneDeliveryScreen> {
  @override
  void initState() {
    super.initState();
    context.read<DroneProvider>().loadDashboard();
  }

  @override
  Widget build(BuildContext context) {
    final drone = context.watch<DroneProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Drone Delivery'),
        actions: [
          IconButton(
            icon: const Icon(Icons.video_call),
            tooltip: 'Supervisor Call',
            onPressed: () => context.push('/supervision'),
          ),
        ],
      ),
      body: drone.isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: () => drone.loadDashboard(),
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  // Info banner
                  Card(
                    color: Theme.of(context).colorScheme.primaryContainer,
                    child: const Padding(
                      padding: EdgeInsets.all(16),
                      child: Row(
                        children: [
                          Icon(Icons.info_outline, size: 20),
                          SizedBox(width: 8),
                          Expanded(child: Text('Drone deliveries require VerifyID call agent supervision via WebRTC')),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Fleet
                  Text('Drone Fleet', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  if (drone.drones.isEmpty)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(24),
                        child: Column(
                          children: [
                            Icon(Icons.flight, size: 48, color: Colors.grey.shade400),
                            const SizedBox(height: 8),
                            const Text('No drones registered'),
                          ],
                        ),
                      ),
                    )
                  else
                    ...drone.drones.map((d) => Card(
                          child: ListTile(
                            leading: Icon(Icons.flight, color: d.status == 'idle' ? Colors.green : Colors.orange),
                            title: Text('Drone ${d.id}'),
                            subtitle: Text('Battery: ${d.batteryLevel}% | Alt: ${d.altitude}m | Status: ${d.status}'),
                            trailing: IconButton(
                              icon: const Icon(Icons.gps_fixed),
                              onPressed: () => drone.loadTelemetry(d.id),
                            ),
                          ),
                        )),

                  const SizedBox(height: 24),

                  // Active missions
                  Text('Active Missions', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  if (drone.activeMissions.isEmpty)
                    const Card(child: Padding(padding: EdgeInsets.all(24), child: Text('No active missions')))
                  else
                    ...drone.activeMissions.map((m) => Card(
                          child: ListTile(
                            leading: Icon(Icons.delivery_dining,
                                color: m.status == 'delivered' ? Colors.green : Colors.blue),
                            title: Text('Mission ${m.id}'),
                            subtitle: Text('Drone: ${m.droneId} | Status: ${m.status}'),
                            trailing: m.txHash != null
                                ? const Icon(Icons.verified, color: Colors.green)
                                : const Icon(Icons.pending, color: Colors.orange),
                          ),
                        )),
                ],
              ),
            ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showCreateMissionDialog(),
        icon: const Icon(Icons.add),
        label: const Text('New Mission'),
      ),
    );
  }

  void _showCreateMissionDialog() {
    final droneIdCtrl = TextEditingController();
    final pickupCtrl = TextEditingController();
    final deliveryCtrl = TextEditingController();
    final descCtrl = TextEditingController();
    final weightCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Create Drone Mission'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(controller: droneIdCtrl, decoration: const InputDecoration(labelText: 'Drone ID')),
              TextField(controller: pickupCtrl, decoration: const InputDecoration(labelText: 'Pickup Address')),
              TextField(controller: deliveryCtrl, decoration: const InputDecoration(labelText: 'Delivery Address')),
              TextField(controller: weightCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Package Weight (kg)')),
              TextField(controller: descCtrl, decoration: const InputDecoration(labelText: 'Description')),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              await context.read<DroneProvider>().createMission(
                    droneId: droneIdCtrl.text,
                    pickupAddress: pickupCtrl.text,
                    deliveryAddress: deliveryCtrl.text,
                    packageWeight: double.tryParse(weightCtrl.text) ?? 0,
                    description: descCtrl.text,
                  );
              if (ctx.mounted) Navigator.pop(ctx);
            },
            child: const Text('Create'),
          ),
        ],
      ),
    );
  }
}
