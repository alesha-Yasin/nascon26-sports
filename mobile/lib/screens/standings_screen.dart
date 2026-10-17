import 'package:flutter/material.dart';
import '../widgets/sync_indicator.dart';

class UstandingsScreen extends StatelessWidget {
  const UstandingsScreen({super.key});
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Standings'), actions: const [SyncIndicator()]),
      body: const Center(child: Text('Loading...')),
    );
  }
}
