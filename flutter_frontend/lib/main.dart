import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import 'theme/app_theme.dart';
import 'services/api_service.dart';
import 'screens/landing_screen.dart';
import 'screens/room_entry_screen.dart';
import 'screens/team_claim_screen.dart';
import 'screens/auction_dashboard.dart';

void main() {
  runApp(
    Provider<ApiService>(
      create: (_) => ApiService(),
      child: const CricketAuctionApp(),
    ),
  );
}

final GoRouter _router = GoRouter(
  routes: [
    GoRoute(
      path: '/',
      builder: (context, state) => const LandingScreen(),
    ),
    GoRoute(
      path: '/room/:tournamentId',
      builder: (context, state) => RoomEntryScreen(
        tournamentId: state.pathParameters['tournamentId']!,
      ),
    ),
    GoRoute(
      path: '/claim-team/:roomCode/:participantName',
      builder: (context, state) => TeamClaimScreen(
        roomCode: state.pathParameters['roomCode']!,
        participantName: state.pathParameters['participantName']!,
      ),
    ),
    GoRoute(
      path: '/auction/:roomCode',
      builder: (context, state) => AuctionDashboard(
        roomCode: state.pathParameters['roomCode']!,
        participantName:
            state.uri.queryParameters['name'] ?? '',
        isAdmin: state.uri.queryParameters['admin'] == 'true',
      ),
    ),
  ],
);

class CricketAuctionApp extends StatelessWidget {
  const CricketAuctionApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Cricket Auction Platform',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme.copyWith(
        textTheme: GoogleFonts.outfitTextTheme(
          AppTheme.darkTheme.textTheme,
        ),
      ),
      routerConfig: _router,
    );
  }
}
