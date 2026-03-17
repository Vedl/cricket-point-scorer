import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:file_picker/file_picker.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import 'dart:async';
import 'dart:convert' show utf8;

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
      if (mounted) setState(() { _state = data; _loading = false; _error = null; });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  void _showSnack(String msg, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg),
      backgroundColor: isError ? Colors.red.shade700 : Colors.green.shade700,
      behavior: SnackBarBehavior.floating,
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bgDark,
      appBar: AppBar(
        backgroundColor: AppTheme.bgDark,
        elevation: 0,
        title: Row(children: [
          const Text('🏏 ', style: TextStyle(fontSize: 22)),
          Text('Room: ${widget.roomCode}',
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
          const SizedBox(width: 8),
          IconButton(
            icon: const Icon(Icons.copy, size: 18),
            tooltip: 'Copy Room Code',
            onPressed: () {
              Clipboard.setData(ClipboardData(text: widget.roomCode));
              _showSnack('Room code copied!');
            },
          ),
          const Spacer(),
          if (widget.isAdmin)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                gradient: AppTheme.accentGradient,
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Text('👑 ADMIN', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
            ),
        ]),
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          indicatorColor: AppTheme.accentBlue,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.grey,
          tabs: const [
            Tab(icon: Icon(Icons.dashboard), text: 'Overview'),
            Tab(icon: Icon(Icons.gavel), text: 'Bidding'),
            Tab(icon: Icon(Icons.swap_horiz), text: 'Trading'),
            Tab(icon: Icon(Icons.groups), text: 'Squads'),
            Tab(icon: Icon(Icons.calendar_month), text: 'Schedule'),
            Tab(icon: Icon(Icons.emoji_events), text: 'Standings'),
            Tab(icon: Icon(Icons.calculate), text: 'Calculator'),
          ],
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('Error: $_error', style: const TextStyle(color: Colors.red)))
              : TabBarView(
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
    );
  }

  // ═══════════════════════════════════════════════════
  // TAB 1: OVERVIEW
  // ═══════════════════════════════════════════════════
  Widget _buildOverviewTab() {
    final participants = List<Map<String, dynamic>>.from(_state?['participants'] ?? []);
    final phase = _state?['game_phase'] ?? 'Unknown';
    final gw = _state?['current_gameweek'] ?? 1;
    final locked = _state?['squads_locked'] ?? false;

    return RefreshIndicator(
      onRefresh: _fetchState,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Status Card
          _glassCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                _statusChip(phase),
                const Spacer(),
                Text('GW $gw', style: const TextStyle(color: Colors.white70, fontSize: 16, fontWeight: FontWeight.bold)),
                const SizedBox(width: 8),
                Icon(locked ? Icons.lock : Icons.lock_open,
                    color: locked ? Colors.red : Colors.green, size: 18),
              ]),
              const SizedBox(height: 12),
              Text('Admin: ${_state?['admin'] ?? 'N/A'}',
                  style: const TextStyle(color: Colors.white54, fontSize: 14)),
              Text('Tournament: ${_state?['tournament_type']?.toUpperCase() ?? 'N/A'}',
                  style: const TextStyle(color: Colors.white54, fontSize: 14)),
              Text('Participants: ${participants.length}',
                  style: const TextStyle(color: Colors.white54, fontSize: 14)),
              if (_state?['bidding_deadline'] != null)
                Text('Deadline: ${_state!['bidding_deadline']}',
                    style: TextStyle(color: Colors.amber.shade300, fontSize: 13)),
            ]),
          ),
          const SizedBox(height: 12),

          // Admin Controls
          if (widget.isAdmin) ...[
            _glassCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('⚙️ Admin Controls',
                    style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                Wrap(spacing: 8, runSpacing: 8, children: [
                  _adminBtn('🔒 Lock Squads', _lockSquads, locked ? Colors.grey : Colors.orange),
                  _adminBtn('⏭️ Advance GW', _advanceGW, Colors.blue),
                  _adminBtn('💰 100M Boost', _grantBoost, Colors.green),
                  _adminBtn('🎬 Start Auction', _startAuction, Colors.purple),
                  _adminBtn('📂 Upload CSV', _uploadCsv, Colors.teal),
                ]),
              ]),
            ),
            const SizedBox(height: 12),
          ],

          // Participants Overview
          const Text('Participants',
              style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          ...participants.map((p) => _glassCard(
                child: Row(children: [
                  CircleAvatar(
                    backgroundColor: AppTheme.accentBlue.withOpacity(0.3),
                    child: Text(p['name'][0].toUpperCase(),
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(p['name'], style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                      Text('Budget: ${p['budget']}M  |  Squad: ${p['squad_size']} players',
                          style: const TextStyle(color: Colors.white54, fontSize: 13)),
                    ]),
                  ),
                  if (p['eliminated'] == true)
                    const Chip(label: Text('OUT'), backgroundColor: Colors.red),
                ]),
              )),
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════════════
  // TAB 2: BIDDING
  // ═══════════════════════════════════════════════════
  Widget _buildBiddingTab() {
    final bids = List<Map<String, dynamic>>.from(_state?['active_bids'] ?? []);

    return RefreshIndicator(
      onRefresh: _fetchState,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Place New Bid
          _glassCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('🎯 Place a Bid',
                  style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              _BidForm(
                roomCode: widget.roomCode,
                participantName: widget.participantName,
                onBidPlaced: () { _fetchState(); _showSnack('Bid placed!'); },
                onError: (e) => _showSnack(e, isError: true),
              ),
            ]),
          ),
          const SizedBox(height: 16),

          // Active Bids
          Text('Active Bids (${bids.length})',
              style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          if (bids.isEmpty)
            _glassCard(child: const Center(
              child: Text('No active bids', style: TextStyle(color: Colors.white54)),
            ))
          else
            ...bids.map((b) => _glassCard(
                  child: Row(children: [
                    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(b['player'] ?? 'Unknown',
                          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
                      Text('by ${b['bidder']}  •  ${b['amount']}M',
                          style: TextStyle(color: Colors.amber.shade300, fontSize: 14)),
                      Text('Expires: ${b['expires']?.toString().substring(0, 16) ?? 'N/A'}',
                          style: const TextStyle(color: Colors.white38, fontSize: 12)),
                    ])),
                    if (b['bidder'] != widget.participantName)
                      ElevatedButton(
                        onPressed: () => _outbid(b),
                        style: ElevatedButton.styleFrom(backgroundColor: Colors.orange),
                        child: const Text('Outbid'),
                      ),
                  ]),
                )),
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════════════
  // TAB 3: TRADING
  // ═══════════════════════════════════════════════════
  Widget _buildTradingTab() {
    return _TradingTab(
      roomCode: widget.roomCode,
      participantName: widget.participantName,
      isAdmin: widget.isAdmin,
      state: _state,
      onRefresh: _fetchState,
      showSnack: _showSnack,
    );
  }

  // ═══════════════════════════════════════════════════
  // TAB 4: SQUADS
  // ═══════════════════════════════════════════════════
  Widget _buildSquadsTab() {
    final participants = List<Map<String, dynamic>>.from(_state?['participants'] ?? []);

    return RefreshIndicator(
      onRefresh: _fetchState,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ...participants.map((p) {
            final squad = List<Map<String, dynamic>>.from(p['squad'] ?? []);
            return _glassCard(
              child: ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: Row(children: [
                  Text(p['name'],
                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppTheme.accentBlue.withOpacity(0.3),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text('${squad.length} players  |  ${p['budget']}M',
                        style: const TextStyle(color: Colors.white70, fontSize: 12)),
                  ),
                ]),
                children: squad.isEmpty
                    ? [const Padding(
                        padding: EdgeInsets.all(8),
                        child: Text('No players yet', style: TextStyle(color: Colors.white38)),
                      )]
                    : squad.map((pl) => ListTile(
                        dense: true,
                        leading: _roleIcon(pl['role'] ?? ''),
                        title: Text(pl['name'] ?? '', style: const TextStyle(color: Colors.white)),
                        subtitle: Text('${pl['role'] ?? 'Unknown'}  •  ${pl['team'] ?? ''}',
                            style: const TextStyle(color: Colors.white38, fontSize: 12)),
                        trailing: Text('${pl['price'] ?? 0}M',
                            style: TextStyle(color: Colors.amber.shade300, fontWeight: FontWeight.bold)),
                        // Release button for own squad
                        onLongPress: p['name'] == widget.participantName
                            ? () => _releasePlayer(pl['name'])
                            : null,
                      )).toList(),
              ),
            );
          }),
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════════════
  // TAB 5: SCHEDULE
  // ═══════════════════════════════════════════════════
  Widget _buildScheduleTab() {
    return _ScheduleTab(roomCode: widget.roomCode);
  }

  // ═══════════════════════════════════════════════════
  // TAB 6: STANDINGS
  // ═══════════════════════════════════════════════════
  Widget _buildStandingsTab() {
    return _StandingsTab(roomCode: widget.roomCode);
  }

  // ═══════════════════════════════════════════════════
  // TAB 7: CALCULATOR
  // ═══════════════════════════════════════════════════
  Widget _buildCalculatorTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _glassCard(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('🏏 Fantasy Points Calculator',
                style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            const Text('Paste any Cricbuzz scorecard URL to instantly calculate fantasy points.',
                style: TextStyle(color: Colors.white54, fontSize: 14)),
            const SizedBox(height: 16),
            TextField(
              controller: _calcUrlController,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: 'https://www.cricbuzz.com/live-cricket-scorecard/...',
                hintStyle: const TextStyle(color: Colors.white30),
                filled: true,
                fillColor: Colors.white.withOpacity(0.05),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                prefixIcon: const Icon(Icons.link, color: Colors.white38),
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _calcLoading ? null : _calculatePoints,
                icon: _calcLoading
                    ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.calculate),
                label: Text(_calcLoading ? 'Calculating...' : 'Calculate Points'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.accentBlue,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
              ),
            ),
          ]),
        ),
        if (_calcResults != null) ...[
          const SizedBox(height: 16),
          // Top 3 Podium
          if (_calcResults!.length >= 3) _buildPodium(_calcResults!),
          const SizedBox(height: 12),
          _glassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Full Leaderboard',
                    style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                ..._calcResults!.asMap().entries.map((e) {
                  final i = e.key;
                  final p = e.value;
                  return ListTile(
                    dense: true,
                    leading: CircleAvatar(
                      radius: 14,
                      backgroundColor: i < 3 ? [Colors.amber, Colors.grey.shade400, Colors.brown.shade300][i] : Colors.white12,
                      child: Text('${i + 1}', style: const TextStyle(fontSize: 12, color: Colors.white)),
                    ),
                    title: Text(p['name'] ?? '', style: const TextStyle(color: Colors.white)),
                    subtitle: Text('${p['role'] ?? ''}  •  R:${p['runs'] ?? 0}  W:${p['wickets'] ?? 0}  C:${p['catches'] ?? 0}',
                        style: const TextStyle(color: Colors.white38, fontSize: 11)),
                    trailing: Text('${p['points']} pts',
                        style: TextStyle(color: Colors.amber.shade300, fontWeight: FontWeight.bold, fontSize: 15)),
                  );
                }),
              ],
            ),
          ),
        ],
      ],
    );
  }

  // ═══════════════════════════════════════════════════
  // HELPER WIDGETS
  // ═══════════════════════════════════════════════════
  Widget _glassCard({required Widget child}) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.glassmorphismDecoration,
      child: child,
    );
  }

  Widget _statusChip(String phase) {
    final colors = {
      'NotStarted': Colors.grey,
      'Bidding': Colors.orange,
      'Playing': Colors.green,
      'Completed': Colors.blue,
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      decoration: BoxDecoration(
        color: (colors[phase] ?? Colors.grey).withOpacity(0.3),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: colors[phase] ?? Colors.grey),
      ),
      child: Text(phase, style: TextStyle(color: colors[phase] ?? Colors.grey, fontSize: 13, fontWeight: FontWeight.bold)),
    );
  }

  Widget _adminBtn(String label, VoidCallback onTap, Color color) {
    return ElevatedButton(
      onPressed: onTap,
      style: ElevatedButton.styleFrom(backgroundColor: color.withOpacity(0.8), padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10)),
      child: Text(label, style: const TextStyle(fontSize: 13)),
    );
  }

  Widget _roleIcon(String role) {
    final r = role.toLowerCase();
    if (r.contains('wk') || r.contains('keeper')) return const Icon(Icons.sports_cricket, color: Colors.green, size: 20);
    if (r.contains('bowl')) return const Icon(Icons.sports_baseball, color: Colors.red, size: 20);
    if (r.contains('all')) return const Icon(Icons.star, color: Colors.purple, size: 20);
    return const Icon(Icons.sports_cricket, color: Colors.blue, size: 20);
  }

  Widget _buildPodium(List<dynamic> results) {
    final medals = ['🥇', '🥈', '🥉'];
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: List.generate(3, (i) {
        final p = results[i];
        return _glassCard(
          child: Column(children: [
            Text(medals[i], style: const TextStyle(fontSize: 28)),
            const SizedBox(height: 4),
            Text(p['name'] ?? '', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14)),
            Text('${p['points']} pts', style: TextStyle(color: Colors.amber.shade300, fontSize: 16, fontWeight: FontWeight.bold)),
            Text(p['role'] ?? '', style: const TextStyle(color: Colors.white38, fontSize: 11)),
          ]),
        );
      }),
    );
  }

  // ═══════════════════════════════════════════════════
  // ACTIONS
  // ═══════════════════════════════════════════════════
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
      final result = await api.advanceGameweek(roomCode: widget.roomCode, adminName: widget.participantName);
      _showSnack('Advanced to GW${result['gameweek']}');
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

  Future<void> _startAuction() async {
    final hoursCtrl = TextEditingController(text: '24');
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.cardDark,
        title: const Text('Start Auction', style: TextStyle(color: Colors.white)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Set bidding deadline (in hours):', style: TextStyle(color: Colors.white70)),
            const SizedBox(height: 12),
            TextField(
              controller: hoursCtrl,
              keyboardType: TextInputType.number,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                filled: true,
                fillColor: Colors.white.withOpacity(0.05),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                suffixText: 'hours',
                suffixStyle: const TextStyle(color: Colors.white54),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.purple),
            child: const Text('Start'),
          ),
        ],
      ),
    );

    if (confirm == true) {
      final hours = double.tryParse(hoursCtrl.text) ?? 24.0;
      try {
        final api = context.read<ApiService>();
        await api.startAuction(
          roomCode: widget.roomCode,
          adminName: widget.participantName,
          deadlineHours: hours,
        );
        _showSnack('Auction started! Deadline in $hours hours.');
        _fetchState();
      } catch (e) { _showSnack(e.toString(), isError: true); }
    }
  }

  Future<void> _uploadCsv() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['csv'],
        withData: true,
      );
      if (result != null && result.files.single.bytes != null) {
        final csvText = utf8.decode(result.files.single.bytes!);
        final api = context.read<ApiService>();
        await api.importCsv(
          roomCode: widget.roomCode,
          adminName: widget.participantName,
          csvText: csvText,
        );
        _showSnack('CSV uploaded & parsed successfully!');
        _fetchState();
      }
    } catch (e) {
      _showSnack('Error uploading CSV: $e', isError: true);
    }
  }

  Future<void> _outbid(Map<String, dynamic> bid) async {
    final current = bid['amount'] as int;
    int step = current >= 100 ? 10 : (current >= 50 ? 5 : 1);
    int newAmount = current + step;
    try {
      final api = context.read<ApiService>();
      await api.placeBid(
        roomCode: widget.roomCode,
        participantName: widget.participantName,
        playerName: bid['player'],
        amount: newAmount,
      );
      _showSnack('Outbid! New bid: ${newAmount}M');
      _fetchState();
    } catch (e) { _showSnack(e.toString(), isError: true); }
  }

  Future<void> _releasePlayer(String playerName) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.cardDark,
        title: const Text('Release Player', style: TextStyle(color: Colors.white)),
        content: Text('Release $playerName?', style: const TextStyle(color: Colors.white70)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Release'),
          ),
        ],
      ),
    );
    if (confirm == true) {
      try {
        final api = context.read<ApiService>();
        final result = await api.releasePlayer(
          roomCode: widget.roomCode,
          participantName: widget.participantName,
          playerName: playerName,
        );
        _showSnack('Released $playerName (Refund: ${result['refund']}M)');
        _fetchState();
      } catch (e) { _showSnack(e.toString(), isError: true); }
    }
  }

  Future<void> _calculatePoints() async {
    final url = _calcUrlController.text.trim();
    if (url.isEmpty) { _showSnack('Please enter a URL', isError: true); return; }
    setState(() { _calcLoading = true; _calcResults = null; });
    try {
      final api = context.read<ApiService>();
      final result = await api.calculatePoints(url);
      setState(() { _calcResults = result['players']; _calcLoading = false; });
    } catch (e) {
      setState(() { _calcLoading = false; });
      _showSnack(e.toString(), isError: true);
    }
  }
}

// ═══════════════════════════════════════════════════════
// BID FORM WIDGET
// ═══════════════════════════════════════════════════════
class _BidForm extends StatefulWidget {
  final String roomCode;
  final String participantName;
  final VoidCallback onBidPlaced;
  final Function(String) onError;

  const _BidForm({
    required this.roomCode,
    required this.participantName,
    required this.onBidPlaced,
    required this.onError,
  });

  @override
  State<_BidForm> createState() => _BidFormState();
}

class _BidFormState extends State<_BidForm> {
  final _playerCtrl = TextEditingController();
  final _amountCtrl = TextEditingController();

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      TextField(
        controller: _playerCtrl,
        style: const TextStyle(color: Colors.white),
        decoration: InputDecoration(
          hintText: 'Player name',
          hintStyle: const TextStyle(color: Colors.white30),
          filled: true,
          fillColor: Colors.white.withOpacity(0.05),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
        ),
      ),
      const SizedBox(height: 8),
      TextField(
        controller: _amountCtrl,
        keyboardType: TextInputType.number,
        style: const TextStyle(color: Colors.white),
        decoration: InputDecoration(
          hintText: 'Bid amount (M)',
          hintStyle: const TextStyle(color: Colors.white30),
          filled: true,
          fillColor: Colors.white.withOpacity(0.05),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
        ),
      ),
      const SizedBox(height: 10),
      SizedBox(
        width: double.infinity,
        child: ElevatedButton(
          onPressed: _placeBid,
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.orange,
            padding: const EdgeInsets.symmetric(vertical: 12),
          ),
          child: const Text('Place Bid'),
        ),
      ),
    ]);
  }

  Future<void> _placeBid() async {
    final player = _playerCtrl.text.trim();
    final amount = int.tryParse(_amountCtrl.text.trim());
    if (player.isEmpty || amount == null) {
      widget.onError('Enter player name and amount');
      return;
    }
    try {
      await context.read<ApiService>().placeBid(
        roomCode: widget.roomCode,
        participantName: widget.participantName,
        playerName: player,
        amount: amount,
      );
      _playerCtrl.clear();
      _amountCtrl.clear();
      widget.onBidPlaced();
    } catch (e) {
      widget.onError(e.toString());
    }
  }
}

// ═══════════════════════════════════════════════════════
// TRADING TAB WIDGET
// ═══════════════════════════════════════════════════════
class _TradingTab extends StatefulWidget {
  final String roomCode;
  final String participantName;
  final bool isAdmin;
  final Map<String, dynamic>? state;
  final VoidCallback onRefresh;
  final Function(String, {bool isError}) showSnack;

  const _TradingTab({
    required this.roomCode,
    required this.participantName,
    required this.isAdmin,
    required this.state,
    required this.onRefresh,
    required this.showSnack,
  });

  @override
  State<_TradingTab> createState() => _TradingTabState();
}

class _TradingTabState extends State<_TradingTab> {
  List<dynamic> _pendingTrades = [];
  List<dynamic> _tradeLog = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadTrades();
  }

  Future<void> _loadTrades() async {
    try {
      final api = context.read<ApiService>();
      final data = await api.getTradeLog(widget.roomCode);
      if (mounted) {
        setState(() {
          _pendingTrades = data['pending_trades'] ?? [];
          _tradeLog = data['trade_log'] ?? [];
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());

    final incoming = _pendingTrades.where((t) => t['to'] == widget.participantName && t['status'] == 'pending').toList();
    final outgoing = _pendingTrades.where((t) => t['from'] == widget.participantName).toList();
    final pendingAdmin = _pendingTrades.where((t) => t['status'] == 'pending_admin').toList();

    return RefreshIndicator(
      onRefresh: _loadTrades,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Incoming Proposals
          _sectionTitle('📥 Incoming Proposals (${incoming.length})'),
          if (incoming.isEmpty)
            _infoCard('No incoming proposals')
          else
            ...incoming.map((t) => _tradeCard(t, showActions: true)),

          const SizedBox(height: 16),

          // Outgoing Proposals
          _sectionTitle('📤 Outgoing Proposals (${outgoing.length})'),
          if (outgoing.isEmpty)
            _infoCard('No outgoing proposals')
          else
            ...outgoing.map((t) => _tradeCard(t)),

          // Admin Approvals
          if (widget.isAdmin) ...[
            const SizedBox(height: 16),
            _sectionTitle('👑 Pending Admin Approval (${pendingAdmin.length})'),
            if (pendingAdmin.isEmpty)
              _infoCard('No trades pending approval')
            else
              ...pendingAdmin.map((t) => _tradeCard(t, showAdminActions: true)),
          ],

          const SizedBox(height: 16),

          // Trade Log
          _sectionTitle('📜 Transaction Log (${_tradeLog.length})'),
          if (_tradeLog.isEmpty)
            _infoCard('No transactions yet')
          else
            ..._tradeLog.reversed.take(20).map((log) => Container(
                  margin: const EdgeInsets.only(bottom: 4),
                  padding: const EdgeInsets.all(10),
                  decoration: AppTheme.glassmorphismDecoration,
                  child: Text('${log['time']}  •  ${log['msg']}',
                      style: const TextStyle(color: Colors.white70, fontSize: 12)),
                )),
        ],
      ),
    );
  }

  Widget _sectionTitle(String text) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(text, style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
      );

  Widget _infoCard(String text) => Container(
        padding: const EdgeInsets.all(16),
        decoration: AppTheme.glassmorphismDecoration,
        child: Center(child: Text(text, style: const TextStyle(color: Colors.white38))),
      );

  Widget _tradeCard(Map<String, dynamic> t, {bool showActions = false, bool showAdminActions = false}) {
    final type = t['type'] ?? '';
    final player = t['player'] ?? t['give_player'] ?? '';
    final getPlayer = t['get_player'] ?? '';
    final price = t['price'] ?? 0;
    final status = t['status'] ?? 'pending';

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: AppTheme.glassmorphismDecoration,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: Colors.purple.withOpacity(0.3),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(type, style: const TextStyle(color: Colors.purpleAccent, fontSize: 11, fontWeight: FontWeight.bold)),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: status == 'pending_admin' ? Colors.amber.withOpacity(0.3) : Colors.blue.withOpacity(0.3),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(status.toUpperCase(), style: TextStyle(
              color: status == 'pending_admin' ? Colors.amber : Colors.blue,
              fontSize: 10, fontWeight: FontWeight.bold)),
          ),
        ]),
        const SizedBox(height: 8),
        Text('${t['from']} → ${t['to']}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        Text('Player: $player${getPlayer.isNotEmpty ? " ↔ $getPlayer" : ""}  •  ${price}M',
            style: const TextStyle(color: Colors.white54, fontSize: 13)),
        if (showActions) ...[
          const SizedBox(height: 8),
          Row(children: [
            ElevatedButton(
              onPressed: () => _respondTrade(t['id'], 'accept'),
              style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
              child: const Text('Accept'),
            ),
            const SizedBox(width: 8),
            ElevatedButton(
              onPressed: () => _respondTrade(t['id'], 'reject'),
              style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
              child: const Text('Reject'),
            ),
          ]),
        ],
        if (showAdminActions) ...[
          const SizedBox(height: 8),
          Row(children: [
            ElevatedButton(
              onPressed: () => _adminAction(t['id'], 'approve'),
              style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
              child: const Text('✅ Approve'),
            ),
            const SizedBox(width: 8),
            ElevatedButton(
              onPressed: () => _adminAction(t['id'], 'reject'),
              style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
              child: const Text('❌ Reject'),
            ),
          ]),
        ],
      ]),
    );
  }

  Future<void> _respondTrade(String tradeId, String action) async {
    try {
      await context.read<ApiService>().respondTrade(
        roomCode: widget.roomCode,
        tradeId: tradeId,
        participantName: widget.participantName,
        action: action,
      );
      widget.showSnack('Trade ${action}ed!');
      _loadTrades();
      widget.onRefresh();
    } catch (e) {
      widget.showSnack(e.toString(), isError: true);
    }
  }

  Future<void> _adminAction(String tradeId, String action) async {
    try {
      await context.read<ApiService>().adminTradeAction(
        roomCode: widget.roomCode,
        tradeId: tradeId,
        adminName: widget.participantName,
        action: action,
      );
      widget.showSnack('Trade ${action}d!');
      _loadTrades();
      widget.onRefresh();
    } catch (e) {
      widget.showSnack(e.toString(), isError: true);
    }
  }
}

// ═══════════════════════════════════════════════════════
// SCHEDULE TAB WIDGET
// ═══════════════════════════════════════════════════════
class _ScheduleTab extends StatefulWidget {
  final String roomCode;
  const _ScheduleTab({required this.roomCode});

  @override
  State<_ScheduleTab> createState() => _ScheduleTabState();
}

class _ScheduleTabState extends State<_ScheduleTab> {
  Map<String, dynamic>? _schedule;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadSchedule();
  }

  Future<void> _loadSchedule() async {
    try {
      final api = context.read<ApiService>();
      final data = await api.getSchedule(widget.roomCode);
      if (mounted) setState(() { _schedule = data; _loading = false; });
    } catch (e) {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_schedule == null) {
      return const Center(child: Text('No schedule available', style: TextStyle(color: Colors.white54)));
    }

    final gameweeksMap = _schedule!['gameweeks'] as Map<String, dynamic>? ?? {};
    final gameweeks = gameweeksMap.values.toList();
    
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: gameweeks.length,
      itemBuilder: (ctx, i) {
        final gw = gameweeks[i];
        final matches = gw['matches'] as List<dynamic>? ?? [];
        return Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(16),
          decoration: AppTheme.glassmorphismDecoration,
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('GW${gw['gameweek']}  •  ${gw['dates'] ?? ''}',
                style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
            const Divider(color: Colors.white24),
            ...matches.map((m) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(children: [
                    Text('${m['team1'] ?? ''}', style: const TextStyle(color: Colors.white, fontSize: 13)),
                    const Text(' vs ', style: TextStyle(color: Colors.amber, fontSize: 13, fontWeight: FontWeight.bold)),
                    Text('${m['team2'] ?? ''}', style: const TextStyle(color: Colors.white, fontSize: 13)),
                    const Spacer(),
                    Text('${m['date'] ?? ''}', style: const TextStyle(color: Colors.white38, fontSize: 11)),
                  ]),
                )),
          ]),
        );
      },
    );
  }
}

// ═══════════════════════════════════════════════════════
// STANDINGS TAB WIDGET
// ═══════════════════════════════════════════════════════
class _StandingsTab extends StatefulWidget {
  final String roomCode;
  const _StandingsTab({required this.roomCode});

  @override
  State<_StandingsTab> createState() => _StandingsTabState();
}

class _StandingsTabState extends State<_StandingsTab> {
  Map<String, dynamic>? _standings;
  bool _loading = true;
  int? _selectedGW;

  @override
  void initState() {
    super.initState();
    _loadStandings();
  }

  Future<void> _loadStandings() async {
    setState(() => _loading = true);
    try {
      final api = context.read<ApiService>();
      final data = await api.getStandings(widget.roomCode, gameweek: _selectedGW);
      if (mounted) setState(() { _standings = data; _loading = false; });
    } catch (e) {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      // GW selector
      Padding(
        padding: const EdgeInsets.all(12),
        child: Row(children: [
          const Text('View: ', style: TextStyle(color: Colors.white, fontSize: 14)),
          ChoiceChip(
            label: const Text('Overall'),
            selected: _selectedGW == null,
            onSelected: (_) => setState(() { _selectedGW = null; _loadStandings(); }),
            selectedColor: AppTheme.accentBlue,
            labelStyle: TextStyle(color: _selectedGW == null ? Colors.white : Colors.white54),
          ),
          const SizedBox(width: 8),
          ...(_standings?['total_gameweeks'] as List<dynamic>? ?? []).map((gw) {
            final gwInt = int.tryParse(gw.toString());
            return Padding(
              padding: const EdgeInsets.only(right: 4),
              child: ChoiceChip(
                label: Text('GW$gw'),
                selected: _selectedGW == gwInt,
                onSelected: (_) => setState(() { _selectedGW = gwInt; _loadStandings(); }),
                selectedColor: AppTheme.accentBlue,
                labelStyle: TextStyle(color: _selectedGW == gwInt ? Colors.white : Colors.white54),
              ),
            );
          }),
        ]),
      ),
      Expanded(
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _buildStandingsList(),
      ),
    ]);
  }

  Widget _buildStandingsList() {
    final standings = List<Map<String, dynamic>>.from(_standings?['standings'] ?? []);
    if (standings.isEmpty) {
      return const Center(child: Text('No standings data yet', style: TextStyle(color: Colors.white54)));
    }

    final medals = ['🥇', '🥈', '🥉'];
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      itemCount: standings.length,
      itemBuilder: (ctx, i) {
        final s = standings[i];
        return Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(16),
          decoration: AppTheme.glassmorphismDecoration,
          child: Row(children: [
            Text(i < 3 ? medals[i] : '#${s['rank']}',
                style: TextStyle(
                  fontSize: i < 3 ? 24 : 16,
                  color: i < 3 ? Colors.amber : Colors.white54,
                  fontWeight: FontWeight.bold,
                )),
            const SizedBox(width: 16),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(s['participant'] ?? '', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
                if (s['best_11'] != null)
                  Text('Best 11: ${(s['best_11'] as List).take(3).join(', ')}...',
                      style: const TextStyle(color: Colors.white38, fontSize: 11)),
              ]),
            ),
            Text('${(s['points'] as num).toStringAsFixed(0)} pts',
                style: TextStyle(color: Colors.amber.shade300, fontWeight: FontWeight.bold, fontSize: 18)),
          ]),
        );
      },
    );
  }
}
