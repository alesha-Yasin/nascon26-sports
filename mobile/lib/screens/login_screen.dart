import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';
import '../widgets/sync_indicator.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _emailCtrl = TextEditingController(text: 'admin@nascon.test');
  final _passCtrl = TextEditingController(text: 'Nascon@26');
  final _urlCtrl = TextEditingController(text: 'http://127.0.0.1:8080');
  bool _loading = false;
  String? _error;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                const Icon(Icons.sports, size: 80, color: Color(0xFF1565C0)),
                const SizedBox(height: 16),
                const Text('Sports Platform',
                    style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold)),
                const Text('NaSCon \'26', style: TextStyle(color: Colors.grey)),
                const SizedBox(height: 40),
                TextField(
                  controller: _emailCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Email',
                    prefixIcon: Icon(Icons.email),
                    border: OutlineInputBorder(),
                  ),
                  keyboardType: TextInputType.emailAddress,
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _passCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Password',
                    prefixIcon: Icon(Icons.lock),
                    border: OutlineInputBorder(),
                  ),
                  obscureText: true,
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _urlCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Server URL',
                    prefixIcon: Icon(Icons.dns),
                    border: OutlineInputBorder(),
                    helperText: 'Emulator: 10.0.2.2:8080 | Phone: LAN IP',
                  ),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.red.shade50,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.red),
                    ),
                    child: Row(children: [
                      const Icon(Icons.error, color: Colors.red),
                      const SizedBox(width: 8),
                      Expanded(child: Text(_error!, style: const TextStyle(color: Colors.red))),
                    ]),
                  ),
                ],
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: ElevatedButton(
                    onPressed: _loading ? null : _login,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF1565C0),
                      foregroundColor: Colors.white,
                    ),
                    child: _loading
                        ? const CircularProgressIndicator(color: Colors.white)
                        : const Text('Sign In', style: TextStyle(fontSize: 18)),
                  ),
                ),
                const SizedBox(height: 24),
                const _DemoAccountsCard(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _login() async {
    setState(() { _loading = true; _error = null; });
    final auth = context.read<AuthService>();
    final api = context.read<ApiService>();
    api.setBaseUrl(_urlCtrl.text.trim());
    final ok = await auth.login(_emailCtrl.text.trim(), _passCtrl.text.trim(), _urlCtrl.text.trim());
    setState(() => _loading = false);
    if (ok && mounted) {
      context.go('/home');
    } else {
      setState(() => _error = 'Invalid credentials. Use demo accounts below.');
    }
  }
}

class _DemoAccountsCard extends StatelessWidget {
  const _DemoAccountsCard();
  @override
  Widget build(BuildContext context) {
    const accounts = [
      ('admin@nascon.test', 'Super Admin'),
      ('organizer@nascon.test', 'League Organizer'),
      ('manager@nascon.test', 'Club Manager'),
      ('player@nascon.test', 'Player'),
      ('viewer@nascon.test', 'Viewer'),
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Demo Accounts (password: Nascon@26)',
                style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            ...accounts.map((a) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 2),
              child: Row(children: [
                Expanded(child: Text(a.$1, style: const TextStyle(fontSize: 12))),
                Text(a.$2, style: const TextStyle(fontSize: 12, color: Colors.grey)),
              ]),
            )),
          ],
        ),
      ),
    );
  }
}
