import 'package:flutter/material.dart';
import '../widgets/sync_indicator.dart';

class RosterScreen extends StatelessWidget {
  const RosterScreen({super.key});
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Player Roster'), actions: const [SyncIndicator()]),
      body: const Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
        Icon(Icons.manage_accounts, size: 64, color: Colors.teal),
        SizedBox(height: 16),
        Text('Roster Management', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
        SizedBox(height: 8),
        Text('Manage player transfers and loans', style: TextStyle(color: Colors.grey)),
      ])),
    );
  }
}
