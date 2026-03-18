import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import 'theme/app_theme.dart';
import 'services/api_service.dart';
import 'providers/auth_provider.dart';
import 'screens/landing_screen.dart';
import 'screens/room_entry_screen.dart';
import 'screens/team_claim_screen.dart';
import 'screens/auction_dashboard.dart';
import 'screens/auth_screen.dart';

void main() {
  final apiService = ApiService();
  
  runApp(
    MultiProvider(
      providers: [
        Provider<ApiService>.value(value: apiService),
        ChangeNotifierProvider<AuthProvider>(
          create: (_) => AuthProvider(apiService),
        ),
      ],
      child: const CricketAuctionApp(),
    ),
  );
}

final GlobalKey<NavigatorState> _rootNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'root');

GoRouter _buildRouter(AuthProvider authProvider) {
  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    refreshListenable: authProvider,
    initialLocation: '/',
    redirect: (context, state) {
      final isLoggedIn = authProvider.isAuthenticated;
      final isLoggingIn = state.matchedLocation == '/auth';
      
      // Still loading from SharedPreferences
      if (authProvider.isLoading) return null;

      if (!isLoggedIn && !isLoggingIn) {
        return '/auth';
      }
      
      if (isLoggedIn && isLoggingIn) {
        return '/';
      }
      
      return null;
    },
    routes: [
      GoRoute(
        path: '/auth',
        builder: (context, state) => const AuthScreen(),
      ),
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
}

class CricketAuctionApp extends StatelessWidget {
  const CricketAuctionApp({super.key});

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final router = _buildRouter(authProvider);
    
    return MaterialApp.router(
      title: 'Cricket Auction Platform',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme.copyWith(
        textTheme: GoogleFonts.outfitTextTheme(
          AppTheme.darkTheme.textTheme,
        ),
      ),
      routerConfig: router,
    );
  }
}
