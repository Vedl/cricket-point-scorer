import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import '../theme/app_theme.dart';
import '../services/api_service.dart';
import '../providers/auth_provider.dart';

class RoomEntryScreen extends StatefulWidget {
  final String tournamentId;
  const RoomEntryScreen({super.key, required this.tournamentId});

  @override
  State<RoomEntryScreen> createState() => _RoomEntryScreenState();
}

class _RoomEntryScreenState extends State<RoomEntryScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final _nameCtrl = TextEditingController();
  final _codeCtrl = TextEditingController();
  final _pinCtrl = TextEditingController();
  bool _adminPlaying = true;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _tabController.addListener(() {
      if (mounted) setState(() => _error = null);
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    _nameCtrl.dispose();
    _codeCtrl.dispose();
    _pinCtrl.dispose();
    super.dispose();
  }

  void _showSnack(String msg, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg),
      backgroundColor: isError ? AppTheme.red : AppTheme.green,
    ));
  }

  Future<void> _createRoom() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      setState(() => _error = 'Enter your name');
      return;
    }
    setState(() { _loading = true; _error = null; });
    try {
      final api = context.read<ApiService>();
      final auth = context.read<AuthProvider>();
      final result = await api.createRoom(
        adminName: name,
        tournamentType: widget.tournamentId,
        userId: auth.username,
        adminPlaying: _adminPlaying,
      );
      final code = result['room_code'];
      if (mounted) {
        _showSnack('Room $code created!');
        context.go('/auction/$code?name=$name&admin=true');
      }
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _joinRoom() async {
    final name = _nameCtrl.text.trim();
    final code = _codeCtrl.text.trim().toUpperCase();
    if (name.isEmpty || code.isEmpty) {
      setState(() => _error = 'Fill in all fields');
      return;
    }
    setState(() { _loading = true; _error = null; });
    try {
      final api = context.read<ApiService>();
      final auth = context.read<AuthProvider>();
      await api.joinRoom(
        roomCode: code,
        participantName: name,
        userId: auth.username,
      );
      if (mounted) {
        _showSnack('Joined room $code!');
        context.go('/auction/$code?name=$name&admin=false');
      }
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _claimWithPin() async {
    final code = _codeCtrl.text.trim().toUpperCase();
    final pin = _pinCtrl.text.trim().toUpperCase();
    if (code.isEmpty || pin.isEmpty) {
      setState(() => _error = 'Enter room code and PIN');
      return;
    }
    setState(() { _loading = true; _error = null; });
    try {
      final api = context.read<ApiService>();
      final auth = context.read<AuthProvider>();
      final result = await api.claimWithCode(
        roomCode: code,
        claimCode: pin,
        uid: auth.username!,
      );
      final pName = result['participant_name'] ?? '';
      if (mounted) {
        _showSnack('Claimed squad as $pName!');
        context.go('/auction/$code?name=$pName&admin=false');
      }
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bgDark,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: AppTheme.textPrimary),
          onPressed: () => context.go('/'),
        ),
        title: Text(
          _getTournamentName(),
          style: GoogleFonts.outfit(fontWeight: FontWeight.w700, fontSize: 17),
        ),
      ),
      body: Container(
        decoration: const BoxDecoration(gradient: AppTheme.bgGradient),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                // Tab switcher
                Container(
                  decoration: AppTheme.premiumCard(borderRadius: 20),
                  child: Column(
                    children: [
                      Container(
                        decoration: BoxDecoration(
                          color: AppTheme.surface.withValues(alpha: 0.5),
                          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
                        ),
                        child: TabBar(
                          controller: _tabController,
                          dividerHeight: 0,
                          isScrollable: false,
                          labelPadding: EdgeInsets.zero,
                          tabs: const [
                            Tab(text: 'Create'),
                            Tab(text: 'Join'),
                            Tab(text: 'Claim PIN'),
                          ],
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.all(24),
                        child: AnimatedSize(
                          duration: const Duration(milliseconds: 250),
                          child: _buildCurrentTab(),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildCurrentTab() {
    switch (_tabController.index) {
      case 0:
        return _buildCreateForm();
      case 1:
        return _buildJoinForm();
      case 2:
        return _buildClaimForm();
      default:
        return const SizedBox();
    }
  }

  Widget _buildCreateForm() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Create a new auction room',
          style: GoogleFonts.outfit(color: AppTheme.textSecondary, fontSize: 14),
        ),
        const SizedBox(height: 20),
        TextField(
          controller: _nameCtrl,
          style: GoogleFonts.outfit(color: AppTheme.textPrimary),
          decoration: const InputDecoration(
            labelText: 'Your name',
            prefixIcon: Icon(Icons.person_outline, color: AppTheme.textMuted, size: 20),
          ),
        ),
        const SizedBox(height: 16),
        // Admin playing toggle
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(AppTheme.radiusMd),
            border: Border.all(color: Colors.white.withValues(alpha: 0.06)),
          ),
          child: Row(
            children: [
              Icon(
                _adminPlaying ? Icons.sports_cricket : Icons.admin_panel_settings,
                color: AppTheme.textMuted,
                size: 20,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  _adminPlaying ? 'Playing as participant' : 'Admin only (not playing)',
                  style: GoogleFonts.outfit(color: AppTheme.textSecondary, fontSize: 14),
                ),
              ),
              Switch(
                value: _adminPlaying,
                onChanged: (v) => setState(() => _adminPlaying = v),
                activeThumbColor: AppTheme.gold,
              ),
            ],
          ),
        ),
        if (_error != null) _buildError(),
        const SizedBox(height: 24),
        _buildActionButton('Create Room', _createRoom),
      ],
    );
  }

  Widget _buildJoinForm() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Join an existing room',
          style: GoogleFonts.outfit(color: AppTheme.textSecondary, fontSize: 14),
        ),
        const SizedBox(height: 20),
        TextField(
          controller: _codeCtrl,
          style: GoogleFonts.outfit(color: AppTheme.textPrimary),
          textCapitalization: TextCapitalization.characters,
          inputFormatters: [
            FilteringTextInputFormatter.allow(RegExp(r'[A-Za-z0-9]')),
            LengthLimitingTextInputFormatter(6),
          ],
          decoration: const InputDecoration(
            labelText: 'Room code',
            prefixIcon: Icon(Icons.tag, color: AppTheme.textMuted, size: 20),
          ),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _nameCtrl,
          style: GoogleFonts.outfit(color: AppTheme.textPrimary),
          decoration: const InputDecoration(
            labelText: 'Your name',
            prefixIcon: Icon(Icons.person_outline, color: AppTheme.textMuted, size: 20),
          ),
        ),
        if (_error != null) _buildError(),
        const SizedBox(height: 24),
        _buildActionButton('Join Room', _joinRoom),
      ],
    );
  }

  Widget _buildClaimForm() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Claim your squad using your 4-character PIN',
          style: GoogleFonts.outfit(color: AppTheme.textSecondary, fontSize: 14),
        ),
        const SizedBox(height: 20),
        TextField(
          controller: _codeCtrl,
          style: GoogleFonts.outfit(color: AppTheme.textPrimary),
          textCapitalization: TextCapitalization.characters,
          inputFormatters: [
            FilteringTextInputFormatter.allow(RegExp(r'[A-Za-z0-9]')),
            LengthLimitingTextInputFormatter(6),
          ],
          decoration: const InputDecoration(
            labelText: 'Room code',
            prefixIcon: Icon(Icons.tag, color: AppTheme.textMuted, size: 20),
          ),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _pinCtrl,
          style: GoogleFonts.outfit(color: AppTheme.textPrimary, letterSpacing: 4),
          textCapitalization: TextCapitalization.characters,
          textAlign: TextAlign.center,
          inputFormatters: [
            FilteringTextInputFormatter.allow(RegExp(r'[A-Za-z0-9]')),
            LengthLimitingTextInputFormatter(4),
          ],
          decoration: const InputDecoration(
            labelText: 'PIN Code',
            prefixIcon: Icon(Icons.vpn_key_rounded, color: AppTheme.textMuted, size: 20),
          ),
        ),
        if (_error != null) _buildError(),
        const SizedBox(height: 24),
        _buildActionButton('Claim Squad', _claimWithPin),
      ],
    );
  }

  Widget _buildError() {
    return Container(
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppTheme.red.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.red.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: AppTheme.red, size: 16),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              _error!,
              style: GoogleFonts.outfit(color: AppTheme.redLight, fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionButton(String label, VoidCallback onPressed) {
    return SizedBox(
      height: 48,
      child: ElevatedButton(
        onPressed: _loading ? null : onPressed,
        style: ElevatedButton.styleFrom(
          backgroundColor: AppTheme.accent,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppTheme.radiusMd),
          ),
        ),
        child: _loading
            ? const SizedBox(
                width: 20, height: 20,
                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
              )
            : Text(label, style: GoogleFonts.outfit(fontWeight: FontWeight.w700, fontSize: 15)),
      ),
    );
  }

  String _getTournamentName() {
    switch (widget.tournamentId) {
      case 'ipl':
        return 'TATA IPL 2026';
      case 't20_wc':
        return 'T20 World Cup 2026';
      default:
        return widget.tournamentId.toUpperCase();
    }
  }
}
