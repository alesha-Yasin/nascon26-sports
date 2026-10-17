import 'package:flutter/material.dart';
import '../widgets/sync_indicator.dart';

class UrosterScreen extends StatelessWidget {
  const UrosterScreen({super.key});
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Roster'), actions: const [SyncIndicator()]),
      body: const Center(child: Text('Loading...')),
    );
  }
}
