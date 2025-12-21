import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../providers/admin/violations_provider.dart';
import '../../../models/violation.dart';
import '../../../widgets/admin/admin_sidebar.dart';
import '../../../widgets/common/empty_state_widget.dart';
import '../../../widgets/common/loading_widget.dart';
import 'violation_detail_screen.dart';

class ViolationsListScreen extends StatefulWidget {
  const ViolationsListScreen({super.key});

  @override
  State<ViolationsListScreen> createState() => _ViolationsListScreenState();
}

class _ViolationsListScreenState extends State<ViolationsListScreen> {
  final TextEditingController _searchController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  String? _selectedStatus;
  String? _selectedType;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ViolationsProvider>().loadViolations(refresh: true);
    });
    
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >= 
        _scrollController.position.maxScrollExtent - 200) {
      context.read<ViolationsProvider>().loadNextPage();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          // Sidebar
          AdminSidebar(
            selectedIndex: 2, // Violations index
            onItemSelected: (index) => _handleNavigation(index),
          ),
          
          // Main content
          Expanded(
            child: Container(
              color: AppColors.background,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildHeader(),
                  _buildFilters(),
                  Expanded(child: _buildViolationsTable()),
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
        Navigator.of(context).pushReplacementNamed('/admin/dashboard');
        break;
      case 1:
        Navigator.of(context).pushReplacementNamed('/admin/zones');
        break;
      case 2:
        // Already here
        break;
      case 3:
        Navigator.of(context).pushReplacementNamed('/admin/drivers');
        break;
      case 4:
        Navigator.of(context).pushReplacementNamed('/admin/analytics');
        break;
      case 5:
        Navigator.of(context).pushReplacementNamed('/admin/logs');
        break;
      case 6:
        Navigator.of(context).pushReplacementNamed('/admin/settings');
        break;
    }
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
                'Violation Management',
                style: AppTypography.h1.copyWith(fontSize: 28),
              ),
              const SizedBox(height: 4),
              Consumer<ViolationsProvider>(
                builder: (context, provider, _) {
                  return Text(
                    '${provider.total} total violations',
                    style: AppTypography.bodyMedium.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  );
                },
              ),
