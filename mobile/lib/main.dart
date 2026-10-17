import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';

import 'services/api_service.dart';
import 'services/auth_service.dart';
import 'services/local_db.dart';
import 'services/sync_service.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';
import 'screens/fixtures_screen.dart';
import 'screens/match_detail_screen.dart';
import 'screens/standings_screen.dart';
import 'screens/club_profile_screen.dart';
import 'screens/store_screen.dart';
import 'screens/roster_screen.dart';
import 'screens/sync_screen.dart';
import 'screens/settings_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await LocalDB.instance.init();
  runApp(const SportsApp());
}

class SportsApp extends StatelessWidget {
  const SportsApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthService()),
        ChangeNotifierProvider(create: (_) => ApiService()),
        ChangeNotifierProvider(create: (_) => SyncService()),
      ],
      child: Consumer<AuthService>(
        builder: (context, auth, _) {
          final router = GoRouter(
            initialLocation: '/login',
            routes: [
              GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
              GoRoute(path: '/home', builder: (_, __) => const HomeScreen()),
              GoRoute(path: '/fixtures', builder: (_, __) => const FixturesScreen()),
              GoRoute(
                path: '/match/:id',
                builder: (_, state) => MatchDetailScreen(matchId: state.pathParameters['id'] ?? ''),
              ),
              GoRoute(path: '/standings', builder: (_, __) => const StandingsScreen()),
              GoRoute(
                path: '/club/:id',
                builder: (_, state) => ClubProfileScreen(clubId: state.pathParameters['id'] ?? ''),
              ),
              GoRoute(path: '/store', builder: (_, __) => const StoreScreen()),
              GoRoute(path: '/roster', builder: (_, __) => const RosterScreen()),
              GoRoute(path: '/sync', builder: (_, __) => const SyncScreen()),
              GoRoute(path: '/settings', builder: (_, __) => const SettingsScreen()),
            ],
          );

          return MaterialApp.router(
            title: 'Sports Platform',
            theme: ThemeData(
              colorScheme: ColorScheme.fromSeed(
                seedColor: const Color(0xFF1565C0),
                brightness: Brightness.light,
              ),
              useMaterial3: true,
              appBarTheme: const AppBarTheme(
                backgroundColor: Color(0xFF1565C0),
                foregroundColor: Colors.white,
                elevation: 2,
              ),
            ),
            routerConfig: router,
          );
        },
      ),
    );
  }
}
