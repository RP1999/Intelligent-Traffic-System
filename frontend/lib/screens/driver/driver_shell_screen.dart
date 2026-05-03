import 'package:flutter/material.dart';
import '../../widgets/driver/driver_bottom_nav.dart';
import 'driver_home_screen.dart';
import 'driver_violations_screen.dart';
import 'driver_fines_screen.dart';
import 'driver_profile_screen.dart';

/// Shell screen that manages driver bottom navigation and tab switching.
/// All driver tabs share this scaffold; each tab keeps its state alive.
class DriverShellScreen extends StatefulWidget {
  const DriverShellScreen({super.key});

  @override
  State<DriverShellScreen> createState() => _DriverShellScreenState();
}

class _DriverShellScreenState extends State<DriverShellScreen> {
  int _currentIndex = 0;

  final List<Widget> _screens = const [
    DriverHomeScreen(),
    DriverViolationsScreen(),
    DriverFinesScreen(),
    DriverProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: DriverBottomNav(
        currentIndex: _currentIndex,
        onTap: (index) {
          setState(() => _currentIndex = index);
        },
      ),
    );
  }
}
