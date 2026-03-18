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

class CricketAuctionApp extends StatefulWidget {
  const CricketAuctionApp({super.key});

  @override
  State<CricketAuctionApp> createState() => _CricketAuctionAppState();
}

class _CricketAuctionAppState extends State<CricketAuctionApp> {
  GoRouter? _router;

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    
    if (authProvider.isLoading) {
      return const MaterialApp(
        debugShowCheckedModeBanner: false,
        home: SplashPage(),
      );
    }

    // Initialize router once after loading
    _router ??= _buildRouter(authProvider);
    
    return MaterialApp.router(
      title: 'Cricket Auction Platform',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme.copyWith(
        textTheme: GoogleFonts.outfitTextTheme(
          AppTheme.darkTheme.textTheme,
        ),
      ),
      routerConfig: _router!,
    );
  }
}

class SplashPage extends StatelessWidget {
  const SplashPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bgDark,
      body: Container(
        decoration: const BoxDecoration(gradient: AppTheme.bgGradient),
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  gradient: AppTheme.goldGradient,
                  borderRadius: BorderRadius.circular(18),
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.gold.withValues(alpha: 0.25),
                      blurRadius: 24,
                      offset: const Offset(0, 8),
                    ),
                  ],
                ),
                child: const Center(
                  child: Text('🏏', style: TextStyle(fontSize: 36)),
                ),
              ),
              const SizedBox(height: 24),
              const CircularProgressIndicator(color: AppTheme.accent),
              const SizedBox(height: 16),
              Text(
                'Loading...',
                style: GoogleFonts.outfit(
                  color: AppTheme.textMuted,
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
