import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:file_picker/file_picker.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import 'dart:async';
import 'dart:convert';

class AuctionDashboard extends StatefulWidget {
  final String roomCode;
  final String participantName;
  final bool isAdmin;

  const AuctionDashboard({
    super.key,
    required this.roomCode,
    required this.participantName,
    required this.isAdmin,
  });

  @override
  State<AuctionDashboard> createState() => _AuctionDashboardState();
}

class _AuctionDashboardState extends State<AuctionDashboard>
    with TickerProviderStateMixin {
  late TabController _tabController;
  Map<String, dynamic>? _state;
  bool _loading = true;
  String? _error;
  Timer? _refreshTimer;

  // Calculator state
  final _calcUrlController = TextEditingController();
  List<dynamic>? _calcResults;
  bool _calcLoading = false;

  // IPL squads cache
  Map<String, dynamic>? _iplSquads;
  // Schedule cache
  Map<String, dynamic>? _schedule;
  
  // Available players cache
  List<String>? _availablePlayers;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 7, vsync: this);
    _fetchState();
    _refreshTimer =
        Timer.periodic(const Duration(seconds: 15), (_) => _fetchState());
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _tabController.dispose();
    _calcUrlController.dispose();
    super.dispose();
  }

  Future<void> _fetchState() async {
    try {
      final api = context.read<ApiService>();
      final data = await api.getAuctionState(widget.roomCode);
      List<String>? avail;
      try {
        final availRes = await api.getAvailablePlayers(widget.roomCode);
        avail = (availRes['available_players'] as List?)?.map((e) => e['name'] as String).toList();
      } catch (_) {}
      
      if (mounted) setState(() { 
        _state = data; 
        _availablePlayers = avail;
        _loading = false; 
        _error = null; 
      });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  void _showSnack(String msg, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg, style: GoogleFonts.outfit()),
      backgroundColor: isError ? AppTheme.red : AppTheme.green,
    ));
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(
        backgroundColor: AppTheme.bgDark,
        body: Container(
          decoration: const BoxDecoration(gradient: AppTheme.bgGradient),
          child: const Center(child: CircularProgressIndicator(color: AppTheme.accent)),
        ),
      );
    }

    return Scaffold(
      backgroundColor: AppTheme.bgDark,
      appBar: _buildAppBar(),
      body: Container(
        decoration: const BoxDecoration(gradient: AppTheme.bgGradient),
        child: TabBarView(
          controller: _tabController,
          children: [
            _buildOverviewTab(),
            _buildBiddingTab(),
            _buildTradingTab(),
            _buildSquadsTab(),
            _buildScheduleTab(),
            _buildStandingsTab(),
            _buildCalculatorTab(),
          ],
        ),
      ),
    );
  }

  PreferredSizeWidget _buildAppBar() {
    return AppBar(
      backgroundColor: AppTheme.bgDark,
      elevation: 0,
      scrolledUnderElevation: 0,
      title: Row(children: [
        Text(widget.roomCode, style: GoogleFonts.outfit(
          fontWeight: FontWeight.w800, fontSize: 16, color: AppTheme.textPrimary)),
        const SizedBox(width: 6),
        IconButton(
          icon: const Icon(Icons.copy_rounded, size: 16, color: AppTheme.textMuted),
          tooltip: 'Copy Code',
          onPressed: () {
            Clipboard.setData(ClipboardData(text: widget.roomCode));
            _showSnack('Room code copied!');
          },
        ),
        const Spacer(),
        if (widget.isAdmin)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: AppTheme.gold.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text('ADMIN', style: GoogleFonts.outfit(
              color: AppTheme.gold, fontSize: 10, fontWeight: FontWeight.w800)),
          ),
      ]),
      bottom: TabBar(
        controller: _tabController,
        isScrollable: true,
        tabAlignment: TabAlignment.start,
        labelPadding: const EdgeInsets.symmetric(horizontal: 14),
        tabs: const [
          Tab(text: 'Overview'),
          Tab(text: 'Bidding'),
          Tab(text: 'Trading'),
          Tab(text: 'Squads'),
          Tab(text: 'Schedule'),
          Tab(text: 'Standings'),
          Tab(text: 'Calculator'),
        ],
      ),
    );
  }

  // ─── OVERVIEW TAB ────────────────────────────────────────
  Widget _buildOverviewTab() {
    if (_state == null) return _buildErrorState();
    final phase = _state!['game_phase'] ?? 'Unknown';
    final gw = _state!['current_gameweek'] ?? 1;
    final locked = _state!['squads_locked'] == true;
    final deadline = _state!['bidding_deadline'];
    final participants = (_state!['participants'] as List?) ?? [];

    return RefreshIndicator(
      color: AppTheme.accent,
      onRefresh: _fetchState,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Status card
          Container(
            padding: const EdgeInsets.all(18),
            decoration: AppTheme.premiumCard(),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  _statusChip(phase, phase == 'Bidding' ? AppTheme.green : AppTheme.orange),
                  const SizedBox(width: 8),
                  _statusChip('GW $gw', AppTheme.accent),
                  const SizedBox(width: 8),
                  _statusChip(locked ? 'Locked' : 'Open', locked ? AppTheme.red : AppTheme.green),
                ]),
                if (deadline != null) ...[
                  const SizedBox(height: 12),
                  Row(children: [
                    const Icon(Icons.timer_outlined, size: 16, color: AppTheme.textMuted),
                    const SizedBox(width: 6),
                    Text('Deadline: ${_formatDeadline(deadline)}',
                      style: GoogleFonts.outfit(color: AppTheme.textSecondary, fontSize: 13)),
                  ]),
                ],
              ],
            ),
          ),

          const SizedBox(height: 16),

          // Admin controls
          if (widget.isAdmin) _buildAdminControls(),

          // Participants
          Padding(
            padding: const EdgeInsets.only(top: 16, bottom: 8),
            child: Text('Participants (${participants.length})',
              style: GoogleFonts.outfit(color: AppTheme.textPrimary, fontSize: 15, fontWeight: FontWeight.w700)),
          ),
          ...participants.map((p) => _buildParticipantCard(p)),
        ],
      ),
    );
  }

  Widget _statusChip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(label, style: GoogleFonts.outfit(
        color: color, fontSize: 11, fontWeight: FontWeight.w700)),
    );
  }

  Widget _buildAdminControls() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.glowCard(glowColor: AppTheme.gold, borderRadius: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Admin Controls', style: GoogleFonts.outfit(
            color: AppTheme.gold, fontSize: 14, fontWeight: FontWeight.w700)),
          const SizedBox(height: 14),
          Wrap(spacing: 8, runSpacing: 8, children: [
            _adminBtn('Start Auction', Icons.play_arrow_rounded, AppTheme.green, _startAuction),
            _adminBtn('Set Deadline', Icons.timer, AppTheme.red, _setDeadline),
            _adminBtn('Lock Squads', Icons.lock_rounded, AppTheme.orange, _lockSquads),
            _adminBtn('Advance GW', Icons.skip_next_rounded, AppTheme.accent, _advanceGW),
            _adminBtn('100M Boost', Icons.bolt_rounded, AppTheme.gold, _grantBoost),
            _adminBtn('Import CSV', Icons.upload_file_rounded, AppTheme.purple, _importCsv),
          ]),
        ],
      ),
    );
  }

  Widget _adminBtn(String label, IconData icon, Color color, VoidCallback onTap) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(10),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: color.withValues(alpha: 0.2)),
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, size: 16, color: color),
            const SizedBox(width: 6),
            Text(label, style: GoogleFonts.outfit(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
          ]),
        ),
      ),
    );
  }

  Widget _buildParticipantCard(dynamic p) {
    final name = p['name'] ?? '';
    final budget = (p['budget'] ?? 0).toDouble();
    final squadSize = p['squad_size'] ?? 0;
    final eliminated = p['eliminated'] == true;
    final claimCode = p['claim_code'];

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.glassmorphism(borderRadius: 12),
      child: Row(children: [
        Container(
          width: 40, height: 40,
          decoration: BoxDecoration(
            color: eliminated ? AppTheme.red.withValues(alpha: 0.15) : AppTheme.accent.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Center(child: Text(
            name.isNotEmpty ? name[0].toUpperCase() : '?',
            style: GoogleFonts.outfit(
              color: eliminated ? AppTheme.red : AppTheme.accent,
              fontWeight: FontWeight.w800, fontSize: 16),
          )),
        ),
        const SizedBox(width: 12),
        Expanded(child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Text(name, style: GoogleFonts.outfit(
                color: eliminated ? AppTheme.textMuted : AppTheme.textPrimary,
                fontWeight: FontWeight.w600, fontSize: 14)),
              if (eliminated) ...[
                const SizedBox(width: 6),
                _statusChip('OUT', AppTheme.red),
              ],
            ]),
            const SizedBox(height: 2),
            Row(children: [
              Text('$squadSize players', style: GoogleFonts.outfit(
                color: AppTheme.textMuted, fontSize: 12)),
              if (widget.isAdmin && claimCode != null) ...[
                const SizedBox(width: 8),
                Text('PIN: $claimCode', style: GoogleFonts.outfit(
                  color: AppTheme.orange, fontSize: 12, fontWeight: FontWeight.bold)),
              ],
            ]),
          ],
        )),
        Text('${budget.toStringAsFixed(0)}M', style: GoogleFonts.outfit(
          color: AppTheme.green, fontWeight: FontWeight.w700, fontSize: 14)),
      ]),
    );
  }

  // ─── BIDDING TAB ─────────────────────────────────────────
  Widget _buildBiddingTab() {
    if (_state == null) return _buildErrorState();
    final bids = (_state!['active_bids'] as List?) ?? [];
    final participants = (_state!['participants'] as List?) ?? [];

    // Collect all owned players
    final Set<String> ownedPlayers = {};
    for (final p in participants) {
      for (final sq in (p['squad'] as List?) ?? []) {
        ownedPlayers.add((sq as Map)['name'] ?? '');
      }
    }

    return RefreshIndicator(
      color: AppTheme.accent,
      onRefresh: _fetchState,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Active bids
          Text('Active Bids', style: GoogleFonts.outfit(
            color: AppTheme.textPrimary, fontSize: 15, fontWeight: FontWeight.w700)),
          const SizedBox(height: 10),
          if (bids.isEmpty)
            _buildEmptyCard('No active bids', 'Place a bid on an available player below')
          else
            ...bids.map((b) => _buildBidCard(b)),

          const SizedBox(height: 24),

          // Place bid
          Text('Place a Bid', style: GoogleFonts.outfit(
            color: AppTheme.textPrimary, fontSize: 15, fontWeight: FontWeight.w700)),
          const SizedBox(height: 10),
          _buildPlaceBidSection(ownedPlayers),
        ],
      ),
    );
  }

  Widget _buildBidCard(dynamic bid) {
    final player = bid['player'] ?? '';
    final amount = bid['amount'] ?? 0;
    final bidder = bid['bidder'] ?? '';
    final isMyBid = bidder == widget.participantName;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.glassmorphism(
        borderRadius: 12,
        borderColor: isMyBid ? AppTheme.accent.withValues(alpha: 0.3) : null,
      ),
      child: Row(children: [
        Expanded(child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(player, style: GoogleFonts.outfit(
              color: AppTheme.textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
            const SizedBox(height: 2),
            Text('by $bidder', style: GoogleFonts.outfit(
              color: AppTheme.textMuted, fontSize: 12)),
            const SizedBox(height: 4),
            _buildBidExpiry(bid),
          ],
        )),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
          decoration: BoxDecoration(
            color: AppTheme.gold.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text('${amount}M', style: GoogleFonts.outfit(
            color: AppTheme.gold, fontWeight: FontWeight.w800, fontSize: 14)),
        ),
      ]),
    );
  }
  Widget _buildBidExpiry(dynamic bid) {
    final expiresStr = bid['expires'] as String?;
    if (expiresStr == null) return const SizedBox();

    try {
      final expires = DateTime.parse(expiresStr);
      final now = DateTime.now();
      
      // Also consider global deadline
      final deadlineStr = _state?['bidding_deadline'] as String?;
      DateTime? deadlineCandidate;
      if (deadlineStr != null) {
        deadlineCandidate = DateTime.parse(deadlineStr);
      }

      final actualExpiry = (deadlineCandidate != null && deadlineCandidate.isBefore(expires))
          ? deadlineCandidate
          : expires;

      final diff = actualExpiry.difference(now);
      if (diff.isNegative) {
        return Text('Closing...', style: GoogleFonts.outfit(color: AppTheme.green, fontSize: 11, fontWeight: FontWeight.bold));
      }

      final h = diff.inHours;
      final m = diff.inMinutes % 60;
      return Text('Wins in: ${h}h ${m}m', style: GoogleFonts.outfit(
        color: AppTheme.accent, fontSize: 11, fontWeight: FontWeight.w600));
    } catch (_) {
      return const SizedBox();
    }
  }

  final _bidPlayerCtrl = TextEditingController();
  final _bidAmountCtrl = TextEditingController();

  Widget _buildPlaceBidSection(Set<String> ownedPlayers) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.premiumCard(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Autocomplete<String>(
            optionsBuilder: (TextEditingValue textEditingValue) {
              if (textEditingValue.text.isEmpty || _availablePlayers == null) {
                return const Iterable<String>.empty();
              }
              return _availablePlayers!.where((p) => p.toLowerCase().contains(textEditingValue.text.toLowerCase()));
            },
            onSelected: (String selection) {
              _bidPlayerCtrl.text = selection;
            },
            fieldViewBuilder: (context, controller, focusNode, onFieldSubmitted) {
              return TextField(
                controller: controller,
                focusNode: focusNode,
                style: GoogleFonts.outfit(color: AppTheme.textPrimary),
                onChanged: (val) => _bidPlayerCtrl.text = val,
                decoration: const InputDecoration(
                  labelText: 'Player name',
                  prefixIcon: Icon(Icons.person_search, color: AppTheme.textMuted, size: 20),
                ),
              );
            },
            optionsViewBuilder: (context, onSelected, options) {
              return Align(
                alignment: Alignment.topLeft,
                child: Material(
                  elevation: 8,
                  borderRadius: BorderRadius.circular(12),
                  color: AppTheme.bgCard,
                  child: Container(
                    width: 300, // Explicit width
                    constraints: const BoxConstraints(maxHeight: 250),
                    child: ListView.builder(
                      padding: EdgeInsets.zero,
                      shrinkWrap: true,
                      itemCount: options.length,
                      itemBuilder: (BuildContext context, int index) {
                        final String option = options.elementAt(index);
                        return ListTile(
                          title: Text(option, style: GoogleFonts.outfit(color: AppTheme.textPrimary, fontSize: 13)),
                          onTap: () => onSelected(option),
                        );
                      },
                    ),
                  ),
                ),
              );
            },
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _bidAmountCtrl,
            keyboardType: TextInputType.number,
            style: GoogleFonts.outfit(color: AppTheme.textPrimary),
            decoration: const InputDecoration(
              labelText: 'Bid amount (M)',
              prefixIcon: Icon(Icons.currency_rupee, color: AppTheme.textMuted, size: 20),
              helperText: 'Min 5M. Increments of 5 above 50M.',
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 44,
            child: ElevatedButton(
              onPressed: () => _placeBid(ownedPlayers),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.accent,
                foregroundColor: Colors.white,
              ),
              child: Text('Place Bid', style: GoogleFonts.outfit(fontWeight: FontWeight.w700)),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _placeBid(Set<String> ownedPlayers) async {
    final player = _bidPlayerCtrl.text.trim();
    final amount = int.tryParse(_bidAmountCtrl.text.trim()) ?? 0;

    if (player.isEmpty || amount <= 0) {
      _showSnack('Enter player name and amount', isError: true);
      return;
    }
    if (ownedPlayers.contains(player)) {
      _showSnack('Player already in someone\'s squad', isError: true);
      return;
    }
    try {
      final api = context.read<ApiService>();
      await api.placeBid(
        roomCode: widget.roomCode,
        participantName: widget.participantName,
        playerName: player,
        amount: amount,
      );
      _showSnack('Bid placed: $player for ${amount}M');
      _bidPlayerCtrl.clear();
      _bidAmountCtrl.clear();
      _fetchState();
    } catch (e) {
      _showSnack(e.toString(), isError: true);
    }
  }

  // ─── TRADING TAB ─────────────────────────────────────────
  Widget _buildTradingTab() {
    return RefreshIndicator(
      color: AppTheme.accent,
      onRefresh: _fetchState,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Trading', style: GoogleFonts.outfit(
            color: AppTheme.textPrimary, fontSize: 15, fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          _buildEmptyCard('Trading System', 'Propose trades, respond to offers, and manage your squad transactions from this tab.'),
          const SizedBox(height: 16),
          SizedBox(
            height: 44,
            child: OutlinedButton.icon(
              onPressed: _loadTradeLog,
              icon: const Icon(Icons.receipt_long_rounded, size: 18),
              label: Text('View Trade Log', style: GoogleFonts.outfit(fontWeight: FontWeight.w600)),
            ),
          ),
        ],
      ),
    );
  }

  // ─── SQUADS TAB ──────────────────────────────────────────
  Widget _buildSquadsTab() {
    if (_state == null) return _buildErrorState();
    final participants = (_state!['participants'] as List?) ?? [];

    return RefreshIndicator(
      color: AppTheme.accent,
      onRefresh: _fetchState,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('All Squads', style: GoogleFonts.outfit(
            color: AppTheme.textPrimary, fontSize: 15, fontWeight: FontWeight.w700)),
          const SizedBox(height: 10),
          ...participants.map((p) => _buildSquadExpansionCard(p)),

          const SizedBox(height: 24),

          // IPL Squads
          Row(children: [
            Text('IPL 2026 Squads', style: GoogleFonts.outfit(
              color: AppTheme.textPrimary, fontSize: 15, fontWeight: FontWeight.w700)),
            const Spacer(),
            if (_iplSquads == null)
              TextButton(
                onPressed: _loadIplSquads,
                child: Text('Load', style: GoogleFonts.outfit(color: AppTheme.accent, fontSize: 13)),
              ),
          ]),
          const SizedBox(height: 10),
          if (_iplSquads != null) ..._buildIplSquadCards(),
        ],
      ),
    );
  }

  Widget _buildSquadExpansionCard(dynamic p) {
    final name = p['name'] ?? '';
    final budget = (p['budget'] ?? 0).toDouble();
    final squad = (p['squad'] as List?) ?? [];
    final isMe = name == widget.participantName;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: AppTheme.premiumCard(borderRadius: 14),
      child: ExpansionTile(
        tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        leading: Container(
          width: 36, height: 36,
          decoration: BoxDecoration(
            color: (isMe ? AppTheme.accent : AppTheme.surface),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Center(child: Text(
            name.isNotEmpty ? name[0].toUpperCase() : '?',
            style: GoogleFonts.outfit(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 14),
          )),
        ),
        title: Text(name, style: GoogleFonts.outfit(
          color: AppTheme.textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
        subtitle: Text('${squad.length} players · ${budget.toStringAsFixed(0)}M',
          style: GoogleFonts.outfit(color: AppTheme.textMuted, fontSize: 12)),
        children: squad.isEmpty
            ? [Text('No players yet', style: GoogleFonts.outfit(color: AppTheme.textMuted, fontSize: 13))]
            : squad.map<Widget>((pl) {
                final playerName = pl['name'] ?? '';
                final role = pl['role'] ?? 'Unknown';
                final price = pl['price'] ?? 0;
                final roleColor = AppTheme.getRoleColor(role);
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: roleColor.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(AppTheme.getRoleShort(role), style: GoogleFonts.outfit(
                        color: roleColor, fontSize: 10, fontWeight: FontWeight.w700)),
                    ),
                    const SizedBox(width: 8),
                    Expanded(child: Text(playerName, style: GoogleFonts.outfit(
                      color: AppTheme.textPrimary, fontSize: 13))),
                    Text('${price}M', style: GoogleFonts.outfit(
                      color: AppTheme.textMuted, fontSize: 12)),
                  ]),
                );
              }).toList(),
      ),
    );
  }

  Future<void> _loadIplSquads() async {
    try {
      final api = context.read<ApiService>();
      final data = await api.getIplSquads();
      if (mounted) setState(() => _iplSquads = data);
    } catch (e) {
      _showSnack('Failed to load IPL squads', isError: true);
    }
  }

  List<Widget> _buildIplSquadCards() {
    final teams = _iplSquads?['teams'] as Map<String, dynamic>? ?? {};
    return teams.entries.map((entry) {
      final code = entry.key;
      final team = entry.value as Map<String, dynamic>;
      final name = team['name'] ?? code;
      final squad = (team['squad'] as List?) ?? [];
      final color = AppTheme.getIplTeamColor(code);

      return Container(
        margin: const EdgeInsets.only(bottom: 10),
        decoration: AppTheme.glowCard(glowColor: color, borderRadius: 14),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          leading: Container(
            width: 36, height: 36,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Center(child: Text(code, style: GoogleFonts.outfit(
              color: color, fontWeight: FontWeight.w800, fontSize: 11))),
          ),
          title: Text(name, style: GoogleFonts.outfit(
            color: AppTheme.textPrimary, fontWeight: FontWeight.w600, fontSize: 14)),
          subtitle: Text('${squad.length} players', style: GoogleFonts.outfit(
            color: AppTheme.textMuted, fontSize: 12)),
          children: squad.map<Widget>((pl) {
            final pName = pl['name'] ?? '';
            final role = pl['role'] ?? '';
            final roleColor = AppTheme.getRoleColor(role);
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: roleColor.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(AppTheme.getRoleShort(role), style: GoogleFonts.outfit(
                    color: roleColor, fontSize: 10, fontWeight: FontWeight.w700)),
                ),
                const SizedBox(width: 8),
                Expanded(child: Text(pName, style: GoogleFonts.outfit(
                  color: AppTheme.textPrimary, fontSize: 13))),
              ]),
            );
          }).toList(),
        ),
      );
    }).toList();
  }

  // ─── SCHEDULE TAB ────────────────────────────────────────
  Widget _buildScheduleTab() {
    return RefreshIndicator(
      color: AppTheme.accent,
      onRefresh: _fetchState,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(children: [
            Text('Match Schedule', style: GoogleFonts.outfit(
              color: AppTheme.textPrimary, fontSize: 15, fontWeight: FontWeight.w700)),
            const Spacer(),
            if (_schedule == null)
              TextButton(
                onPressed: _loadSchedule,
                child: Text('Load', style: GoogleFonts.outfit(color: AppTheme.accent, fontSize: 13)),
              ),
          ]),
          const SizedBox(height: 10),
          if (_schedule != null) ..._buildScheduleCards()
          else
            _buildEmptyCard('Schedule', 'Tap "Load" to view the IPL 2026 match schedule'),
        ],
      ),
    );
  }

  Future<void> _loadSchedule() async {
    try {
      final api = context.read<ApiService>();
      final data = await api.getSchedule(widget.roomCode);
      if (mounted) setState(() => _schedule = data);
    } catch (e) {
      _showSnack('Failed to load schedule', isError: true);
    }
  }

  List<Widget> _buildScheduleCards() {
    final gameweeks = _schedule?['gameweeks'] as Map<String, dynamic>? ?? {};
    if (gameweeks.isEmpty) {
      // Try flat schedule format
      final matches = _schedule?['matches'] as List? ?? [];
      if (matches.isEmpty) return [_buildEmptyCard('No matches', 'Schedule data is empty')];
      return matches.map<Widget>((m) => _buildMatchCard(m)).toList();
    }

    return gameweeks.entries.map<Widget>((gw) {
      final gwName = gw.key;
      final matchData = (gw.value as Map<String, dynamic>?) ?? {};
      final matches = (matchData['matches'] as List?) ?? [];
      final gwTitle = matchData['name'] ?? 'Gameweek $gwName';
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text(gwTitle, style: GoogleFonts.outfit(
              color: AppTheme.gold, fontSize: 13, fontWeight: FontWeight.w700)),
          ),
          ...matches.map<Widget>((m) => _buildMatchCard(m)),
          const SizedBox(height: 8),
        ],
      );
    }).toList();
  }

  Widget _buildMatchCard(dynamic m) {
    final teams = m['teams'] as List? ?? [];
    final team1 = teams.isNotEmpty ? teams[0] : (m['team1'] ?? m['home'] ?? '');
    final team2 = teams.length > 1 ? teams[1] : (m['team2'] ?? m['away'] ?? '');
    final date = m['date'] ?? '';
    final time = m['time'] ?? '';
    final venue = m['venue'] ?? '';

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.glassmorphism(borderRadius: 12),
      child: Row(children: [
        Expanded(child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('$team1 vs $team2', style: GoogleFonts.outfit(
              color: AppTheme.textPrimary, fontWeight: FontWeight.w600, fontSize: 13)),
            if (venue.isNotEmpty)
              Text(venue, style: GoogleFonts.outfit(
                color: AppTheme.textMuted, fontSize: 11)),
          ],
        )),
        if (date.isNotEmpty)
          Text('$date\n$time', textAlign: TextAlign.right, style: GoogleFonts.outfit(
            color: AppTheme.textSecondary, fontSize: 11)),
      ]),
    );
  }

  // ─── STANDINGS TAB ───────────────────────────────────────
  Widget _buildStandingsTab() {
    return RefreshIndicator(
      color: AppTheme.accent,
      onRefresh: _fetchState,
      child: FutureBuilder(
        future: context.read<ApiService>().getStandings(widget.roomCode),
        builder: (ctx, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator(color: AppTheme.accent));
          }
          if (snap.hasError) {
            return _buildEmptyCard('No standings', snap.error.toString());
          }
          final data = snap.data;
          final standings = (data?['standings'] as List?) ?? [];
          if (standings.isEmpty) {
            return ListView(
              padding: const EdgeInsets.all(16),
              children: [_buildEmptyCard('No standings yet', 'Scores will appear after the first gameweek')],
            );
          }

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text('Standings', style: GoogleFonts.outfit(
                color: AppTheme.textPrimary, fontSize: 15, fontWeight: FontWeight.w700)),
              const SizedBox(height: 10),
              ...standings.asMap().entries.map((e) {
                final idx = e.key;
                final s = e.value;
                final rank = s['rank'] ?? (idx + 1);
                final name = s['participant'] ?? '';
                final pts = (s['points'] ?? 0).toDouble();

                Color rankColor = AppTheme.textMuted;
                if (rank == 1) rankColor = AppTheme.gold;
                if (rank == 2) rankColor = AppTheme.accentLight;
                if (rank == 3) rankColor = AppTheme.orange;

                return Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(14),
                  decoration: rank <= 3
                      ? AppTheme.glowCard(glowColor: rankColor, borderRadius: 12)
                      : AppTheme.glassmorphism(borderRadius: 12),
                  child: Row(children: [
                    SizedBox(
                      width: 30,
                      child: Text('#$rank', style: GoogleFonts.outfit(
                        color: rankColor, fontWeight: FontWeight.w800, fontSize: 16)),
                    ),
                    const SizedBox(width: 10),
                    Expanded(child: Text(name, style: GoogleFonts.outfit(
                      color: AppTheme.textPrimary, fontWeight: FontWeight.w600, fontSize: 14))),
                    Text('${pts.toStringAsFixed(0)} pts', style: GoogleFonts.outfit(
                      color: rankColor, fontWeight: FontWeight.w800, fontSize: 14)),
                  ]),
                );
              }),
            ],
          );
        },
      ),
    );
  }

  // ─── CALCULATOR TAB ──────────────────────────────────────
  Widget _buildCalculatorTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Fantasy Points Calculator', style: GoogleFonts.outfit(
          color: AppTheme.textPrimary, fontSize: 15, fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        Text('Paste a Cricbuzz scorecard URL to calculate points',
          style: GoogleFonts.outfit(color: AppTheme.textMuted, fontSize: 13)),
        const SizedBox(height: 16),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: AppTheme.premiumCard(),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextField(
                controller: _calcUrlController,
                style: GoogleFonts.outfit(color: AppTheme.textPrimary, fontSize: 13),
                decoration: const InputDecoration(
                  labelText: 'Cricbuzz URL',
                  prefixIcon: Icon(Icons.link, color: AppTheme.textMuted, size: 20),
                ),
              ),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(
                  child: SizedBox(height: 42,
                    child: ElevatedButton(
                      onPressed: _calcLoading ? null : _calculatePoints,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.accent,
                        foregroundColor: Colors.white,
                      ),
                      child: _calcLoading
                          ? const SizedBox(width: 18, height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : Text('Calculate', style: GoogleFonts.outfit(fontWeight: FontWeight.w700)),
                    ),
                  ),
                ),
                if (widget.isAdmin) ...[
                  const SizedBox(width: 8),
                  Expanded(
                    child: SizedBox(height: 42,
                      child: OutlinedButton(
                        onPressed: _calcLoading ? null : _computeForGW,
                        child: Text('Save for GW', style: GoogleFonts.outfit(fontWeight: FontWeight.w600, fontSize: 13)),
                      ),
                    ),
                  ),
                ],
              ]),
            ],
          ),
        ),
        const SizedBox(height: 16),
        if (_calcResults != null)
          ..._calcResults!.asMap().entries.map((e) {
            final idx = e.key;
            final p = e.value;
            final name = p['name'] ?? '';
            final pts = (p['points'] ?? 0).toDouble();

            Color medal = Colors.transparent;
            if (idx == 0) medal = AppTheme.gold;
            if (idx == 1) medal = AppTheme.accentLight;
            if (idx == 2) medal = AppTheme.orange;

            return Container(
              margin: const EdgeInsets.only(bottom: 6),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: idx < 3
                  ? AppTheme.glowCard(glowColor: medal, borderRadius: 10)
                  : AppTheme.glassmorphism(borderRadius: 10),
              child: Row(children: [
                SizedBox(width: 28, child: Text(
                  '${idx + 1}',
                  style: GoogleFonts.outfit(color: idx < 3 ? medal : AppTheme.textMuted,
                    fontWeight: FontWeight.w700, fontSize: 13),
                )),
                Expanded(child: Text(name, style: GoogleFonts.outfit(
                  color: AppTheme.textPrimary, fontSize: 13))),
                Text('${pts.toStringAsFixed(1)} pts', style: GoogleFonts.outfit(
                  color: idx < 3 ? medal : AppTheme.textSecondary,
                  fontWeight: FontWeight.w700, fontSize: 13)),
              ]),
            );
          }),
      ],
    );
  }

  // ─── SHARED WIDGETS ──────────────────────────────────────
  Widget _buildEmptyCard(String title, String subtitle) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.glassmorphism(borderRadius: 14),
      child: Column(
        children: [
          Text(title, style: GoogleFonts.outfit(
            color: AppTheme.textSecondary, fontSize: 14, fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          Text(subtitle, style: GoogleFonts.outfit(
            color: AppTheme.textMuted, fontSize: 12), textAlign: TextAlign.center),
        ],
      ),
    );
  }

  Widget _buildErrorState() {
    return Center(child: Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Icon(Icons.error_outline, color: AppTheme.red, size: 40),
        const SizedBox(height: 12),
        Text(_error ?? 'Failed to load', style: GoogleFonts.outfit(color: AppTheme.textSecondary)),
        const SizedBox(height: 16),
        ElevatedButton(onPressed: _fetchState, child: const Text('Retry')),
      ],
    ));
  }

  String _formatDeadline(String iso) {
    try {
      final dt = DateTime.parse(iso);
      return '${dt.day}/${dt.month} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return iso;
    }
  }

  // ─── ADMIN ACTIONS ───────────────────────────────────────
  Future<void> _startAuction() async {
    try {
      final api = context.read<ApiService>();
      await api.startAuction(roomCode: widget.roomCode, adminName: widget.participantName);
      _showSnack('Auction started!');
      _fetchState();
    } catch (e) { _showSnack(e.toString(), isError: true); }
  }

  Future<void> _setDeadline() async {
    final date = await showDatePicker(
      context: context, 
      initialDate: DateTime.now(), 
      firstDate: DateTime.now(), 
      lastDate: DateTime.now().add(const Duration(days: 365)),
      builder: (context, child) {
        return Theme(
          data: ThemeData.dark().copyWith(
            colorScheme: const ColorScheme.dark(
              primary: AppTheme.accent,
              onPrimary: Colors.white,
              surface: AppTheme.bgCard,
              onSurface: AppTheme.textPrimary,
            ),
          ),
          child: child!,
        );
      },
    );
    if (date == null || !mounted) return;
    final time = await showTimePicker(
      context: context, 
      initialTime: TimeOfDay.now(),
      builder: (context, child) {
        return Theme(
          data: ThemeData.dark().copyWith(
            colorScheme: const ColorScheme.dark(
              primary: AppTheme.accent,
              onPrimary: Colors.white,
              surface: AppTheme.bgCard,
              onSurface: AppTheme.textPrimary,
            ),
          ),
          child: child!,
        );
      },
    );
    if (time == null || !mounted) return;
    final dt = DateTime(date.year, date.month, date.day, time.hour, time.minute);
    try {
      final api = context.read<ApiService>();
      await api.setDeadline(roomCode: widget.roomCode, adminName: widget.participantName, deadlineIso: dt.toUtc().toIso8601String());
      _showSnack('Deadline set to \${dt.toLocal()}');
      _fetchState();
    } catch (e) {
      _showSnack(e.toString(), isError: true);
    }
  }

  Future<void> _lockSquads() async {
    try {
      final api = context.read<ApiService>();
      await api.lockSquads(roomCode: widget.roomCode, adminName: widget.participantName);
      _showSnack('Squads locked!');
      _fetchState();
    } catch (e) { _showSnack(e.toString(), isError: true); }
  }

  Future<void> _advanceGW() async {
    try {
      final api = context.read<ApiService>();
      await api.advanceGameweek(roomCode: widget.roomCode, adminName: widget.participantName);
      _showSnack('Advanced to next gameweek!');
      _fetchState();
    } catch (e) { _showSnack(e.toString(), isError: true); }
  }

  Future<void> _grantBoost() async {
    try {
      final api = context.read<ApiService>();
      await api.grantBoost(roomCode: widget.roomCode, adminName: widget.participantName);
      _showSnack('100M boost granted!');
      _fetchState();
    } catch (e) { _showSnack(e.toString(), isError: true); }
  }

  Future<void> _importCsv() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['csv'],
        withData: true,
      );
      if (result == null || result.files.isEmpty) return;
      final bytes = result.files.first.bytes;
      if (bytes == null) {
        _showSnack('Could not read file', isError: true);
        return;
      }
      final csvText = utf8.decode(bytes);
      final api = context.read<ApiService>();
      final response = await api.importCsv(
        roomCode: widget.roomCode,
        adminName: widget.participantName,
        csvText: csvText,
        dryRun: true,
      );
      
      final squads = response['squads'] as Map<String, dynamic>;
      final budgets = (response['budgets'] as Map<String, dynamic>?) ?? {};

      if (!mounted) return;
      
      final confirm = await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (ctx) => _CsvReviewDialog(squads: squads, budgets: budgets),
      );
      
      if (confirm == true) {
         await api.importSquads(
           roomCode: widget.roomCode, 
           adminName: widget.participantName, 
           squads: squads,
           budgets: budgets,
         );
         if (mounted) _showSnack('CSV Imported Successfully!');
         _fetchState();
      }
    } catch (e) { _showSnack(e.toString(), isError: true); }
  }

  Future<void> _calculatePoints() async {
    final url = _calcUrlController.text.trim();
    if (url.isEmpty) { _showSnack('Enter a URL', isError: true); return; }
    setState(() => _calcLoading = true);
    try {
      final api = context.read<ApiService>();
      final data = await api.calculatePoints(url);
      if (mounted) setState(() {
        _calcResults = data['players'] ?? [];
        _calcLoading = false;
      });
    } catch (e) {
      if (mounted) setState(() => _calcLoading = false);
      _showSnack(e.toString(), isError: true);
    }
  }

  Future<void> _computeForGW() async {
    final url = _calcUrlController.text.trim();
    if (url.isEmpty) { _showSnack('Enter a URL', isError: true); return; }
    setState(() => _calcLoading = true);
    try {
      final api = context.read<ApiService>();
      await api.calculateScores(
        roomCode: widget.roomCode,
        adminName: widget.participantName,
        cricbuzzUrl: url,
      );
      _showSnack('Scores saved for current GW!');
      if (mounted) setState(() => _calcLoading = false);
    } catch (e) {
      if (mounted) setState(() => _calcLoading = false);
      _showSnack(e.toString(), isError: true);
    }
  }

  Future<void> _loadTradeLog() async {
    try {
      final api = context.read<ApiService>();
      final data = await api.getTradeLog(widget.roomCode);
      final log = (data['trade_log'] as List?) ?? [];
      if (mounted && log.isNotEmpty) {
        showModalBottomSheet(
          context: context,
          backgroundColor: AppTheme.bgCard,
          shape: const RoundedRectangleBorder(
            borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
          ),
          builder: (_) => Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('Trade Log', style: GoogleFonts.outfit(
                  color: AppTheme.textPrimary, fontSize: 16, fontWeight: FontWeight.w700)),
                const SizedBox(height: 12),
                ...log.take(20).map((entry) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Text(
                    '${entry['time']} — ${entry['msg']}'.replaceAll('**', ''),
                    style: GoogleFonts.outfit(color: AppTheme.textSecondary, fontSize: 12),
                  ),
                )),
              ],
            ),
          ),
        );
      } else {
        _showSnack('No trades yet');
      }
    } catch (e) { _showSnack(e.toString(), isError: true); }
  }
}

class _CsvReviewDialog extends StatefulWidget {
  final Map<String, dynamic> squads;
  final Map<String, dynamic> budgets;
  const _CsvReviewDialog({required this.squads, required this.budgets});
  @override
  State<_CsvReviewDialog> createState() => _CsvReviewDialogState();
}

class _CsvReviewDialogState extends State<_CsvReviewDialog> {
  late Map<String, dynamic> _editableSquads;
  late Map<String, dynamic> _editableBudgets;

  @override
  void initState() {
    super.initState();
    _editableSquads = jsonDecode(jsonEncode(widget.squads));
    _editableBudgets = jsonDecode(jsonEncode(widget.budgets));
  }

  bool get _isValid {
    for (var squad in _editableSquads.values) {
      for (var p in (squad as List)) {
        if (p['role'] == 'Unknown' || p['name'] == 'Unknown') return false;
      }
    }
    return true;
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: AppTheme.bgCard,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Container(
        width: 600,
        height: 600,
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Review CSV Import', style: GoogleFonts.outfit(color: AppTheme.textPrimary, fontSize: 18, fontWeight: FontWeight.bold)),
                if (!_isValid)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(color: AppTheme.red.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(6)),
                    child: Text('MATCHING REQUIRED', style: GoogleFonts.outfit(color: AppTheme.red, fontSize: 10, fontWeight: FontWeight.w900)),
                  ),
              ],
            ),
            const SizedBox(height: 10),
            Text('Verify player roles and team budgets below. All players must be matched to JSON data.', style: GoogleFonts.outfit(color: AppTheme.textMuted, fontSize: 13)),
            const SizedBox(height: 16),
            Expanded(
              child: ListView(
                children: _editableSquads.entries.map((e) {
                  final List players = e.value as List;
                  final teamName = e.key;
                  final budgetValue = _editableBudgets[teamName] ?? 0;

                  return ExpansionTile(
                    title: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('$teamName (${players.length} players)', style: const TextStyle(color: AppTheme.accent)),
                        Text('Budget: ${budgetValue}M', style: const TextStyle(color: AppTheme.gold, fontSize: 12)),
                      ],
                    ),
                    children: [
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                        child: TextFormField(
                          initialValue: budgetValue.toString(),
                          keyboardType: TextInputType.number,
                          style: const TextStyle(color: AppTheme.gold, fontSize: 13),
                          decoration: const InputDecoration(
                            labelText: 'Custom Remaining Budget (Optional)',
                            labelStyle: TextStyle(color: AppTheme.textMuted, fontSize: 11),
                            enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: AppTheme.textMuted)),
                          ),
                          onChanged: (val) => setState(() => _editableBudgets[teamName] = int.tryParse(val) ?? budgetValue),
                        ),
                      ),
                      ...players.map((p) {
                        final List? suggestions = p['suggestions'] as List?;
                        final isUnknown = p['role'] == 'Unknown';
                        return Container(
                          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: isUnknown ? AppTheme.red.withValues(alpha: 0.05) : Colors.white.withValues(alpha: 0.03),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: isUnknown ? AppTheme.red.withValues(alpha: 0.3) : Colors.white.withValues(alpha: 0.05)),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Expanded(
                                    flex: 3,
                                    child: TextFormField(
                                      initialValue: p['name'],
                                      style: GoogleFonts.outfit(color: isUnknown ? AppTheme.red : AppTheme.textPrimary, fontSize: 13),
                                      decoration: const InputDecoration(
                                        labelText: 'Player Name',
                                        labelStyle: TextStyle(color: AppTheme.textMuted, fontSize: 10),
                                        isDense: true,
                                        contentPadding: EdgeInsets.symmetric(vertical: 8),
                                      ),
                                      onChanged: (val) => setState(() => p['name'] = val),
                                    ),
                                  ),
                                  const SizedBox(width: 12),
                                  Expanded(
                                    flex: 2,
                                    child: TextFormField(
                                      initialValue: p['role'],
                                      style: GoogleFonts.outfit(color: isUnknown ? AppTheme.red : AppTheme.textPrimary, fontSize: 13),
                                      decoration: InputDecoration(
                                        labelText: 'Role',
                                        labelStyle: const TextStyle(color: AppTheme.textMuted, fontSize: 10),
                                        isDense: true,
                                        contentPadding: const EdgeInsets.symmetric(vertical: 8),
                                        suffixText: '${p["buy_price"]}M',
                                        suffixStyle: const TextStyle(color: AppTheme.gold, fontSize: 10),
                                      ),
                                      onChanged: (val) => setState(() => p['role'] = val),
                                    ),
                                  ),
                                ],
                              ),
                              if (suggestions != null && suggestions.isNotEmpty) ...[
                                const SizedBox(height: 8),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8),
                                  decoration: BoxDecoration(
                                    color: AppTheme.accent.withValues(alpha: 0.1),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: DropdownButtonHideUnderline(
                                    child: DropdownButton<Map<String, dynamic>>(
                                      isExpanded: true,
                                      hint: Text('Suggested matches...', style: GoogleFonts.outfit(color: AppTheme.accent, fontSize: 11)),
                                      icon: const Icon(Icons.auto_awesome, size: 14, color: AppTheme.accent),
                                      items: suggestions.map((s) {
                                        final sm = s as Map<String, dynamic>;
                                        return DropdownMenuItem<Map<String, dynamic>>(
                                          value: sm,
                                          child: Text('${sm['name']} (${sm['role']} - ${sm['team']})', 
                                            style: GoogleFonts.outfit(color: AppTheme.textPrimary, fontSize: 11)),
                                        );
                                      }).toList(),
                                      onChanged: (val) {
                                        if (val != null) {
                                          setState(() {
                                            p['name'] = val['name'];
                                            p['role'] = val['role'];
                                            p['ipl_team'] = val['team'];
                                          });
                                        }
                                      },
                                    ),
                                  ),
                                ),
                              ],
                            ],
                          ),
                        );
                      }),
                    ],
                  );
                }).toList(),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: () => Navigator.pop(context, false), 
                  child: Text('Cancel', style: GoogleFonts.outfit(color: AppTheme.red, fontWeight: FontWeight.bold))
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: _isValid ? () {
                    widget.squads.clear();
                    widget.squads.addAll(_editableSquads);
                    widget.budgets.clear();
                    widget.budgets.addAll(_editableBudgets);
                    Navigator.pop(context, true);
                  } : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.green,
                    disabledBackgroundColor: AppTheme.textMuted.withValues(alpha: 0.2),
                    foregroundColor: Colors.white,
                  ),
                  child: Text('Confirm Import', style: GoogleFonts.outfit(fontWeight: FontWeight.bold)),
                ),
              ],
            )
          ],
        ),
      ),
    );
  }
}
