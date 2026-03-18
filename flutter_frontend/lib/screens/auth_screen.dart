import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shimmer/shimmer.dart';
import 'dart:ui';

import '../providers/auth_provider.dart';
import '../theme/app_theme.dart';

class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key});

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final _loginUsernameController = TextEditingController();
  final _loginPasswordController = TextEditingController();
  final _regUsernameController = TextEditingController();
  final _regPasswordController = TextEditingController();
  final _regPasswordConfirmController = TextEditingController();
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    _loginUsernameController.dispose();
    _loginPasswordController.dispose();
    _regUsernameController.dispose();
    _regPasswordController.dispose();
    _regPasswordConfirmController.dispose();
    super.dispose();
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: AppTheme.red),
    );
  }

  Future<void> _handleLogin() async {
    final username = _loginUsernameController.text.trim();
    final password = _loginPasswordController.text;
    if (username.isEmpty || password.isEmpty) {
      _showError('Please enter username and password');
      return;
    }

    setState(() => _isLoading = true);
    try {
      await context.read<AuthProvider>().login(username, password);
    } catch (e) {
      _showError(e.toString().replaceAll('ApiException(401): ', '').replaceAll('ApiException(404): ', ''));
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _handleRegister() async {
    final username = _regUsernameController.text.trim();
    final password = _regPasswordController.text;
    final confirm = _regPasswordConfirmController.text;

    if (username.isEmpty || password.isEmpty) {
      _showError('Please enter a username and password');
    } else if (password.length < 4) {
      _showError('Password must be at least 4 characters');
    } else if (password != confirm) {
      _showError('Passwords do not match');
    } else {
      setState(() => _isLoading = true);
      try {
        await context.read<AuthProvider>().register(username, password);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Account Created! Logging you in...'), backgroundColor: AppTheme.green),
          );
        }
      } catch (e) {
        _showError(e.toString().replaceAll('ApiException(400): ', ''));
      } finally {
        if (mounted) setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bgDark,
      body: Container(
        decoration: const BoxDecoration(gradient: AppTheme.bgGradient),
        child: Center(
          child: SingleChildScrollView(
            child: Padding(
              padding: const EdgeInsets.all(24.0),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(24),
                child: BackdropFilter(
                  filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
                  child: Container(
                    width: 400,
                    padding: const EdgeInsets.all(32),
                    decoration: BoxDecoration(
                      color: AppTheme.bgCard.withValues(alpha: 0.8),
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(color: Colors.white.withValues(alpha: 0.1)),
                    ),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        _buildHeader(),
                        const SizedBox(height: 32),
                        TabBar(
                          controller: _tabController,
                          indicatorColor: AppTheme.gold,
                          labelColor: AppTheme.gold,
                          unselectedLabelColor: Colors.grey,
                          tabs: const [
                            Tab(text: '🔐 Login'),
                            Tab(text: '📝 Register'),
                          ],
                        ),
                        const SizedBox(height: 24),
                        SizedBox(
                          height: 300,
                          child: TabBarView(
                            controller: _tabController,
                            children: [
                              _buildLoginTab(),
                              _buildRegisterTab(),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Column(
      children: [
        Shimmer.fromColors(
          baseColor: AppTheme.gold,
          highlightColor: Colors.white,
          child: Text(
            '🏏 Cricket Auction',
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: AppTheme.gold,
                ),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Build your dream team with real-time bidding strategies.',
          textAlign: TextAlign.center,
          style: TextStyle(color: Colors.grey[400]),
        ),
      ],
    );
  }

  Widget _buildLoginTab() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          controller: _loginUsernameController,
          style: const TextStyle(color: Colors.white),
          decoration: _inputDecoration('Username', Icons.person),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _loginPasswordController,
          obscureText: true,
          style: const TextStyle(color: Colors.white),
          decoration: _inputDecoration('Password', Icons.lock),
        ),
        const Spacer(),
        ElevatedButton(
          onPressed: _isLoading ? null : _handleLogin,
          style: Theme.of(context).elevatedButtonTheme.style?.copyWith(
            padding: const WidgetStatePropertyAll(EdgeInsets.symmetric(vertical: 16)),
          ),
          child: _isLoading ? const CircularProgressIndicator(color: Colors.black) : const Text('🚀 Log In'),
        ),
      ],
    );
  }

  Widget _buildRegisterTab() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          controller: _regUsernameController,
          style: const TextStyle(color: Colors.white),
          decoration: _inputDecoration('Choose Username', Icons.person_add),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _regPasswordController,
          obscureText: true,
          style: const TextStyle(color: Colors.white),
          decoration: _inputDecoration('Create Password', Icons.lock),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _regPasswordConfirmController,
          obscureText: true,
          style: const TextStyle(color: Colors.white),
          decoration: _inputDecoration('Confirm Password', Icons.lock_outline),
        ),
        const Spacer(),
        ElevatedButton(
          onPressed: _isLoading ? null : _handleRegister,
          style: Theme.of(context).elevatedButtonTheme.style?.copyWith(
            padding: const WidgetStatePropertyAll(EdgeInsets.symmetric(vertical: 16)),
          ),
          child: _isLoading ? const CircularProgressIndicator(color: Colors.black) : const Text('✨ Create Account'),
        ),
      ],
    );
  }

  InputDecoration _inputDecoration(String label, IconData icon) {
    return InputDecoration(
      labelText: label,
      labelStyle: const TextStyle(color: Colors.grey),
      prefixIcon: Icon(icon, color: Colors.grey),
      filled: true,
      fillColor: Colors.white.withValues(alpha: 0.05),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.1)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.1)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppTheme.gold),
      ),
    );
  }
}
