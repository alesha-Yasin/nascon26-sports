import 'package:flutter/material.dart';
import '../widgets/sync_indicator.dart';

class StandingsScreen extends StatelessWidget {
  const StandingsScreen({super.key});
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Standings'), actions: const [SyncIndicator()]),
      body: const Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
        Icon(Icons.leaderboard, size: 64, color: Color(0xFF1565C0)),
        SizedBox(height: 16),
        Text('Points Table', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
        SizedBox(height: 8),
        Text('Connect to server to view standings', style: TextStyle(color: Colors.grey)),
      ])),
    );
  }
}
