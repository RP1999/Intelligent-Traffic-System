import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/theme/app_theme.dart';
import 'providers/auth_provider.dart';
import 'providers/admin/violations_provider.dart';
import 'providers/admin/drivers_provider.dart';
import 'providers/admin/analytics_provider.dart';
import 'screens/screens.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const TrafficControlApp());
}

class TrafficControlApp extends StatelessWidget {
  const TrafficControlApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => ViolationsProvider()),
        ChangeNotifierProvider(create: (_) => DriversProvider()),
        ChangeNotifierProvider(create: (_) => AnalyticsProvider()),
      ],
      child: MaterialApp(
        title: 'Traffic Control System',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.darkTheme,
        initialRoute: '/',
        routes: _buildRoutes(),
      ),
    );
  }

  Map<String, WidgetBuilder> _buildRoutes() {
    return {
      '/': (context) => const SplashScreen(),
      '/platform-router': (context) => const PlatformRouter(),
      
      // Auth routes
      '/admin/login': (context) => const AdminLoginScreen(),
      '/driver/login': (context) => const DriverLoginScreen(),
      '/driver/register': (context) => const DriverRegisterScreen(),
      
      // Admin routes
      '/admin/dashboard': (context) => const AdminDashboardScreen(),
      '/admin/zones': (context) => const ZoneEditorScreen(),
      '/admin/logs': (context) => const AuditLogScreen(),
      '/admin/violations': (context) => const ViolationsListScreen(),
      '/admin/drivers': (context) => const DriversListScreen(),
      '/admin/analytics': (context) => const AnalyticsScreen(),
      '/admin/settings': (context) => const _PlaceholderScreen(title: 'Settings'),
      
      // Driver routes (placeholders for now)
      '/driver/home': (context) => const _PlaceholderScreen(title: 'Driver Home'),
      '/driver/violations': (context) => const _PlaceholderScreen(title: 'My Violations'),
      '/driver/fines': (context) => const _PlaceholderScreen(title: 'My Fines'),
      '/driver/profile': (context) => const _PlaceholderScreen(title: 'Profile'),
    };
  }
}

/// Placeholder screen for routes not yet implemented
class _PlaceholderScreen extends StatelessWidget {
  final String title;

  const _PlaceholderScreen({required this.title});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await context.read<AuthProvider>().logout();
              if (context.mounted) {
                Navigator.of(context).pushReplacementNamed('/platform-router');
              }
            },
          ),
        ],
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.construction,
              size: 80,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(height: 24),
            Text(
              title,
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Coming in next sprint...',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Colors.grey,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
