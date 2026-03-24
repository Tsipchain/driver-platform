import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class DrivingSchoolScreen extends StatefulWidget {
  const DrivingSchoolScreen({super.key});

  @override
  State<DrivingSchoolScreen> createState() => _DrivingSchoolScreenState();
}

class _DrivingSchoolScreenState extends State<DrivingSchoolScreen> {
  Map<String, dynamic>? _dashboard;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadDashboard();
  }

  Future<void> _loadDashboard() async {
    setState(() => _isLoading = true);
    try {
      _dashboard = await ApiService.getSchoolDashboard();
    } catch (_) {}
    setState(() => _isLoading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Driving School')),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadDashboard,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  // Stats
                  Row(
                    children: [
                      _SchoolStat(label: 'Students', count: (_dashboard?['students'] as List?)?.length ?? 0, icon: Icons.people),
                      const SizedBox(width: 8),
                      _SchoolStat(label: 'Lessons', count: (_dashboard?['lessons'] as List?)?.length ?? 0, icon: Icons.calendar_today),
                      const SizedBox(width: 8),
                      _SchoolStat(label: 'Certs', count: (_dashboard?['certifications'] as List?)?.length ?? 0, icon: Icons.verified),
                    ],
                  ),
                  const SizedBox(height: 24),

                  // Actions
                  Text('Actions', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 12),
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.person_add, color: Colors.blue),
                      title: const Text('Enroll Student'),
                      subtitle: const Text('Register new student'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => _showEnrollDialog(),
                    ),
                  ),
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.schedule, color: Colors.orange),
                      title: const Text('Schedule Lesson'),
                      subtitle: const Text('Book a driving lesson'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () {},
                    ),
                  ),
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.card_membership, color: Colors.green),
                      title: const Text('Issue Certification'),
                      subtitle: const Text('Recorded on Thronos blockchain'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () {},
                    ),
                  ),
                ],
              ),
            ),
    );
  }

  void _showEnrollDialog() {
    final nameCtrl = TextEditingController();
    final phoneCtrl = TextEditingController();
    final emailCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Enroll Student'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Name')),
            TextField(controller: phoneCtrl, decoration: const InputDecoration(labelText: 'Phone')),
            TextField(controller: emailCtrl, decoration: const InputDecoration(labelText: 'Email')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              await ApiService.enrollStudent(nameCtrl.text, phoneCtrl.text, emailCtrl.text);
              if (ctx.mounted) Navigator.pop(ctx);
              _loadDashboard();
            },
            child: const Text('Enroll'),
          ),
        ],
      ),
    );
  }
}

class _SchoolStat extends StatelessWidget {
  final String label;
  final int count;
  final IconData icon;

  const _SchoolStat({required this.label, required this.count, required this.icon});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Icon(icon, size: 28, color: Theme.of(context).colorScheme.primary),
              const SizedBox(height: 8),
              Text('$count', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
              Text(label, style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
        ),
      ),
    );
  }
}
