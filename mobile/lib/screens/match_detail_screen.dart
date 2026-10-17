import 'package:flutter/material.dart';
import '../widgets/sync_indicator.dart';

class MatchDetailScreen extends StatelessWidget {
  final String matchId;
  const MatchDetailScreen({super.key, required this.matchId});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Match: $matchId'),
        actions: const [SyncIndicator()],
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.sports, size: 64, color: Color(0xFF1565C0)),
            const SizedBox(height: 16),
            Text('Match ID: $matchId', style: const TextStyle(fontSize: 18)),
            const SizedBox(height: 8),
            const Text('Score details loading...', style: TextStyle(color: Colors.grey)),
          ],
        ),
      ),
    );
  }
}
