import 'package:flutter/material.dart';

/// Premium dark theme for the Cricket Auction Platform.
class AppTheme {
  // ── Colors ──
  static const Color bgDark = Color(0xFF0A0E1A);
  static const Color bgCard = Color(0xFF141828);
  static const Color bgCardHover = Color(0xFF1A2040);
  static const Color surface = Color(0xFF1E2344);
  static const Color gold = Color(0xFFFFD700);
  static const Color goldMuted = Color(0xFFB8960F);
  static const Color accent = Color(0xFF00B4D8);
  static const Color accentLight = Color(0xFF48CAE4);
  static const Color green = Color(0xFF22C55E);
  static const Color red = Color(0xFFEF4444);
  static const Color textPrimary = Color(0xFFE2E8F0);
  static const Color textSecondary = Color(0xFF94A3B8);
  static const Color textMuted = Color(0xFF64748B);
  static const Color border = Color(0xFF1E293B);
  static const Color borderGlow = Color(0x33FFD700);
  static const Color accentBlue = Color(0xFF00B4D8);
  static const Color cardDark = Color(0xFF141828);

  /// Convenience getter for default glassmorphism decoration.
  static BoxDecoration get glassmorphismDecoration => glassmorphism();

  // IPL team colors
  static const Map<String, Color> iplColors = {
    'CSK': Color(0xFFFFCC00),
    'MI': Color(0xFF004BA0),
    'RCB': Color(0xFFD4213D),
    'KKR': Color(0xFF3B215D),
    'SRH': Color(0xFFF26522),
    'DC': Color(0xFF00468B),
    'PBKS': Color(0xFFDD1F2D),
    'RR': Color(0xFFEA1A85),
    'GT': Color(0xFF1C3C6B),
    'LSG': Color(0xFF004B8D),
  };

  static Color getIplTeamColor(String code) =>
      iplColors[code.toUpperCase()] ?? accent;

  // ── Gradients ──
  static const LinearGradient bgGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [bgDark, Color(0xFF0F1629), Color(0xFF131A2E)],
  );

  static const LinearGradient goldGradient = LinearGradient(
    colors: [Color(0xFFFFD700), Color(0xFFFFA500)],
  );

  static const LinearGradient accentGradient = LinearGradient(
    colors: [Color(0xFF00B4D8), Color(0xFF0077B6)],
  );

  // ── Decorations ──
  static BoxDecoration glassmorphism({
    Color? borderColor,
    double borderRadius = 20,
  }) {
    return BoxDecoration(
      color: bgCard.withValues(alpha: 0.7),
      borderRadius: BorderRadius.circular(borderRadius),
      border: Border.all(
        color: borderColor ?? Colors.white.withValues(alpha: 0.08),
      ),
    );
  }

  static BoxDecoration glowCard({
    required Color glowColor,
    double borderRadius = 20,
  }) {
    return BoxDecoration(
      color: bgCard,
      borderRadius: BorderRadius.circular(borderRadius),
      border: Border.all(color: glowColor.withValues(alpha: 0.3)),
      boxShadow: [
        BoxShadow(
          color: glowColor.withValues(alpha: 0.15),
          blurRadius: 24,
          spreadRadius: 0,
        ),
      ],
    );
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
        centerTitle: true,
        titleTextStyle: TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w700,
          color: textPrimary,
          letterSpacing: -0.5,
        ),
      ),
      cardTheme: CardThemeData(
        color: bgCard,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: Colors.white.withValues(alpha: 0.06)),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: gold,
          foregroundColor: bgDark,
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
          textStyle: const TextStyle(
            fontWeight: FontWeight.w700,
            fontSize: 15,
            letterSpacing: 0.5,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textPrimary,
          side: BorderSide(color: Colors.white.withValues(alpha: 0.15)),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.08)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: gold, width: 1.5),
        ),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
        hintStyle: const TextStyle(color: textMuted),
      ),
      dividerTheme: DividerThemeData(
        color: Colors.white.withValues(alpha: 0.06),
        thickness: 1,
      ),
    );
  }
}
