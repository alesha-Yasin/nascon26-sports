import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/sync_service.dart';

class SyncIndicator extends StatelessWidget {
  const SyncIndicator({super.key});

  @override
  Widget build(BuildContext context) {
    final sync = context.watch<SyncService>();
    final count = sync.pendingCount;

    IconData icon;
    Color color;
    String tooltip;

    switch (sync.status) {
      case SyncStatus.syncing:
        icon = Icons.sync;
        color = Colors.orange;
        tooltip = 'Syncing...';
        break;
      case SyncStatus.offline:
        icon = Icons.cloud_off;
        color = Colors.red;
        tooltip = 'Offline ($count pending)';
        break;
      case SyncStatus.online:
        icon = Icons.cloud_done;
        color = Colors.green;
        tooltip = 'Online';
        break;
      default:
        icon = Icons.cloud_queue;
        color = Colors.grey;
        tooltip = 'Idle';
    }

    return Tooltip(
      message: tooltip,
      child: Stack(
        children: [
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: sync.status == SyncStatus.syncing
                ? SizedBox(
                    width: 24, height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2, color: color),
                  )
                : Icon(icon, color: color),
          ),
          if (count > 0)
            Positioned(
              right: 4, top: 4,
              child: Container(
                width: 16, height: 16,
                decoration: const BoxDecoration(color: Colors.red, shape: BoxShape.circle),
                child: Center(
                  child: Text('$count', style: const TextStyle(color: Colors.white, fontSize: 10)),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
