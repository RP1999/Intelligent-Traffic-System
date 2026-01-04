import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../providers/admin/drivers_provider.dart';
import '../../../models/driver.dart';
import '../../../widgets/admin/admin_sidebar.dart';
import '../../../widgets/common/empty_state_widget.dart';
import '../../../widgets/common/loading_widget.dart';
import 'driver_detail_screen.dart';

class DriversListScreen extends StatefulWidget {
  const DriversListScreen({super.key});

  @override
  State<DriversListScreen> createState() => _DriversListScreenState();
}

class _DriversListScreenState extends State<DriversListScreen> {
  final TextEditingController _searchController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DriversProvider>().loadDrivers(refresh: true);
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
      context.read<DriversProvider>().loadNextPage();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          // Sidebar
          AdminSidebar(
            selectedIndex: 3, // Drivers index
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
                  Expanded(child: _buildDriversGrid()),
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
        Navigator.of(context).pushReplacementNamed('/admin/violations');
        break;
      case 3:
        // Already here - Drivers
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
                'Driver Registry',
                style: AppTypography.h1.copyWith(fontSize: 28),
              ),
              const SizedBox(height: 4),
              Consumer<DriversProvider>(
                builder: (context, provider, _) {
                  return Text(
                    '${provider.total} registered drivers',
                    style: AppTypography.bodyMedium.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  );
                },
              ),
            ],
          ),
          const Spacer(),
          
          // Refresh button
          IconButton(
            onPressed: () {
              context.read<DriversProvider>().loadDrivers(refresh: true);
            },
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
          ),
        ],
      ),
    );
  }

  Widget _buildFilters() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        children: [
          // Search box
          Expanded(
            flex: 2,
            child: TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: 'Search by ID, phone, or name...',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchController.clear();
                          context.read<DriversProvider>().setSearchQuery('');
                        },
                      )
                    : null,
                filled: true,
                fillColor: AppColors.surfaceVariant,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              ),
              onChanged: (value) {
                context.read<DriversProvider>().setSearchQuery(value);
              },
            ),
          ),
          const SizedBox(width: 16),
          
          // Sort dropdown
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(
              color: AppColors.surfaceVariant,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Consumer<DriversProvider>(
              builder: (context, provider, _) {
                return DropdownButtonHideUnderline(
                  child: DropdownButton<String>(
                    value: provider.sortBy,
                    hint: const Text('Sort By'),
                    dropdownColor: AppColors.surface,
                    items: const [
                      DropdownMenuItem(value: 'current_score', child: Text('Score (Low to High)')),
                      DropdownMenuItem(value: 'total_violations', child: Text('Total Violations')),
                      DropdownMenuItem(value: 'total_fines', child: Text('Total Fines')),
                    ],
                    onChanged: (value) {
                      if (value != null) {
                        provider.setSorting(value, order: 'asc');
                      }
                    },
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDriversGrid() {
    return Consumer<DriversProvider>(
      builder: (context, provider, _) {
        if (provider.state == LoadingState.loading && provider.drivers.isEmpty) {
          return const LoadingWidget(message: 'Loading drivers...');
        }

        if (provider.state == LoadingState.error && provider.drivers.isEmpty) {
          return EmptyStateWidget(
            icon: Icons.error_outline,
            title: 'Error Loading Drivers',
            message: provider.errorMessage ?? 'An unknown error occurred',
            actionLabel: 'Retry',
            onAction: () => provider.loadDrivers(refresh: true),
          );
        }

        if (provider.drivers.isEmpty) {
          return const EmptyStateWidget(
            icon: Icons.people_outline,
            title: 'No Drivers Found',
            message: 'No registered drivers in the system yet.',
          );
        }

        return Padding(
          padding: const EdgeInsets.all(24),
          child: GridView.builder(
            controller: _scrollController,
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 3,
              mainAxisSpacing: 16,
              crossAxisSpacing: 16,
              childAspectRatio: 1.4,
            ),
            itemCount: provider.drivers.length + (provider.hasMore ? 1 : 0),
            itemBuilder: (context, index) {
              if (index >= provider.drivers.length) {
                return const Center(
                  child: CircularProgressIndicator(color: AppColors.primary),
                );
              }
              
              return _buildDriverCard(provider.drivers[index]);
            },
          ),
        );
      },
    );
  }

  Widget _buildDriverCard(Driver driver) {
    return InkWell(
      onTap: () => _openDriverDetail(driver),
      borderRadius: BorderRadius.circular(16),
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: _getRiskColor(driver.riskLevel).withOpacity(0.3),
            width: 2,
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.1),
              blurRadius: 10,
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header with score gauge
              Row(
                children: [
                  // Score circle
                  _buildScoreCircle(driver.currentScore, driver.riskLevel),
                  const SizedBox(width: 16),
                  
                  // Driver ID
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          driver.name ?? driver.driverId,
                          style: AppTypography.h4,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          driver.phone ?? driver.driverId,
                          style: AppTypography.bodySmall.copyWith(
                            color: AppColors.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                  
                  // Risk badge
                  _buildRiskBadge(driver.riskLevel),
                ],
              ),
              
              const Spacer(),
              
              // Stats row
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.surfaceVariant,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _buildStatItem(
                      icon: Icons.warning_amber,
                      value: driver.totalViolations.toString(),
                      label: 'Violations',
                    ),
                    Container(
                      width: 1,
                      height: 30,
                      color: AppColors.border,
                    ),
                    _buildStatItem(
                      icon: Icons.attach_money,
                      value: '\$${driver.totalFines.toStringAsFixed(0)}',
                      label: 'Total Fines',
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildScoreCircle(int score, String riskLevel) {
    final color = _getRiskColor(riskLevel);
    
    return Container(
      width: 60,
      height: 60,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            color.withOpacity(0.8),
            color.withOpacity(0.4),
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: color.withOpacity(0.4),
            blurRadius: 12,
            spreadRadius: 2,
          ),
        ],
      ),
      child: Center(
        child: Text(
          score.toString(),
          style: AppTypography.h3.copyWith(
            color: Colors.white,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }

  Widget _buildRiskBadge(String riskLevel) {
    final color = _getRiskColor(riskLevel);
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.5)),
      ),
      child: Text(
        riskLevel.toUpperCase(),
        style: AppTypography.labelSmall.copyWith(
          color: color,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildStatItem({
    required IconData icon,
    required String value,
    required String label,
  }) {
    return Column(
      children: [
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16, color: AppColors.textSecondary),
            const SizedBox(width: 4),
            Text(
              value,
              style: AppTypography.labelLarge.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: AppTypography.labelSmall.copyWith(
            color: AppColors.textSecondary,
          ),
        ),
      ],
    );
  }

  Color _getRiskColor(String riskLevel) {
    switch (riskLevel.toLowerCase()) {
      case 'excellent':
        return AppColors.success;
      case 'good':
        return AppColors.riskLow;
      case 'fair':
        return AppColors.warning;
      case 'poor':
        return AppColors.riskHigh;
      case 'critical':
        return AppColors.error;
      default:
        return AppColors.textSecondary;
    }
  }

  void _openDriverDetail(Driver driver) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => DriverDetailScreen(driverId: driver.driverId),
      ),
    );
  }
}
