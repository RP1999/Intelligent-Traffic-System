import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'auth/admin_login_screen.dart';
import 'auth/driver_login_screen.dart';

/// Routes to the appropriate login screen based on platform
/// - Web: Admin Login (Control Center)
/// - Mobile: Driver Login (Driver App)
class PlatformRouter extends StatelessWidget {
  const PlatformRouter({super.key});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        // Check if we're on web or a wide screen (desktop-like)
        final isWideScreen = constraints.maxWidth > 800;
        
        // On web, default to admin login
        // On mobile, default to driver login
        if (kIsWeb || isWideScreen) {
          return AdminLoginScreen();
        } else {
          return DriverLoginScreen();
        }
      },
    );
  }
}
