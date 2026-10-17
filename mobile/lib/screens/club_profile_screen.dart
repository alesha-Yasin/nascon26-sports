import 'package:flutter/material.dart';
import '../widgets/sync_indicator.dart';

class ClubProfileScreen extends StatelessWidget {
  final String clubId;
  const ClubProfileScreen({super.key, required this.clubId});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Club: $clubId'),
        actions: const [SyncIndicator()],
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.shield, size: 64, color: Color(0xFF1565C0)),
            const SizedBox(height: 16),
            Text('Club ID: $clubId', style: const TextStyle(fontSize: 18)),
            const SizedBox(height: 8),
            const Text('Club profile loading...', style: TextStyle(color: Colors.grey)),
          ],
        ),
      ),
    );
  }
}
