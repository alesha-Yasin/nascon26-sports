import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/sync_service.dart';
import '../services/api_service.dart';
import '../widgets/sync_indicator.dart';

class SyncScreen extends StatelessWidget {
  const SyncScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final sync = context.watch<SyncService>();
    return Scaffold(
      appBar: AppBar(title: const Text('Sync Queue'), actions: const [SyncIndicator()]),
      body: Column(children: [
        Container(
          padding: const EdgeInsets.all(16),
          child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            Text('Pending: ${sync.pendingCount}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            ElevatedButton.icon(
              icon: const Icon(Icons.sync),
              label: const Text('Sync Now'),
              onPressed: sync.status == SyncStatus.syncing ? null : () {
                final api = context.read<ApiService>();
                sync.sync(api, 'device-001');
              },
            ),
          ]),
        ),
        const Divider(),
        Expanded(
          child: sync.pendingActions.isEmpty
            ? const Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                Icon(Icons.check_circle, size: 64, color: Colors.green),
                SizedBox(height: 16),
                Text('All actions synced!', style: TextStyle(fontSize: 18, color: Colors.green)),
              ]))
            : ListView.builder(
                itemCount: sync.pendingActions.length,
                itemBuilder: (_, i) {
                  final a = sync.pendingActions[i];
                  return ListTile(
                    leading: const Icon(Icons.pending_actions, color: Colors.orange),
                    title: Text('${a["type"]}'),
                    subtitle: Text('Queued: ${a["queued_at"]}'),
                    trailing: const Icon(Icons.schedule),
                  );
                },
              ),
        ),
      ]),
    );
  }
}
