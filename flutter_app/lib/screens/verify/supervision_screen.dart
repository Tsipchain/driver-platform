import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class SupervisionScreen extends StatelessWidget {
  const SupervisionScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Drone Supervision')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            color: Theme.of(context).colorScheme.primaryContainer,
            child: const Padding(
              padding: EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Drone Delivery Supervision', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
                  SizedBox(height: 8),
                  Text('Autonomous drone deliveries require visual contact with a human supervisor '
                      'via the VerifyID call agent system using WebRTC.\n\n'
                      'The call agent monitors the delivery in real-time and can intervene if needed.'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: ListTile(
              leading: const Icon(Icons.video_call, color: Colors.green, size: 36),
              title: const Text('Start Supervision Call'),
              subtitle: const Text('Connect to VerifyID agent via WebRTC'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => context.push('/video-call'),
            ),
          ),
          const SizedBox(height: 8),
          Card(
            child: ListTile(
              leading: const Icon(Icons.flight_takeoff, color: Colors.blue, size: 36),
              title: const Text('Active Drone Missions'),
              subtitle: const Text('View and manage ongoing deliveries'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => context.push('/drone'),
            ),
          ),
          const SizedBox(height: 24),
          const Text('How It Works', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
          const SizedBox(height: 12),
          _StepTile(step: '1', title: 'Create Mission', desc: 'Set pickup/delivery and select drone'),
          _StepTile(step: '2', title: 'Agent Approval', desc: 'VerifyID call agent approves mission via WebRTC call'),
          _StepTile(step: '3', title: 'Live Monitoring', desc: 'Agent maintains visual contact during delivery'),
          _StepTile(step: '4', title: 'Blockchain Record', desc: 'Completion recorded on Thronos V3.6 blockchain'),
        ],
      ),
    );
  }
}

class _StepTile extends StatelessWidget {
  final String step;
  final String title;
  final String desc;

  const _StepTile({required this.step, required this.title, required this.desc});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(radius: 16, child: Text(step)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
                Text(desc, style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
