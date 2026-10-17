import 'package:flutter/material.dart';
import '../widgets/sync_indicator.dart';

class UclubUprofileScreen extends StatelessWidget {
  const UclubUprofileScreen({super.key, required this.clubId});
  final String clubId;
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Club Profile'), actions: const [SyncIndicator()]),
      body: const Center(child: Text('Loading...')),
    );
  }
}
