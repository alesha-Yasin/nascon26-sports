import 'package:flutter/material.dart';
import '../widgets/sync_indicator.dart';

class UsettingsScreen extends StatelessWidget {
  const UsettingsScreen({super.key});
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Settings'), actions: const [SyncIndicator()]),
      body: const Center(child: Text('Loading...')),
    );
  }
}
