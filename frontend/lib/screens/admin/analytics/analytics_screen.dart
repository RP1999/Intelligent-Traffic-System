import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:fl_chart/fl_chart.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../providers/admin/analytics_provider.dart';
import '../../../widgets/admin/admin_sidebar.dart';
import '../../../widgets/common/loading_widget.dart';

class AnalyticsScreen extends StatefulWidget {
  const AnalyticsScreen({super.key});

  @override
  State<AnalyticsScreen> createState() => _AnalyticsScreenState();
}

class _AnalyticsScreenState extends State<AnalyticsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AnalyticsProvider>().loadAllAnalytics();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          // Sidebar
          AdminSidebar(
            selectedIndex: 4, // Analytics
            onItemSelected: (index) => _handleNavigation(index),
          ),
          
          // Main content
          Expanded(
            child: Container(
              color: AppColors.background,
              child: CustomScrollView(
                slivers: [
                  SliverToBoxAdapter(child: _buildHeader()),
                  SliverToBoxAdapter(child: _buildStatsCards()),
                  SliverToBoxAdapter(child: _buildChartsRow()),
                  SliverToBoxAdapter(child: _buildHotspotsSection()),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _handleNavigation(int index) {
    switch (index) {
      case 0:
