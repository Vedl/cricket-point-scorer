import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import '../theme/app_theme.dart';
import '../services/api_service.dart';
import '../providers/auth_provider.dart';

class LandingScreen extends StatefulWidget {
  const LandingScreen({super.key});

  @override
  State<LandingScreen> createState() => _LandingScreenState();
}

class _LandingScreenState extends State<LandingScreen> {
  List<Map<String, dynamic>> _tournaments = [];
  List<Map<String, dynamic>> _userRooms = [];
  bool _loading = true;
  bool _roomsLoading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final auth = context.read<AuthProvider>();
    if (!auth.isAuthenticated) return;

    final api = context.read<ApiService>();

    // Load tournaments and rooms in parallel
    try {
      final tournaments = await api.getTournaments();
      if (mounted) setState(() { _tournaments = tournaments; _loading = false; });
    } catch (_) {
      if (mounted) setState(() { _loading = false; });
    }

    try {
      final rooms = await api.getUserRooms(auth.username!);
      final roomList = (rooms['rooms'] as List?)?.cast<Map<String, dynamic>>() ?? [];
      if (mounted) setState(() { _userRooms = roomList; _roomsLoading = false; });
    } catch (_) {
      if (mounted) setState(() { _roomsLoading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();

    return Scaffold(
      backgroundColor: AppTheme.bgDark,
      body: Container(
        decoration: const BoxDecoration(gradient: AppTheme.bgGradient),
        child: SafeArea(
          child: CustomScrollView(
            slivers: [
              // ── Header ──
              SliverToBoxAdapter(child: _buildHeader(auth)),

              // ── My Rooms Section ──
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
                  child: _buildSectionHeader('My Rooms', Icons.meeting_room_outlined),
                ),
              ),
              _roomsLoading
                  ? const SliverToBoxAdapter(
                      child: Center(
                        child: Padding(
                          padding: EdgeInsets.all(32),
                          child: CircularProgressIndicator(color: AppTheme.accent),
                        ),
                      ),
                    )
                  : _userRooms.isEmpty
                      ? SliverToBoxAdapter(child: _buildEmptyRooms())
                      : SliverPadding(
                          padding: const EdgeInsets.symmetric(horizontal: 20),
                          sliver: SliverList(
                            delegate: SliverChildBuilderDelegate(
                              (ctx, i) => _buildRoomCard(_userRooms[i]),
                              childCount: _userRooms.length,
                            ),
                          ),
                        ),

              // ── Tournaments Section ──
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 32, 20, 12),
                  child: _buildSectionHeader('Tournaments', Icons.emoji_events_rounded),
                ),
              ),
              _loading
                  ? const SliverToBoxAdapter(
                      child: Center(
                        child: Padding(
                          padding: EdgeInsets.all(32),
                          child: CircularProgressIndicator(color: AppTheme.gold),
                        ),
                      ),
                    )
                  : SliverPadding(
                      padding: const EdgeInsets.fromLTRB(20, 0, 20, 32),
                      sliver: SliverList(
                        delegate: SliverChildBuilderDelegate(
                          (ctx, i) => _buildTournamentCard(_tournaments[i]),
                          childCount: _tournaments.length,
                        ),
                      ),
                    ),

              const SliverToBoxAdapter(child: SizedBox(height: 24)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(AuthProvider auth) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              gradient: AppTheme.goldGradient,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Center(child: Text('🏏', style: TextStyle(fontSize: 22))),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Welcome back,',
                  style: GoogleFonts.outfit(color: AppTheme.textMuted, fontSize: 12),
                ),
                Text(
                  auth.username ?? 'Player',
                  style: GoogleFonts.outfit(
                    color: AppTheme.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.logout_rounded, color: AppTheme.textMuted, size: 20),
            tooltip: 'Logout',
            onPressed: () => auth.logout(),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title, IconData icon) {
    return Row(
      children: [
        Icon(icon, color: AppTheme.gold, size: 20),
        const SizedBox(width: 8),
        Text(
          title,
          style: GoogleFonts.outfit(
            color: AppTheme.textPrimary,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }

  Widget _buildEmptyRooms() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      padding: const EdgeInsets.all(24),
      decoration: AppTheme.glassmorphism(borderRadius: 16),
      child: Column(
        children: [
          Icon(Icons.inbox_rounded, color: AppTheme.textMuted, size: 40),
          const SizedBox(height: 12),
          Text(
            'No rooms yet',
            style: GoogleFonts.outfit(color: AppTheme.textSecondary, fontSize: 15, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 6),
          Text(
            'Create a room from a tournament below, or join one with a room code.',
            textAlign: TextAlign.center,
            style: GoogleFonts.outfit(color: AppTheme.textMuted, fontSize: 13),
          ),
        ],
      ),
    );
  }

  Widget _buildRoomCard(Map<String, dynamic> room) {
    final code = room['room_code'] ?? '';
    final phase = room['game_phase'] ?? 'Unknown';
    final type = room['tournament_type'] ?? '';
    final isAdmin = room['is_admin'] == true;
    final pName = room['participant_name'] ?? '';
    final count = room['participant_count'] ?? 0;

    Color phaseColor = AppTheme.textMuted;
    if (phase == 'Bidding') phaseColor = AppTheme.green;
    if (phase == 'NotStarted') phaseColor = AppTheme.orange;

    return GestureDetector(
      onTap: () => context.go('/auction/$code?name=$pName&admin=$isAdmin'),
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(16),
        decoration: AppTheme.premiumCard(borderRadius: 14),
        child: Row(
          children: [
            // Room code chip
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                color: AppTheme.accent.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.accent.withValues(alpha: 0.2)),
              ),
              child: Center(
                child: Text(
                  code.length > 3 ? code.substring(0, 3) : code,
                  style: GoogleFonts.outfit(
                    color: AppTheme.accent,
                    fontWeight: FontWeight.w800,
                    fontSize: 16,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        code,
                        style: GoogleFonts.outfit(
                          color: AppTheme.textPrimary,
                          fontWeight: FontWeight.w700,
                          fontSize: 15,
                        ),
                      ),
                      if (isAdmin) ...[
                        const SizedBox(width: 6),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: AppTheme.gold.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            'ADMIN',
                            style: GoogleFonts.outfit(
                              color: AppTheme.gold,
                              fontSize: 9,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      _buildMiniChip(type.toUpperCase(), AppTheme.textMuted),
                      const SizedBox(width: 6),
                      _buildMiniChip('$count players', AppTheme.textMuted),
                    ],
                  ),
                ],
              ),
            ),
            // Phase badge
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: phaseColor.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                phase,
                style: GoogleFonts.outfit(
                  color: phaseColor,
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMiniChip(String text, Color color) {
    return Text(
      text,
      style: GoogleFonts.outfit(color: color, fontSize: 11),
    );
  }

  Widget _buildTournamentCard(Map<String, dynamic> t) {
    final id = t['id'] ?? '';
    final name = t['name'] ?? '';
    final desc = t['description'] ?? '';
    final status = t['status'] ?? 'upcoming';
    final icon = t['icon'] ?? '🏅';
    final isActive = status == 'active' || status == 'archived';

    Color statusColor = AppTheme.textMuted;
    String statusLabel = status.toString().toUpperCase();
    if (status == 'active') statusColor = AppTheme.green;
    if (status == 'archived') statusColor = AppTheme.orange;
    if (status == 'upcoming') statusColor = AppTheme.purple;

    return GestureDetector(
      onTap: isActive ? () => context.go('/room/$id') : null,
      child: Opacity(
        opacity: isActive ? 1.0 : 0.5,
        child: Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(18),
          decoration: isActive
              ? AppTheme.glowCard(
                  glowColor: status == 'active' ? AppTheme.gold : AppTheme.accent,
                  borderRadius: 14,
                )
              : AppTheme.glassmorphism(borderRadius: 14),
          child: Row(
            children: [
              // Icon
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Center(child: Text(icon, style: const TextStyle(fontSize: 26))),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name,
                      style: GoogleFonts.outfit(
                        color: AppTheme.textPrimary,
                        fontWeight: FontWeight.w700,
                        fontSize: 15,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      desc,
                      style: GoogleFonts.outfit(color: AppTheme.textMuted, fontSize: 12),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: statusColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  statusLabel,
                  style: GoogleFonts.outfit(
                    color: statusColor,
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.5,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
