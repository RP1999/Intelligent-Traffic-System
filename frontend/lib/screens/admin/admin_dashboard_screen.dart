import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/admin/admin_sidebar.dart';
import '../../widgets/admin/stat_card.dart';
import '../../widgets/admin/live_video_feed.dart';
import '../../widgets/admin/traffic_light_panel.dart';
import '../../core/network/api_client.dart';
import '../../core/network/api_endpoints.dart';

class AdminDashboardScreen extends StatefulWidget {
  const AdminDashboardScreen({super.key});

  @override
  State<AdminDashboardScreen> createState() => _AdminDashboardScreenState();
}

class _AdminDashboardScreenState extends State<AdminDashboardScreen> {
  int _selectedIndex = 0;
  Map<String, dynamic>? _stats;
  bool _isLoading = true;
  
  final ApiClient _apiClient = ApiClient();

  @override
  void initState() {
    super.initState();
    _loadStats();
  }

  /// Handle unauthorized access - redirect to login
  void _handleUnauthorized() {
    if (!mounted) return;
    Navigator.of(context).pushNamedAndRemoveUntil('/platform-router', (route) => false);
  }

  Future<void> _loadStats() async {
    if (!mounted) return;
    setState(() => _isLoading = true);
    
    try {
      final response = await _apiClient.get(ApiEndpoints.adminStats);
      if (!mounted) return;
      
      if (response.success && response.data != null) {
        setState(() {
          _stats = response.data;
          _isLoading = false;
        });
      } else {
        setState(() => _isLoading = false);
      }
    } on UnauthorizedException {
      _handleUnauthorized();
    } catch (e) {
      if (!mounted) return;
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          // Sidebar
          AdminSidebar(
            selectedIndex: _selectedIndex,
            onItemSelected: (index) {
              setState(() => _selectedIndex = index);
              _handleNavigation(index);
            },
          ),
          
          // Main content
          Expanded(
            child: Container(
              color: AppColors.background,
              child: _buildMainContent(),
            ),
          ),
        ],
      ),
    );
  }

  void _handleNavigation(int index) {
    switch (index) {
      case 0: // Dashboard - stay here
        break;
      case 1: // Zone Editor
        Navigator.of(context).pushReplacementNamed('/admin/zones');
        break;
      case 2: // Violations
        Navigator.of(context).pushReplacementNamed('/admin/violations');
        break;
      case 3: // Drivers
        Navigator.of(context).pushReplacementNamed('/admin/drivers');
        break;
      case 4: // Analytics
        Navigator.of(context).pushReplacementNamed('/admin/analytics');
        break;
      case 5: // Audit Logs
        Navigator.of(context).pushReplacementNamed('/admin/logs');
        break;
      case 6: // Settings
        Navigator.of(context).pushReplacementNamed('/admin/settings');
        break;
      case 7: // Logout
        _handleLogout();
        break;
    }
  }

  Future<void> _handleLogout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Confirm Logout'),
        content: const Text('Are you sure you want to logout?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.error,
            ),
            child: const Text('Logout'),
          ),
        ],
      ),
    );
