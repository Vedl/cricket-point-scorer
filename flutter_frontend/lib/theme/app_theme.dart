import 'package:flutter/material.dart';

/// Premium dark theme for the Cricket Auction Platform.
/// Inspired by the best fantasy-sports apps (FPL, Dream11).
class AppTheme {
  // ── Core Palette ──
  static const Color bgDark       = Color(0xFF050A18);
  static const Color bgCard       = Color(0xFF0D1326);
  static const Color bgCardHover  = Color(0xFF141C38);
  static const Color surface      = Color(0xFF131A30);
  static const Color surfaceLight = Color(0xFF1A2342);

  // Accents
  static const Color gold        = Color(0xFFF5C518);
  static const Color goldMuted   = Color(0xFFBFA023);
  static const Color goldLight   = Color(0xFFFFF0B3);
  static const Color accent      = Color(0xFF3B82F6);
  static const Color accentLight = Color(0xFF60A5FA);
  static const Color cyan        = Color(0xFF06B6D4);
  static const Color green       = Color(0xFF10B981);
  static const Color greenLight  = Color(0xFF34D399);
  static const Color red         = Color(0xFFEF4444);
  static const Color redLight    = Color(0xFFF87171);
  static const Color purple      = Color(0xFF8B5CF6);
  static const Color orange      = Color(0xFFF97316);
  static const Color pink        = Color(0xFFEC4899);

  // Text
  static const Color textPrimary   = Color(0xFFF1F5F9);
  static const Color textSecondary = Color(0xFF94A3B8);
  static const Color textMuted     = Color(0xFF64748B);
  static const Color textDim       = Color(0xFF475569);

  // Border & Surface
  static const Color border     = Color(0xFF1E293B);
  static const Color borderGlow = Color(0x33F5C518);

  // Legacy aliases
  static const Color accentBlue = accent;
  static const Color cardDark   = bgCard;

  // ── IPL Team Colors ──
  static const Map<String, Color> iplColors = {
    'CSK':  Color(0xFFFFCC00),
    'MI':   Color(0xFF004BA0),
    'RCB':  Color(0xFFD4213D),
    'KKR':  Color(0xFF3B215D),
    'SRH':  Color(0xFFF26522),
    'DC':   Color(0xFF00468B),
    'PBKS': Color(0xFFDD1F2D),
    'RR':   Color(0xFFEA1A85),
    'GT':   Color(0xFF1C3C6B),
    'LSG':  Color(0xFF004B8D),
  };

  static Color getIplTeamColor(String code) =>
      iplColors[code.toUpperCase()] ?? accent;

  // ── Gradients ──
  static const LinearGradient bgGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF050A18), Color(0xFF0A1128), Color(0xFF0D1530)],
  );

  static const LinearGradient goldGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFFF5C518), Color(0xFFE8A317)],
  );

  static const LinearGradient accentGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF3B82F6), Color(0xFF2563EB)],
  );

  static const LinearGradient cyanGradient = LinearGradient(
    colors: [Color(0xFF06B6D4), Color(0xFF0891B2)],
  );

  static const LinearGradient greenGradient = LinearGradient(
    colors: [Color(0xFF10B981), Color(0xFF059669)],
  );

  static const LinearGradient purpleGradient = LinearGradient(
    colors: [Color(0xFF8B5CF6), Color(0xFF7C3AED)],
  );

  static const LinearGradient heroGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [Color(0xFF0A1628), Color(0xFF050A18)],
  );

  // ── Decorations ──
  static BoxDecoration glassmorphism({
    Color? borderColor,
    double borderRadius = 16,
    double opacity = 0.6,
  }) {
    return BoxDecoration(
      color: bgCard.withValues(alpha: opacity),
      borderRadius: BorderRadius.circular(borderRadius),
      border: Border.all(
        color: borderColor ?? Colors.white.withValues(alpha: 0.06),
      ),
    );
  }

  static BoxDecoration glowCard({
    required Color glowColor,
    double borderRadius = 16,
  }) {
    return BoxDecoration(
      color: bgCard,
      borderRadius: BorderRadius.circular(borderRadius),
      border: Border.all(color: glowColor.withValues(alpha: 0.25)),
      boxShadow: [
        BoxShadow(
          color: glowColor.withValues(alpha: 0.08),
          blurRadius: 20,
          spreadRadius: 0,
        ),
      ],
    );
  }

  static BoxDecoration premiumCard({double borderRadius = 16}) {
    return BoxDecoration(
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          bgCard,
          bgCard.withValues(alpha: 0.95),
        ],
      ),
      borderRadius: BorderRadius.circular(borderRadius),
      border: Border.all(color: Colors.white.withValues(alpha: 0.05)),
      boxShadow: [
        BoxShadow(
          color: Colors.black.withValues(alpha: 0.3),
          blurRadius: 12,
          offset: const Offset(0, 4),
        ),
      ],
    );
  }

  /// Convenience getter for default glassmorphism decoration.
  static BoxDecoration get glassmorphismDecoration => glassmorphism();

  // ── Spacing Tokens ──
  static const double spacingXs = 4;
  static const double spacingSm = 8;
  static const double spacingMd = 16;
  static const double spacingLg = 24;
  static const double spacingXl = 32;
  static const double spacingXxl = 48;

  // ── Border Radii ──
  static const double radiusSm = 8;
  static const double radiusMd = 12;
  static const double radiusLg = 16;
  static const double radiusXl = 20;
  static const double radiusFull = 999;

  // ── Role Colors ──
  static Color getRoleColor(String role) {
    final r = role.toLowerCase();
    if (r.contains('wk') || r.contains('keeper')) return cyan;
    if (r.contains('bat')) return accent;
    if (r.contains('all')) return purple;
    if (r.contains('bowl')) return green;
    return textSecondary;
  }

  static String getRoleShort(String role) {
    final r = role.toLowerCase();
    if (r.contains('wk') || r.contains('keeper')) return 'WK';
    if (r.contains('bat')) return 'BAT';
    if (r.contains('all')) return 'AR';
    if (r.contains('bowl')) return 'BWL';
    return role;
  }

  // ── Theme Data ──
  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: bgDark,
      colorScheme: const ColorScheme.dark(
        primary: gold,
        secondary: accent,
        surface: bgCard,
        error: red,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.w700,
          color: textPrimary,
          letterSpacing: -0.3,
        ),
      ),
      cardTheme: CardThemeData(
        color: bgCard,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusLg),
          side: BorderSide(color: Colors.white.withValues(alpha: 0.05)),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: gold,
          foregroundColor: bgDark,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusMd),
          ),
          textStyle: const TextStyle(
            fontWeight: FontWeight.w700,
            fontSize: 14,
            letterSpacing: 0.3,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textPrimary,
          side: BorderSide(color: Colors.white.withValues(alpha: 0.12)),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusMd),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.06)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: const BorderSide(color: accent, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: const BorderSide(color: red, width: 1),
        ),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        hintStyle: const TextStyle(color: textMuted, fontSize: 14),
        labelStyle: const TextStyle(color: textSecondary, fontSize: 14),
      ),
      tabBarTheme: TabBarThemeData(
        labelColor: gold,
        unselectedLabelColor: textMuted,
        indicatorColor: gold,
        indicatorSize: TabBarIndicatorSize.label,
        labelStyle: const TextStyle(
          fontWeight: FontWeight.w600,
          fontSize: 13,
        ),
        unselectedLabelStyle: const TextStyle(
          fontWeight: FontWeight.w500,
          fontSize: 13,
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: surface,
        labelStyle: const TextStyle(fontSize: 12, color: textPrimary),
        side: BorderSide(color: Colors.white.withValues(alpha: 0.08)),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusSm),
        ),
      ),
      dividerTheme: DividerThemeData(
        color: Colors.white.withValues(alpha: 0.04),
        thickness: 1,
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: surfaceLight,
        contentTextStyle: const TextStyle(color: textPrimary),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusMd),
        ),
        behavior: SnackBarBehavior.floating,
      ),
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: bgCard,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
      ),
    );
  }
}
