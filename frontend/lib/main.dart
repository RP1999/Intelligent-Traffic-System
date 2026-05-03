import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import 'core/theme/app_theme.dart';
import 'core/services/notification_service.dart';
import 'providers/auth_provider.dart';
import 'providers/admin/violations_provider.dart';
import 'providers/admin/drivers_provider.dart';
import 'providers/admin/analytics_provider.dart';
import 'providers/admin/iot_junction_provider.dart';
import 'providers/driver/driver_home_provider.dart';
import 'providers/driver/driver_violations_provider.dart';
import 'providers/driver/driver_fines_provider.dart';
import 'screens/screens.dart';
import 'models/fine.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Firebase (mobile only — web requires FirebaseOptions)
  if (!kIsWeb) {
    try {
      await Firebase.initializeApp();
      // Register background message handler
      FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
    } catch (e) {
      debugPrint('[Main] Firebase init error (running without FCM): $e');
    }
  }

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
        ChangeNotifierProvider(create: (_) => IotJunctionProvider()),
        ChangeNotifierProvider(create: (_) => DriverHomeProvider()),
        ChangeNotifierProvider(create: (_) => DriverViolationsProvider()),
        ChangeNotifierProvider(create: (_) => DriverFinesProvider()),
      ],
      child: MaterialApp(
        title: 'Traffic Control System',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.darkTheme,
        initialRoute: '/',
        routes: _buildRoutes(),
        onGenerateRoute: _onGenerateRoute,
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
      '/admin/risk': (context) => const RiskAnalyticsScreen(),
      '/admin/settings': (context) => const AdminSettingsScreen(),
      '/admin/iot-junction': (context) => const IotJunctionScreen(),
      
      // Driver routes
      '/driver/home': (context) => const DriverShellScreen(),
      '/driver/violations': (context) => const DriverShellScreen(),
      '/driver/fines': (context) => const DriverShellScreen(),
      '/driver/profile': (context) => const DriverShellScreen(),
    };
  }

  /// Handle routes that require arguments (e.g. payment with Fine object)
  static Route<dynamic>? _onGenerateRoute(RouteSettings settings) {
    if (settings.name == '/driver/payment') {
      final fine = settings.arguments as Fine?;
      if (fine != null) {
        return MaterialPageRoute(
          builder: (_) => PaymentScreen(fine: fine),
          settings: settings,
        );
      }
    }
    return null;
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
