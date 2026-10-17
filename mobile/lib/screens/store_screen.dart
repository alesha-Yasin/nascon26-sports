import 'package:flutter/material.dart';
import '../widgets/sync_indicator.dart';

class StoreScreen extends StatelessWidget {
  const StoreScreen({super.key});
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Merchandise Store'), actions: const [SyncIndicator()]),
      body: const Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
        Icon(Icons.store, size: 64, color: Colors.orange),
        SizedBox(height: 16),
        Text('Club Store', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
        SizedBox(height: 8),
        Text('Jerseys, scarves and more!', style: TextStyle(color: Colors.grey)),
      ])),
    );
  }
}
