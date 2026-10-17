import 'package:flutter/material.dart';
import '../widgets/sync_indicator.dart';

class UsyncScreen extends StatelessWidget {
  const UsyncScreen({super.key});
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Sync'), actions: const [SyncIndicator()]),
      body: const Center(child: Text('Loading...')),
    );
  }
}
