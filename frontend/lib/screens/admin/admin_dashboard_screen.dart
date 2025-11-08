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
      
