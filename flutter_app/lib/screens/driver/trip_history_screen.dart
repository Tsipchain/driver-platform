import 'package:flutter/material.dart';
import '../../models/trip_model.dart';
import '../../services/api_service.dart';

class TripHistoryScreen extends StatefulWidget {
  const TripHistoryScreen({super.key});

  @override
  State<TripHistoryScreen> createState() => _TripHistoryScreenState();
}

class _TripHistoryScreenState extends State<TripHistoryScreen> {
  List<TripModel> _trips = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    setState(() => _isLoading = true);
    try {
      final res = await ApiService.getTripHistory();
      _trips = (res['trips'] as List?)?.map((t) => TripModel.fromJson(t)).toList() ?? [];
    } catch (_) {}
    setState(() => _isLoading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Trip History')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _trips.isEmpty
              ? const Center(child: Text('No trips yet'))
              : RefreshIndicator(
                  onRefresh: _loadHistory,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _trips.length,
                    itemBuilder: (context, index) {
                      final trip = _trips[index];
                      return Card(
                        child: ListTile(
                          leading: Icon(
                            trip.type == 'taxi' ? Icons.local_taxi : Icons.local_shipping,
                            color: trip.status == 'completed' ? Colors.green : Colors.orange,
                          ),
                          title: Text(trip.pickup?.address ?? 'Trip #${trip.id}'),
                          subtitle: Text('${trip.type} | ${trip.status}\nFare: \$${trip.fare ?? 0}'),
                          isThreeLine: true,
                          trailing: trip.txHash != null ? const Icon(Icons.verified, color: Colors.green, size: 20) : null,
                        ),
                      );
                    },
                  ),
                ),
    );
  }
}
