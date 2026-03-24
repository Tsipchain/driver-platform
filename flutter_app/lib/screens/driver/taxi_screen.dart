import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/driver_provider.dart';

class TaxiScreen extends StatefulWidget {
  const TaxiScreen({super.key});

  @override
  State<TaxiScreen> createState() => _TaxiScreenState();
}

class _TaxiScreenState extends State<TaxiScreen> {
  @override
  void initState() {
    super.initState();
    final driver = context.read<DriverProvider>();
    driver.setMode('taxi');
    driver.loadAvailableTrips();
  }

  @override
  Widget build(BuildContext context) {
    final driver = context.watch<DriverProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Taxi Service'),
        actions: [
          Switch(
            value: driver.isOnline,
            onChanged: (v) => driver.toggleOnline(v),
            activeColor: Colors.green,
          ),
        ],
      ),
      body: Column(
        children: [
          // Active trip banner
          if (driver.activeTrip != null)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              color: Theme.of(context).colorScheme.primaryContainer,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Active Trip', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Text('${driver.activeTrip!.pickup?.address ?? "Pickup"} -> ${driver.activeTrip!.dropoff?.address ?? "Dropoff"}'),
                  Text('Status: ${driver.activeTrip!.status}'),
                  const SizedBox(height: 8),
                  if (driver.activeTrip!.status == 'accepted')
                    ElevatedButton(
                      onPressed: () => driver.completeTrip(driver.activeTrip!.id),
                      child: const Text('Complete Trip'),
                    ),
                ],
              ),
            ),

          // Available trips
          Expanded(
            child: driver.availableTrips.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.local_taxi, size: 64, color: Colors.grey.shade400),
                        const SizedBox(height: 16),
                        Text(driver.isOnline ? 'Waiting for trips...' : 'Go online to receive trips',
                            style: TextStyle(color: Colors.grey.shade600)),
                      ],
                    ),
                  )
                : ListView.builder(
                    itemCount: driver.availableTrips.length,
                    padding: const EdgeInsets.all(16),
                    itemBuilder: (context, index) {
                      final trip = driver.availableTrips[index];
                      return Card(
                        child: ListTile(
                          leading: const Icon(Icons.directions_car),
                          title: Text(trip.pickup?.address ?? 'Unknown pickup'),
                          subtitle: Text('To: ${trip.dropoff?.address ?? "Unknown"}\nFare: \$${trip.fare ?? 0}'),
                          isThreeLine: true,
                          trailing: ElevatedButton(
                            onPressed: () => driver.acceptTrip(trip.id),
                            child: const Text('Accept'),
                          ),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => driver.loadAvailableTrips(),
        child: const Icon(Icons.refresh),
      ),
    );
  }
}
