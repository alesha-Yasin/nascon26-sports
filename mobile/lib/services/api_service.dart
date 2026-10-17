import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService extends ChangeNotifier {
  String _baseUrl = 'http://10.0.2.2:8080';
  String? _authToken;
  bool _isOnline = true;

  String get baseUrl => _baseUrl;
  bool get isOnline => _isOnline;

  ApiService() {
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    _baseUrl = prefs.getString('base_url') ?? 'http://10.0.2.2:8080';
    notifyListeners();
  }

  void setBaseUrl(String url) {
    _baseUrl = url;
    notifyListeners();
  }

  void setToken(String? token) {
    _authToken = token;
  }

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    if (_authToken != null) 'Authorization': 'Bearer $_authToken',
  };

  Future<Map<String, dynamic>> get(String path) async {
    final uri = Uri.parse('$_baseUrl$path');
    final resp = await http.get(uri, headers: _headers).timeout(
      const Duration(seconds: 10),
    );
    _isOnline = true;
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> post(String path, Map<String, dynamic> body) async {
    final uri = Uri.parse('$_baseUrl$path');
    final resp = await http.post(
      uri,
      headers: _headers,
      body: jsonEncode(body),
    ).timeout(const Duration(seconds: 10));
    _isOnline = true;
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  Future<dynamic> getList(String path) async {
    final uri = Uri.parse('$_baseUrl$path');
    final resp = await http.get(uri, headers: _headers).timeout(
      const Duration(seconds: 10),
    );
    _isOnline = true;
    return jsonDecode(resp.body);
  }
}
