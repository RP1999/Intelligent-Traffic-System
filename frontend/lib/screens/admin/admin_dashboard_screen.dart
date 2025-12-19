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
    
    if (confirmed == true && mounted) {
      await context.read<AuthProvider>().logout();
      Navigator.of(context).pushReplacementNamed('/');
    }
  }

  Widget _buildMainContent() {
    return CustomScrollView(
      slivers: [
        // App Bar
        SliverToBoxAdapter(
          child: _buildHeader(),
        ),
        
        // Stats Cards
        SliverToBoxAdapter(
          child: _buildStatsSection(),
        ),
        
        // Main Grid
        SliverToBoxAdapter(
          child: _buildMainGrid(),
        ),
      ],
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(24),
      child: Row(
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Command Center',
                style: AppTypography.h1.copyWith(fontSize: 32),
              ),
              const SizedBox(height: 4),
              Text(
                'Real-time traffic monitoring and control',
                style: AppTypography.bodyMedium.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
          const Spacer(),
          
          // Refresh button
          IconButton(
            onPressed: _loadStats,
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
          ),
          const SizedBox(width: 16),
          
          // Emergency button
          _buildEmergencyButton(),
        ],
      ),
    );
  }

  Widget _buildEmergencyButton() {
    return Container(
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFFFF4444), Color(0xFFCC0000)],
        ),
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.red.withOpacity(0.4),
            blurRadius: 12,
            spreadRadius: 2,
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _handleEmergency,
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            child: Row(
              children: [
                const Icon(Icons.warning_amber_rounded, color: Colors.white),
                const SizedBox(width: 8),
                Text(
                  'EMERGENCY',
                  style: AppTypography.buttonMedium.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _handleEmergency() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: Row(
          children: [
            Icon(Icons.warning, color: AppColors.error),
            const SizedBox(width: 12),
            const Text('Emergency Override'),
          ],
        ),
        content: const Text(
          'This will override all traffic signals and switch to emergency mode. '
          'All intersections will display flashing yellow.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.of(context).pop();
              _activateEmergency();
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.error,
            ),
            child: const Text('Activate Emergency'),
          ),
        ],
      ),
    );
  }

  void _activateEmergency() async {
    try {
      // Show loading indicator
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Row(
            children: [
              SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white,
                ),
              ),
              SizedBox(width: 12),
              Text('Activating emergency mode...'),
            ],
          ),
          backgroundColor: AppColors.warning,
          behavior: SnackBarBehavior.floating,
          duration: const Duration(seconds: 2),
        ),
      );

      // Call API to trigger emergency mode
      final response = await _apiClient.post(ApiEndpoints.emergencyTrigger);
      
      if (response.success) {
        ScaffoldMessenger.of(context).hideCurrentSnackBar();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('🚨 Emergency mode ACTIVATED - All signals set to emergency'),
            backgroundColor: AppColors.error,
            behavior: SnackBarBehavior.floating,
            duration: const Duration(seconds: 5),
          ),
        );
      } else {
        throw Exception(response.error ?? 'Unknown error');
      }
    } catch (e) {
      ScaffoldMessenger.of(context).hideCurrentSnackBar();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to activate emergency: $e'),
          backgroundColor: AppColors.error,
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  Widget _buildStatsSection() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        children: [
          Expanded(
            child: StatCard(
              title: 'Active Zones',
              value: _stats?['active_zones']?.toString() ?? '0',
              icon: Icons.location_on,
              color: AppColors.primary,
              isLoading: _isLoading,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: StatCard(
              title: 'Violations Today',
              value: _stats?['total_violations_today']?.toString() ?? '0',
              icon: Icons.report_problem,
              color: AppColors.error,
              isLoading: _isLoading,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: StatCard(
              title: 'Registered Drivers',
              value: _stats?['total_drivers']?.toString() ?? '0',
              icon: Icons.people,
              color: AppColors.info,
              isLoading: _isLoading,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: StatCard(
              title: 'Pending Fines',
              value: 'Rs. ${(_stats?['pending_fines'] ?? 0).toStringAsFixed(0)}',
              icon: Icons.attach_money,
              color: AppColors.warning,
              isLoading: _isLoading,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMainGrid() {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Live Video Feed
          Expanded(
            flex: 3,
            child: LiveVideoFeed(
              onZoneEditorPressed: () {
                Navigator.of(context).pushReplacementNamed('/admin/zones');
              },
            ),
          ),
          const SizedBox(width: 24),
          
          // Right panel
          Expanded(
            flex: 1,
            child: Column(
              children: [
                // Traffic Light Panel
