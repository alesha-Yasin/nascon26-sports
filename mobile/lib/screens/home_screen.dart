import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import '../services/auth_service.dart';
import '../services/sync_service.dart';
import '../widgets/sync_indicator.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthService>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('Sports Platform'),
        actions: [
          const SyncIndicator(),
          IconButton(icon: const Icon(Icons.settings), onPressed: () => context.push('/settings')),
          IconButton(icon: const Icon(Icons.logout), onPressed: () async {
            await auth.logout();
            if (context.mounted) context.go('/login');
          }),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _RoleBadge(role: auth.role ?? 'viewer'),
            const SizedBox(height: 20),
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
              children: [
                _NavCard(icon: Icons.calendar_today, label: 'Fixtures', route: '/fixtures', color: Colors.blue),
                _NavCard(icon: Icons.leaderboard, label: 'Standings', route: '/standings', color: Colors.green),
                _NavCard(icon: Icons.store, label: 'Store', route: '/store', color: Colors.orange),
                _NavCard(icon: Icons.group, label: 'Club', route: '/club/club-alpha-1', color: Colors.purple),
                if (auth.canManageRoster)
                  _NavCard(icon: Icons.manage_accounts, label: 'Roster', route: '/roster', color: Colors.teal),
                _NavCard(icon: Icons.sync, label: 'Sync Queue', route: '/sync', color: Colors.red),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _RoleBadge extends StatelessWidget {
  final String role;
  const _RoleBadge({required this.role});
  @override
  Widget build(BuildContext context) {
    const roleLabels = {
      'super_admin': 'Platform Super-Admin',
      'league_organizer': 'League Organizer',
      'club_manager': 'Club Manager',
      'player': 'Player',
      'viewer': 'General Viewer',
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFF1565C0).withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1565C0).withOpacity(0.3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.verified_user, color: Color(0xFF1565C0)),
          const SizedBox(width: 8),
          Text('Role: ${roleLabels[role] ?? role}',
              style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF1565C0))),
        ],
      ),
    );
  }
}

class _NavCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String route;
  final Color color;
  const _NavCard({required this.icon, required this.label, required this.route, required this.color});

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 3,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => context.push(route),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 48, color: color),
            const SizedBox(height: 12),
            Text(label, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          ],
        ),
      ),
    );
  }
}
