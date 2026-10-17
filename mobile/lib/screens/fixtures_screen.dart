import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import '../services/api_service.dart';
import '../services/local_db.dart';
import '../widgets/sync_indicator.dart';

class FixturesScreen extends StatefulWidget {
  const FixturesScreen({super.key});
  @override State<FixturesScreen> createState() => _FixturesScreenState();
}

class _FixturesScreenState extends State<FixturesScreen> {
  List<dynamic> _fixtures = [];
  bool _loading = true;
  bool _fromCache = false;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    final api = context.read<ApiService>();
    try {
      final data = await api.getList('/audit/v1/score/all') ?? [];
      await LocalDB.instance.cacheFixtures(List<Map<String,dynamic>>.from(data));
      setState(() { _fixtures = data; _loading = false; _fromCache = false; });
    } catch (_) {
      final cached = await LocalDB.instance.getCachedFixtures();
      setState(() { _fixtures = cached; _loading = false; _fromCache = true; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Fixtures'),
        actions: [const SyncIndicator(), IconButton(icon: const Icon(Icons.refresh), onPressed: _load)],
      ),
      body: _loading
        ? const Center(child: CircularProgressIndicator())
        : Column(children: [
            if (_fromCache) Container(color: Colors.orange.shade100, padding: const EdgeInsets.all(8),
              child: const Row(children: [Icon(Icons.cloud_off, size: 16), SizedBox(width: 8), Text('Offline — showing cached data')])),
            if (_fixtures.isEmpty) const Expanded(child: Center(child: Text('No matches yet. Check back later.')))
            else Expanded(child: ListView.builder(
              itemCount: _fixtures.length,
              itemBuilder: (_, i) {
                final fx = _fixtures[i] as Map<String,dynamic>;
                return ListTile(
                  leading: const Icon(Icons.sports_soccer),
                  title: Text('${fx["home_team_id"] ?? fx["home"] ?? "?"} vs ${fx["away_team_id"] ?? fx["away"] ?? "?"}'),
                  subtitle: Text('Status: ${fx["status"] ?? "upcoming"}'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.push('/match/${fx["match_id"]}'),
                );
              },
            )),
          ]),
    );
  }
}
