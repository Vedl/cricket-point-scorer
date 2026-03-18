import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';

class AuthProvider extends ChangeNotifier {
  final ApiService _apiService;
  String? _username;
  bool _isLoading = true;
  String? _lastError;

  AuthProvider(this._apiService) {
    _checkLoginStatus();
  }

  String? get username => _username;
  bool get isAuthenticated => _username != null;
  bool get isLoading => _isLoading;
  String? get lastError => _lastError;

  Future<void> _checkLoginStatus() async {
    final prefs = await SharedPreferences.getInstance();
    _username = prefs.getString('auth_username');
    _isLoading = false;
    notifyListeners();
  }

  Future<void> login(String username, String password) async {
    _lastError = null;
    try {
      final result = await _apiService.login(username, password);
      if (result['success'] == true) {
        _username = result['username'];
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('auth_username', _username!);
        notifyListeners();
      }
    } catch (e) {
      _lastError = e.toString();
      notifyListeners();
      rethrow;
    }
  }

  Future<void> register(String username, String password) async {
    _lastError = null;
    try {
      final result = await _apiService.register(username, password);
      if (result['success'] == true) {
        _username = result['username'];
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('auth_username', _username!);
        notifyListeners();
      }
    } catch (e) {
      _lastError = e.toString();
      notifyListeners();
      rethrow;
    }
  }

  Future<void> logout() async {
    _username = null;
    _lastError = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('auth_username');
    notifyListeners();
  }
}
