import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import '../theme/app_theme.dart';
import '../services/api_service.dart';

class RoomEntryScreen extends StatefulWidget {
  final String tournamentId;
  const RoomEntryScreen({super.key, required this.tournamentId});

  @override
  State<RoomEntryScreen> createState() => _RoomEntryScreenState();
}

class _RoomEntryScreenState extends State<RoomEntryScreen> {
  final _joinCodeController = TextEditingController();
  final _nameController = TextEditingController();
  bool _isCreating = false;
  bool _adminPlaying = true;
  bool _loading = false;
  String? _error;

  String get _tournamentLabel {
    switch (widget.tournamentId) {
      case 'ipl': return 'TATA IPL 2026';
      case 't20_wc': return 'T20 World Cup 2026';
      default: return widget.tournamentId.toUpperCase();
    }
  }

  @override
  void dispose() {
    _joinCodeController.dispose();
    _nameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isWide = MediaQuery.of(context).size.width > 700;

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppTheme.bgGradient),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 500),
                child: Column(
                  children: [
                    // Back button
                    Align(
                      alignment: Alignment.centerLeft,
                      child: IconButton(
                        onPressed: () => context.go('/'),
                        icon: const Icon(Icons.arrow_back_rounded),
                        color: AppTheme.textSecondary,
                      ),
                    ),
                    const SizedBox(height: 16),

                    // Title
                    Text(
                      _tournamentLabel,
                      style: GoogleFonts.outfit(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.gold,
                        letterSpacing: 2,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _isCreating ? 'Create a Room' : 'Join a Room',
                      style: GoogleFonts.outfit(
                        fontSize: isWide ? 36 : 28,
                        fontWeight: FontWeight.w800,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 32),

                    // Toggle tabs
                    Container(
                      padding: const EdgeInsets.all(4),
                      decoration: BoxDecoration(
                        color: AppTheme.surface,
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: Row(
                        children: [
                          _buildTab('Join Room', !_isCreating, () {
                            setState(() { _isCreating = false; _error = null; });
                          }),
                          _buildTab('Create Room', _isCreating, () {
                            setState(() { _isCreating = true; _error = null; });
                          }),
                        ],
                      ),
                    ),
                    const SizedBox(height: 32),

                    // Form
                    Container(
                      padding: const EdgeInsets.all(28),
                      decoration: AppTheme.glassmorphism(),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          // Name input
                          Text('Your Name',
                              style: GoogleFonts.inter(
                                  fontSize: 13, color: AppTheme.textSecondary)),
                          const SizedBox(height: 8),
                          TextField(
                            controller: _nameController,
                            style: GoogleFonts.inter(color: AppTheme.textPrimary),
                            decoration: const InputDecoration(
                              hintText: 'Enter your display name',
                              prefixIcon: Icon(Icons.person_rounded,
                                  color: AppTheme.textMuted),
                            ),
                          ),
                          const SizedBox(height: 20),

                          // Room code (join mode)
                          if (!_isCreating) ...[
                            Text('Room Code',
                                style: GoogleFonts.inter(
                                    fontSize: 13,
                                    color: AppTheme.textSecondary)),
                            const SizedBox(height: 8),
                            TextField(
                              controller: _joinCodeController,
                              style: GoogleFonts.outfit(
                                fontSize: 24,
                                fontWeight: FontWeight.w800,
                                color: AppTheme.gold,
                                letterSpacing: 6,
                              ),
                              textAlign: TextAlign.center,
                              textCapitalization: TextCapitalization.characters,
                              maxLength: 6,
                              decoration: InputDecoration(
                                hintText: 'ABC123',
                                hintStyle: GoogleFonts.outfit(
                                  fontSize: 24,
                                  fontWeight: FontWeight.w800,
                                  color: AppTheme.textMuted.withValues(alpha: 0.3),
                                  letterSpacing: 6,
                                ),
                                counterText: '',
                                prefixIcon: const Icon(Icons.tag_rounded,
                                    color: AppTheme.textMuted),
                              ),
                            ),
                          ],
                          if (_isCreating) ...[
                              const SizedBox(height: 16),
                              Container(
                                decoration: AppTheme.glassmorphismDecoration,
                                child: SwitchListTile(
                                  title: Text(
                                    'Participate with a Team',
                                    style: GoogleFonts.inter(
                                      color: AppTheme.textPrimary,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                  subtitle: Text(
                                    'If off, you will only be the Admin.',
                                    style: GoogleFonts.inter(
                                      color: AppTheme.textMuted,
                                      fontSize: 12,
                                    ),
                                  ),
                                  value: _adminPlaying,
                                  onChanged: (val) => setState(() => _adminPlaying = val),
                                  activeColor: AppTheme.accentBlue,
                                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                                ),
                              ),
                            ],

                          if (_error != null) ...[
                            const SizedBox(height: 16),
                            Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: AppTheme.red.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(
                                    color: AppTheme.red.withValues(alpha: 0.2)),
                              ),
                              child: Text(
                                _error!,
                                style: GoogleFonts.inter(
                                    fontSize: 13, color: AppTheme.red),
                                textAlign: TextAlign.center,
                              ),
                            ),
                          ],

                          const SizedBox(height: 24),

                          // Submit button
                          SizedBox(
                            height: 52,
                            child: ElevatedButton(
                              onPressed: _loading ? null : _handleSubmit,
                              child: _loading
                                  ? const SizedBox(
                                      width: 20,
                                      height: 20,
                                      child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          color: AppTheme.bgDark),
                                    )
                                  : Text(_isCreating
                                      ? 'Create Room'
                                      : 'Join Room'),
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
        ),
      ),
    );
  }

  Widget _buildTab(String label, bool active, VoidCallback onTap) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.symmetric(vertical: 12),
          decoration: BoxDecoration(
            color: active ? AppTheme.bgCard : Colors.transparent,
            borderRadius: BorderRadius.circular(11),
          ),
          child: Text(
            label,
            textAlign: TextAlign.center,
            style: GoogleFonts.outfit(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: active ? AppTheme.textPrimary : AppTheme.textMuted,
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _handleSubmit() async {
    final name = _nameController.text.trim();
    if (name.isEmpty) {
      setState(() => _error = 'Please enter your name');
      return;
    }

    setState(() { _loading = true; _error = null; });
    final api = context.read<ApiService>();

    try {
      if (_isCreating) {
        // ── CREATE ROOM ──
        final result = await api.createRoom(
          adminName: name,
          tournamentType: widget.tournamentId,
          adminPlaying: _adminPlaying,
        );
        final roomCode = result['room_code'] as String;
        if (mounted) {
          context.go('/auction/$roomCode?name=$name&admin=true');
        }
      } else {
        // ── JOIN ROOM ──
        final code = _joinCodeController.text.trim().toUpperCase();
        if (code.length != 6) {
          setState(() { _error = 'Room code must be 6 characters'; _loading = false; });
          return;
        }

        // First, check the room state to see if it's IPL (needs team claiming)
        final state = await api.getAuctionState(code);
        final tournamentType = state['tournament_type'] as String? ?? '';

        // Join the room
        await api.joinRoom(
          roomCode: code,
          participantName: name,
        );

        if (mounted) {
          final admin = state['admin'] as String? ?? '';
          if (tournamentType == 'ipl') {
            // IPL rooms need team claiming for non-admin
            if (admin != name) {
              context.go('/claim-team/$code/$name');
            } else {
              context.go('/auction/$code?name=$name&admin=true');
            }
          } else {
            context.go('/auction/$code?name=$name&admin=${admin == name}');
          }
        }
      }
    } on ApiException catch (e) {
      if (mounted) setState(() { _error = e.message; _loading = false; });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }
}
