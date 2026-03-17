import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import '../theme/app_theme.dart';
import '../services/api_service.dart';

/// IPL team claiming screen — shown to non-admin users joining an IPL room.
/// Once a team is claimed, it cannot be changed.
class TeamClaimScreen extends StatefulWidget {
  final String roomCode;
  final String participantName;

  const TeamClaimScreen({
    super.key,
    required this.roomCode,
    required this.participantName,
  });

  @override
  State<TeamClaimScreen> createState() => _TeamClaimScreenState();
}

class _TeamClaimScreenState extends State<TeamClaimScreen> {
  Map<String, dynamic> _roomState = {};
  bool _loading = true;
  bool _claiming = false;
  String? _selectedTeam;
  String? _error;

  static const Map<String, String> _teamNames = {
    'CSK': 'Chennai Super Kings',
    'MI': 'Mumbai Indians',
    'RCB': 'Royal Challengers Bengaluru',
    'KKR': 'Kolkata Knight Riders',
    'SRH': 'Sunrisers Hyderabad',
    'DC': 'Delhi Capitals',
    'PBKS': 'Punjab Kings',
    'RR': 'Rajasthan Royals',
    'GT': 'Gujarat Titans',
    'LSG': 'Lucknow Super Giants',
  };

  static const Map<String, String> _teamShortVenues = {
    'CSK': 'Chennai',
    'MI': 'Mumbai',
    'RCB': 'Bengaluru',
    'KKR': 'Kolkata',
    'SRH': 'Hyderabad',
    'DC': 'Delhi',
    'PBKS': 'Chandigarh',
    'RR': 'Jaipur',
    'GT': 'Ahmedabad',
    'LSG': 'Lucknow',
  };

  @override
  void initState() {
    super.initState();
    _loadRoomState();
  }

  Future<void> _loadRoomState() async {
    try {
      final api = context.read<ApiService>();
      final state = await api.getAuctionState(widget.roomCode);
      if (mounted) setState(() { _roomState = state; _loading = false; });
    } catch (e) {
      if (mounted) setState(() { _loading = false; _error = e.toString(); });
    }
  }

  Set<String> get _claimedTeams {
    final claimed = _roomState['claimed_teams'];
    if (claimed is Map) {
      return Set<String>.from(claimed.values.map((v) => v.toString()));
    }
    return {};
  }

  String? _claimedBy(String teamCode) {
    final claimed = _roomState['claimed_teams'];
    if (claimed is Map) {
      for (final entry in claimed.entries) {
        if (entry.value == teamCode) return entry.key.toString();
      }
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final isWide = MediaQuery.of(context).size.width > 800;

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppTheme.bgGradient),
        child: SafeArea(
          child: _loading
              ? const Center(child: CircularProgressIndicator(color: AppTheme.gold))
              : SingleChildScrollView(
                  padding: EdgeInsets.symmetric(
                    horizontal: isWide ? 80 : 24,
                    vertical: 32,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Header
                      Text(
                        'ROOM ${widget.roomCode}',
                        style: GoogleFonts.outfit(
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.gold,
                          letterSpacing: 2,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Claim Your\nIPL Franchise',
                        style: GoogleFonts.outfit(
                          fontSize: isWide ? 44 : 32,
                          fontWeight: FontWeight.w800,
                          height: 1.1,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Welcome ${widget.participantName}! Pick your IPL team below. Once claimed, your selection is locked.',
                        style: GoogleFonts.inter(
                          fontSize: 15,
                          color: AppTheme.textSecondary,
                          height: 1.5,
                        ),
                      ),
                      const SizedBox(height: 32),

                      if (_error != null)
                        Container(
                          padding: const EdgeInsets.all(14),
                          margin: const EdgeInsets.only(bottom: 20),
                          decoration: BoxDecoration(
                            color: AppTheme.red.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(14),
                            border: Border.all(color: AppTheme.red.withValues(alpha: 0.2)),
                          ),
                          child: Text(_error!,
                              style: GoogleFonts.inter(
                                  fontSize: 13, color: AppTheme.red)),
                        ),

                      // Team grid
                      GridView.builder(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: isWide ? 5 : 2,
                          mainAxisSpacing: 16,
                          crossAxisSpacing: 16,
                          childAspectRatio: isWide ? 1.0 : 1.15,
                        ),
                        itemCount: _teamNames.length,
                        itemBuilder: (ctx, i) {
                          final code = _teamNames.keys.elementAt(i);
                          return _buildTeamCard(code);
                        },
                      ),

                      const SizedBox(height: 32),

                      // Confirm button
                      if (_selectedTeam != null)
                        Center(
                          child: SizedBox(
                            width: 280,
                            height: 52,
                            child: ElevatedButton(
                              onPressed: _claiming ? null : _confirmClaim,
                              style: ElevatedButton.styleFrom(
                                backgroundColor:
                                    AppTheme.getIplTeamColor(_selectedTeam!),
                                foregroundColor: Colors.white,
                              ),
                              child: _claiming
                                  ? const SizedBox(
                                      width: 20,
                                      height: 20,
                                      child: CircularProgressIndicator(
                                          strokeWidth: 2, color: Colors.white),
                                    )
                                  : Text(
                                      'Confirm ${_teamNames[_selectedTeam]}',
                                      style: GoogleFonts.outfit(
                                          fontWeight: FontWeight.w700),
                                    ),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
        ),
      ),
    );
  }

  Widget _buildTeamCard(String code) {
    final isClaimed = _claimedTeams.contains(code);
    final claimedByName = _claimedBy(code);
    final isSelected = _selectedTeam == code;
    final teamColor = AppTheme.getIplTeamColor(code);
    final isAvailable = !isClaimed;

    return GestureDetector(
      onTap: isAvailable
          ? () => setState(() => _selectedTeam = code)
          : null,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        decoration: BoxDecoration(
          color: isSelected
              ? teamColor.withValues(alpha: 0.15)
              : AppTheme.bgCard,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color: isSelected
                ? teamColor
                : isClaimed
                    ? AppTheme.red.withValues(alpha: 0.3)
                    : Colors.white.withValues(alpha: 0.06),
            width: isSelected ? 2 : 1,
          ),
          boxShadow: isSelected
              ? [BoxShadow(color: teamColor.withValues(alpha: 0.2), blurRadius: 20)]
              : [],
        ),
        child: Stack(
          children: [
            // Claimed overlay
            if (isClaimed)
              Positioned.fill(
                child: Container(
                  decoration: BoxDecoration(
                    color: Colors.black.withValues(alpha: 0.5),
                    borderRadius: BorderRadius.circular(18),
                  ),
                ),
              ),

            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Team color circle
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: teamColor.withValues(alpha: isClaimed ? 0.3 : 0.8),
                      boxShadow: [
                        BoxShadow(
                          color: teamColor.withValues(alpha: 0.3),
                          blurRadius: 12,
                        ),
                      ],
                    ),
                    child: Center(
                      child: Text(
                        code,
                        style: GoogleFonts.outfit(
                          fontSize: 14,
                          fontWeight: FontWeight.w900,
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    _teamNames[code] ?? code,
                    textAlign: TextAlign.center,
                    style: GoogleFonts.outfit(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: isClaimed
                          ? AppTheme.textMuted
                          : AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _teamShortVenues[code] ?? '',
                    style: GoogleFonts.inter(
                      fontSize: 11,
                      color: AppTheme.textMuted,
                    ),
                  ),
                  if (isClaimed) ...[
                    const SizedBox(height: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppTheme.red.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        'Claimed by $claimedByName',
                        style: GoogleFonts.inter(
                          fontSize: 10,
                          color: AppTheme.red,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                  if (isSelected && isAvailable) ...[
                    const SizedBox(height: 6),
                    Icon(Icons.check_circle_rounded,
                        color: teamColor, size: 20),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _confirmClaim() async {
    if (_selectedTeam == null) return;
    setState(() { _claiming = true; _error = null; });

    try {
      final api = context.read<ApiService>();
      await api.claimTeam(
        roomCode: widget.roomCode,
        participantName: widget.participantName,
        teamName: _selectedTeam!,
      );
      if (mounted) {
        context.go(
            '/auction/${widget.roomCode}?name=${widget.participantName}');
      }
    } on ApiException catch (e) {
      if (mounted) setState(() { _error = e.message; _claiming = false; });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _claiming = false; });
    }
  }
}
