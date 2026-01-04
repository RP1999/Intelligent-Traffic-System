import 'package:flutter/material.dart';

/// App color palette - Dark theme for Traffic Control Center
class AppColors {
  AppColors._();

  // ============== BACKGROUNDS ==============
  /// Main background - Very Dark Grey
  static const Color background = Color(0xFF121212);
  
  /// Card/Surface background - Dark Grey
  static const Color surface = Color(0xFF1E1E1E);
  
  /// Elevated surface - Slightly lighter
  static const Color surfaceVariant = Color(0xFF2D2D2D);
  
  /// Sidebar/Header background
  static const Color surfaceDark = Color(0xFF0D0D0D);

  // ============== PRIMARY ACCENT ==============
  /// Traffic Yellow - Primary brand color
  static const Color primary = Color(0xFFFFD700);
  
  /// Dark Gold - For pressed states
  static const Color primaryDark = Color(0xFFB8860B);
  
  /// Light Yellow - For hover states
  static const Color primaryLight = Color(0xFFFFE44D);
  
  /// Accent color - Secondary brand color
  static const Color accent = Color(0xFFE0A800);
  
  /// Surface Light - For shimmer and highlights
  static const Color surfaceLight = Color(0xFF3D3D3D);
  
  /// Muted text - For very subtle text
  static const Color textMuted = Color(0xFF4A4A4A);

  // ============== STATUS COLORS ==============
  /// Success/Safe - Green
  static const Color success = Color(0xFF00C853);
  
  /// Error/Danger - Red
  static const Color error = Color(0xFFFF4444);
  
  /// Warning - Orange
  static const Color warning = Color(0xFFFF9800);
  
  /// Info - Blue
  static const Color info = Color(0xFF2196F3);

  // ============== TEXT COLORS ==============
  /// Primary text - White
  static const Color textPrimary = Color(0xFFFFFFFF);
  
  /// Secondary text - Light Grey
  static const Color textSecondary = Color(0xFFB0B0B0);
  
  /// Disabled text - Dark Grey
  static const Color textDisabled = Color(0xFF666666);
  
  /// Hint text
  static const Color textHint = Color(0xFF888888);

  // ============== BORDER COLORS ==============
  /// Default border
  static const Color border = Color(0xFF3D3D3D);
  
  /// Focus border
  static const Color borderFocus = primary;
  
  /// Divider
  static const Color divider = Color(0xFF2D2D2D);

  // ============== TRAFFIC LIGHT COLORS ==============
  /// Traffic Red
  static const Color trafficRed = Color(0xFFFF0000);
  
  /// Traffic Yellow
  static const Color trafficYellow = Color(0xFFFFD700);
  
  /// Traffic Green
  static const Color trafficGreen = Color(0xFF00FF00);
  
  /// Traffic Light Off
  static const Color trafficOff = Color(0xFF333333);

  // ============== RISK LEVEL COLORS ==============
  /// Low Risk - Green
  static const Color riskLow = Color(0xFF00C853);
  
  /// Medium Risk - Orange
  static const Color riskMedium = Color(0xFFFF9800);
  
  /// High Risk - Deep Orange
  static const Color riskHigh = Color(0xFFFF5722);
  
  /// Critical Risk - Red
  static const Color riskCritical = Color(0xFFFF0000);

  // ============== SAFETY SCORE COLORS ==============
  /// Excellent (90-100)
  static const Color scoreExcellent = Color(0xFF00C853);
  
  /// Good (70-89)
  static const Color scoreGood = Color(0xFF4CAF50);
  
  /// Fair (50-69)
  static const Color scoreFair = Color(0xFFFF9800);
  
  /// Poor (30-49)
  static const Color scorePoor = Color(0xFFFF5722);
  
  /// Critical (0-29)
  static const Color scoreCritical = Color(0xFFFF0000);

  /// Get color based on safety score
  static Color getScoreColor(int score) {
    if (score >= 90) return scoreExcellent;
    if (score >= 70) return scoreGood;
    if (score >= 50) return scoreFair;
    if (score >= 30) return scorePoor;
    return scoreCritical;
  }

  /// Get color based on risk level string
  static Color getRiskColor(String level) {
    switch (level.toLowerCase()) {
      case 'low':
        return riskLow;
      case 'medium':
        return riskMedium;
      case 'high':
        return riskHigh;
      case 'critical':
        return riskCritical;
      default:
        return textSecondary;
    }
  }

  // ============== GRADIENTS ==============
  /// Primary gradient (yellow to gold)
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [primaryLight, primary, primaryDark],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  /// Background gradient
  static const LinearGradient backgroundGradient = LinearGradient(
    colors: [Color(0xFF1A1A2E), Color(0xFF121212)],
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
  );

  /// Card glow effect
  static List<BoxShadow> get cardGlow => [
    BoxShadow(
      color: primary.withOpacity(0.1),
      blurRadius: 20,
      spreadRadius: 0,
    ),
  ];

  /// Primary button glow
  static List<BoxShadow> get primaryGlow => [
    BoxShadow(
      color: primary.withOpacity(0.4),
      blurRadius: 20,
      spreadRadius: 0,
    ),
  ];

  /// Error glow (for emergency button)
  static List<BoxShadow> get errorGlow => [
    BoxShadow(
      color: error.withOpacity(0.5),
      blurRadius: 20,
      spreadRadius: 2,
    ),
  ];
}
