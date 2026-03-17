import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'package:shimmer/shimmer.dart';

import '../theme/app_theme.dart';
import '../services/api_service.dart';

class LandingScreen extends StatefulWidget {
  const LandingScreen({super.key});

  @override
  State<LandingScreen> createState() => _LandingScreenState();
}

class _LandingScreenState extends State<LandingScreen>
    with TickerProviderStateMixin {
  List<Map<String, dynamic>> _tournaments = [];
  bool _loading = true;
  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
    _loadTournaments();
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _loadTournaments() async {
    try {
      final api = context.read<ApiService>();
      final tournaments = await api.getTournaments();
      if (mounted) setState(() { _tournaments = tournaments; _loading = false; });
    } catch (e) {
      if (mounted) setState(() { _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    final screenWidth = MediaQuery.of(context).size.width;
    final isWide = screenWidth > 800;

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppTheme.bgGradient),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: EdgeInsets.symmetric(
              horizontal: isWide ? 80 : 24,
              vertical: 40,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildHeader(isWide),
                const SizedBox(height: 48),
                if (_loading) _buildLoadingSkeleton(),
                if (!_loading) ...[
                  _buildSection('🔴 LIVE', _getByStatus('active'), isWide),
                  const SizedBox(height: 40),
                  _buildSection('📋 ARCHIVED', _getByStatus('archived'), isWide),
                  const SizedBox(height: 40),
                  _buildSection('🔜 UPCOMING', _getByStatus('upcoming'), isWide),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(bool isWide) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Live badge
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
          decoration: BoxDecoration(
            color: AppTheme.gold.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(30),
            border: Border.all(color: AppTheme.gold.withValues(alpha: 0.25)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              AnimatedBuilder(
                animation: _pulseController,
                builder: (_, __) => Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: AppTheme.gold.withValues(
                      alpha: 0.5 + _pulseController.value * 0.5,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                'Fantasy Auction Platform',
                style: GoogleFonts.outfit(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.gold,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        Text(
          'Choose Your\nBattleground',
          style: GoogleFonts.outfit(
            fontSize: isWide ? 56 : 38,
            fontWeight: FontWeight.w800,
            height: 1.1,
            color: AppTheme.textPrimary,
          ),
        ),
        const SizedBox(height: 12),
        Text(
          'Select a tournament to start or join a fantasy auction room.',
          style: GoogleFonts.inter(
            fontSize: 16,
            color: AppTheme.textSecondary,
            height: 1.5,
          ),
        ),
      ],
    );
  }

  List<Map<String, dynamic>> _getByStatus(String status) =>
      _tournaments.where((t) => t['status'] == status).toList();

  Widget _buildSection(
    String title,
    List<Map<String, dynamic>> items,
    bool isWide,
  ) {
    if (items.isEmpty) return const SizedBox();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: GoogleFonts.outfit(
            fontSize: 14,
            fontWeight: FontWeight.w700,
            color: AppTheme.textMuted,
            letterSpacing: 2,
          ),
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 20,
          runSpacing: 20,
          children: items
              .map((t) => SizedBox(
                    width: isWide ? 340 : double.infinity,
                    child: _TournamentCard(
                      tournament: t,
                      pulseAnimation: _pulseController,
                    ),
                  ))
              .toList(),
        ),
      ],
    );
  }

  Widget _buildLoadingSkeleton() {
    return Shimmer.fromColors(
      baseColor: AppTheme.bgCard,
      highlightColor: AppTheme.surface,
      child: Wrap(
        spacing: 20,
        runSpacing: 20,
        children: List.generate(
          4,
          (_) => Container(
            width: 340,
            height: 200,
            decoration: BoxDecoration(
              color: AppTheme.bgCard,
              borderRadius: BorderRadius.circular(20),
            ),
          ),
        ),
      ),
    );
  }
}

// ─── Tournament Card Widget ─────────────────────────────────
class _TournamentCard extends StatefulWidget {
  final Map<String, dynamic> tournament;
  final AnimationController pulseAnimation;

  const _TournamentCard({
    required this.tournament,
    required this.pulseAnimation,
  });

  @override
  State<_TournamentCard> createState() => _TournamentCardState();
}

class _TournamentCardState extends State<_TournamentCard> {
  bool _hovered = false;

  Map<String, dynamic> get t => widget.tournament;
  String get status => t['status'] ?? 'upcoming';
  bool get isClickable => status == 'active' || status == 'archived';

  Color get _glowColor {
    switch (status) {
      case 'active':
        return AppTheme.gold;
      case 'archived':
        return AppTheme.accent;
      default:
        return Colors.white.withValues(alpha: 0.05);
    }
  }

  String get _badge {
    switch (status) {
      case 'active':
        return 'LIVE';
      case 'archived':
        return 'ARCHIVED';
      default:
        return 'COMING SOON';
    }
  }

  Color get _badgeColor {
    switch (status) {
      case 'active':
        return AppTheme.green;
      case 'archived':
        return AppTheme.accent;
      default:
        return AppTheme.textMuted;
    }
  }

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      cursor:
          isClickable ? SystemMouseCursors.click : SystemMouseCursors.basic,
      child: GestureDetector(
        onTap: isClickable ? () => _onTap(context) : null,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
          transform: Matrix4.identity()
            ..scale(_hovered && isClickable ? 1.03 : 1.0),
          child: AnimatedBuilder(
            animation: widget.pulseAnimation,
            builder: (_, child) {
              final glowAlpha = status == 'active'
                  ? 0.1 + widget.pulseAnimation.value * 0.1
                  : (status == 'archived' ? 0.08 : 0.02);
              return Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: _hovered && isClickable
                      ? AppTheme.bgCardHover
                      : AppTheme.bgCard,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: _glowColor.withValues(alpha: _hovered ? 0.5 : 0.2),
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: _glowColor.withValues(alpha: glowAlpha),
                      blurRadius: _hovered ? 32 : 16,
                      spreadRadius: 0,
                    ),
                  ],
                ),
                child: child,
              );
            },
            child: _buildContent(),
          ),
        ),
      ),
    );
  }

  Widget _buildContent() {
    final sportIcon = t['icon'] ?? '🏏';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Top row: icon + badge
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(sportIcon, style: const TextStyle(fontSize: 32)),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: _badgeColor.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: _badgeColor.withValues(alpha: 0.3)),
              ),
              child: Text(
                _badge,
                style: GoogleFonts.outfit(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: _badgeColor,
                  letterSpacing: 1,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 20),

        // Tournament name
        Text(
          t['name'] ?? 'Tournament',
          style: GoogleFonts.outfit(
            fontSize: 20,
            fontWeight: FontWeight.w700,
            color: status == 'upcoming'
                ? AppTheme.textMuted
                : AppTheme.textPrimary,
          ),
        ),
        const SizedBox(height: 8),

        // Description
        Text(
          t['description'] ?? '',
          style: GoogleFonts.inter(
            fontSize: 13,
            color: AppTheme.textSecondary,
            height: 1.4,
          ),
        ),
        const SizedBox(height: 16),

        // Date range
        Row(
          children: [
            Icon(Icons.calendar_today_rounded,
                size: 14, color: AppTheme.textMuted),
            const SizedBox(width: 6),
            Text(
              '${t['start_date'] ?? ''} → ${t['end_date'] ?? ''}',
              style: GoogleFonts.inter(
                fontSize: 12,
                color: AppTheme.textMuted,
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),

        // CTA
        if (isClickable)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              gradient: status == 'active'
                  ? AppTheme.goldGradient
                  : AppTheme.accentGradient,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  status == 'active'
                      ? Icons.play_arrow_rounded
                      : Icons.visibility_rounded,
                  size: 18,
                  color: status == 'active' ? AppTheme.bgDark : Colors.white,
                ),
                const SizedBox(width: 6),
                Text(
                  status == 'active' ? 'Start Auction' : 'View / Run Again',
                  style: GoogleFonts.outfit(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color:
                        status == 'active' ? AppTheme.bgDark : Colors.white,
                  ),
                ),
              ],
            ),
          ),

        if (!isClickable)
          Opacity(
            opacity: 0.5,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.lock_rounded,
                      size: 16, color: AppTheme.textMuted),
                  const SizedBox(width: 6),
                  Text(
                    'Coming Soon',
                    style: GoogleFonts.outfit(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textMuted,
                    ),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }

  void _onTap(BuildContext context) {
    final id = t['id'] ?? '';
    context.go('/room/$id');
  }
}
