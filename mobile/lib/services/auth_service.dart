import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:http/http.dart' as http;

class AuthService extends ChangeNotifier {
  static const _storage = FlutterSecureStorage();

  String? _token;
  String? _role;
  String? _email;
  bool _isLoggedIn = false;

  bool get isLoggedIn => _isLoggedIn;
  String? get token => _token;
  String? get role => _role;
  String? get email => _email;

  // Demo accounts — local auth (no server needed)
  static const _demoAccounts = {
    'admin@nascon.test':    {'password': 'Nascon@26', 'role': 'super_admin'},
    'organizer@nascon.test':{'password': 'Nascon@26', 'role': 'league_organizer'},
    'manager@nascon.test':  {'password': 'Nascon@26', 'role': 'club_manager'},
    'player@nascon.test':   {'password': 'Nascon@26', 'role': 'player'},
    'viewer@nascon.test':   {'password': 'Nascon@26', 'role': 'viewer'},
  };

  AuthService() {
    _loadToken();
  }

  Future<void> _loadToken() async {
    try {
      _token = await _storage.read(key: 'auth_token');
      _role = await _storage.read(key: 'auth_role');
      _email = await _storage.read(key: 'auth_email');
      _isLoggedIn = _token != null;
      notifyListeners();
    } catch (_) {}
  }

  Future<bool> login(String email, String password, String baseUrl) async {
    final em = email.trim().toLowerCase();
    final account = _demoAccounts[em];

    // Step 1: Local credential check
    if (account == null || account['password'] != password) {
      return false;
    }

    final role = account['role']!;

    // Step 2: Save URL
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('base_url', baseUrl);

    // Step 3: Try to get real JWT from server (optional — fallback to local token)
    String token = _buildLocalToken(em, role);
    try {
      final uri = Uri.parse('$baseUrl/audit/v1/rbac-matrix');
      final resp = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: '{}',
      ).timeout(const Duration(seconds: 5));

      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        final tokens = data['tokens'] as Map<String, dynamic>?;
        if (tokens != null && tokens[role] != null) {
          token = tokens[role] as String;
          debugPrint('Got real JWT from server for role: $role');
        }
      }
    } catch (e) {
      debugPrint('Server unreachable, using local token: $e');
      // Continue with local token — offline mode
    }

    // Step 4: Store token
    await _storage.write(key: 'auth_token', value: token);
    await _storage.write(key: 'auth_role', value: role);
    await _storage.write(key: 'auth_email', value: em);

    _token = token;
    _role = role;
    _email = em;
    _isLoggedIn = true;
    notifyListeners();
    return true;
  }

  /// Build a simple local JWT-like token for offline use
  String _buildLocalToken(String email, String role) {
    // Base64url encode a simple payload (not cryptographically signed, demo only)
    final header = base64Url.encode(utf8.encode('{"alg":"none","typ":"JWT"}'));
    final payload = base64Url.encode(utf8.encode(jsonEncode({
      'sub': email,
      'role': role,
      'tenant_id': 'tenant-alpha',
      'exp': (DateTime.now().millisecondsSinceEpoch ~/ 1000) + 7200,
    })));
    return '$header.$payload.offline';
  }

  Future<void> logout() async {
    try {
      await _storage.deleteAll();
    } catch (_) {}
    _token = null;
    _role = null;
    _email = null;
    _isLoggedIn = false;
    notifyListeners();
  }

  bool get isSuperAdmin => _role == 'super_admin';
  bool get isOrganizer => _role == 'league_organizer' || _role == 'super_admin';
  bool get isManager => _role == 'club_manager' || _role == 'super_admin';
  bool get isPlayer => _role == 'player';
  bool get canScore => isOrganizer;
  bool get canManageRoster => isManager;
}
