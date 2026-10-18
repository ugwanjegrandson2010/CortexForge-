/// CortexForge theme — a calm, low-chrome Material 3 palette.
///
/// Colours mirror the web client's dark theme so the two surfaces read as one
/// product: deep slate background, a single blue accent for action, green for
/// progress. The design rules come from the research dossiers (minimal chrome,
/// stable spatial mapping, no decorative motion during encoding).
library;

import 'package:flutter/material.dart';

class CfColors {
  static const bg = Color(0xFF0E1116);
  static const surface = Color(0xFF151A21);
  static const surfaceAlt = Color(0xFF1B222B);
  static const border = Color(0xFF2A323D);
  static const text = Color(0xFFE6EDF3);
  static const textDim = Color(0xFF8B98A5);
  static const accent = Color(0xFF4C8DFF);
  static const good = Color(0xFF3FB950);
  static const warn = Color(0xFFD29922);
  static const bad = Color(0xFFF85149);
}

class CfTheme {
  static ThemeData dark() {
    final base = ThemeData.dark(useMaterial3: true);
    return base.copyWith(
      scaffoldBackgroundColor: CfColors.bg,
      colorScheme: base.colorScheme.copyWith(
        primary: CfColors.accent,
        secondary: CfColors.good,
        surface: CfColors.surface,
        error: CfColors.bad,
        onPrimary: Colors.white,
        onSurface: CfColors.text,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: CfColors.bg,
        foregroundColor: CfColors.text,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: CfColors.text,
          fontSize: 20,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.2,
        ),
      ),
      cardTheme: CardThemeData(
        color: CfColors.surface,
        elevation: 0,
        margin: const EdgeInsets.symmetric(vertical: 6),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: const BorderSide(color: CfColors.border),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: CfColors.surfaceAlt,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: CfColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: CfColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: CfColors.accent, width: 1.5),
        ),
        labelStyle: const TextStyle(color: CfColors.textDim),
        hintStyle: const TextStyle(color: CfColors.textDim),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: CfColors.accent,
          foregroundColor: Colors.white,
          minimumSize: const Size.fromHeight(48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          textStyle: const TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: CfColors.text,
          minimumSize: const Size.fromHeight(48),
          side: const BorderSide(color: CfColors.border),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(foregroundColor: CfColors.accent),
      ),
      dividerTheme: const DividerThemeData(color: CfColors.border, space: 1),
      listTileTheme: const ListTileThemeData(
        iconColor: CfColors.textDim,
        textColor: CfColors.text,
      ),
      progressIndicatorTheme:
          const ProgressIndicatorThemeData(color: CfColors.accent),
      snackBarTheme: const SnackBarThemeData(
        backgroundColor: CfColors.surfaceAlt,
        contentTextStyle: TextStyle(color: CfColors.text),
        behavior: SnackBarBehavior.floating,
      ),
      textTheme: base.textTheme.apply(
        bodyColor: CfColors.text,
        displayColor: CfColors.text,
      ),
    );
  }
}
