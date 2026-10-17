import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'api_service.dart';

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
    try {
      // For demo: use the RBAC matrix to get tokens
      // In production would call POST /auth/login
      final api = ApiService();
      api.setBaseUrl(baseUrl);
      
      // Demo account mapping
      const demoRoles = {
        'admin@nascon.test': 'super_admin',
        'organizer@nascon.test': 'league_organizer',
        'manager@nascon.test': 'club_manager',
        'player@nascon.test': 'player',
        'viewer@nascon.test': 'viewer',
      };

      if (password != 'Nascon@26' || !demoRoles.containsKey(email)) {
        return false;
      }

      final role = demoRoles[email]!;
      // Get JWT from rbac-matrix
      final resp = await api.post('/audit/v1/rbac-matrix', {});
      if (resp['tokens'] != null) {
        final tokenForRole = resp['tokens'][role];
        await _storage.write(key: 'auth_token', value: tokenForRole);
        await _storage.write(key: 'auth_role', value: role);
        await _storage.write(key: 'auth_email', value: email);
        
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('base_url', baseUrl);
        
        _token = tokenForRole;
        _role = role;
        _email = email;
        _isLoggedIn = true;
        notifyListeners();
        return true;
      }
      return false;
    } catch (e) {
      debugPrint('Login error: $e');
      return false;
    }
  }

  Future<void> logout() async {
    await _storage.deleteAll();
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
