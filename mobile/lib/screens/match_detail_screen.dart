import 'package:flutter/material.dart';
import '../widgets/sync_indicator.dart';

class UmatchUdetailScreen extends StatelessWidget {
  const UmatchUdetailScreen({super.key, required this.matchId
, required this.clubId});
  final String matchId;
final String clubId;
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Match Detail'), actions: const [SyncIndicator()]),
      body: const Center(child: Text('Loading...')),
    );
  }
}
