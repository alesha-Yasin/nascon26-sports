import 'package:flutter/material.dart';
import '../widgets/sync_indicator.dart';

class UstoreScreen extends StatelessWidget {
  const UstoreScreen({super.key});
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Store'), actions: const [SyncIndicator()]),
      body: const Center(child: Text('Loading...')),
    );
  }
}
