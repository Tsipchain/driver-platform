import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class TransportScreen extends StatefulWidget {
  const TransportScreen({super.key});

  @override
  State<TransportScreen> createState() => _TransportScreenState();
}

class _TransportScreenState extends State<TransportScreen> {
  List<dynamic> _jobs = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadJobs();
  }

  Future<void> _loadJobs() async {
    setState(() => _isLoading = true);
    try {
      final res = await ApiService.getTransportJobs();
      _jobs = res['jobs'] ?? [];
    } catch (_) {}
    setState(() => _isLoading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Transport & Delivery')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _jobs.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.local_shipping, size: 64, color: Colors.grey.shade400),
                      const SizedBox(height: 16),
                      const Text('No transport jobs available'),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _loadJobs,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _jobs.length,
                    itemBuilder: (context, index) {
                      final job = _jobs[index];
                      return Card(
                        child: ListTile(
                          leading: const Icon(Icons.local_shipping),
                          title: Text(job['pickup_address'] ?? 'Pickup'),
                          subtitle: Text('To: ${job['delivery_address'] ?? "Delivery"}\nType: ${job['type'] ?? "delivery"}'),
                          isThreeLine: true,
                          trailing: ElevatedButton(
                            onPressed: () {},
                            child: const Text('Accept'),
                          ),
                        ),
                      );
                    },
                  ),
                ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showCreateJobDialog(),
        icon: const Icon(Icons.add),
        label: const Text('New Job'),
      ),
    );
  }

  void _showCreateJobDialog() {
    final pickupCtrl = TextEditingController();
    final deliveryCtrl = TextEditingController();
    final descCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Create Transport Job'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: pickupCtrl, decoration: const InputDecoration(labelText: 'Pickup Address')),
            TextField(controller: deliveryCtrl, decoration: const InputDecoration(labelText: 'Delivery Address')),
            TextField(controller: descCtrl, decoration: const InputDecoration(labelText: 'Description')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              await ApiService.createTransportJob({
                'pickup_address': pickupCtrl.text,
                'delivery_address': deliveryCtrl.text,
                'description': descCtrl.text,
                'weight': 0.0,
                'type': 'delivery',
              });
              if (ctx.mounted) Navigator.pop(ctx);
              _loadJobs();
            },
            child: const Text('Create'),
          ),
        ],
      ),
    );
  }
}
