import 'dart:async';
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
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final provider = context.read<DriversProvider>();
      provider.resetFilters();
      provider.loadDrivers(refresh: true);
    });
    
    _scrollController.addListener(_onScroll);

    // Auto-refresh driver list every 15 seconds
    _pollTimer = Timer.periodic(const Duration(seconds: 15), (_) {
      if (mounted) {
        context.read<DriversProvider>().loadDrivers(refresh: true);
      }
    });
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
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
        Navigator.of(context).pushReplacementNamed('/admin/risk');
        break;
      case 7:
        Navigator.of(context).pushReplacementNamed('/admin/settings');
        break;
      case 8:
        Navigator.of(context).pushReplacementNamed('/admin/iot-junction');
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
          
          // Registered Only Toggle
          Consumer<DriversProvider>(
            builder: (context, provider, _) {
              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: AppColors.surfaceVariant,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: provider.registeredOnly 
                        ? AppColors.primary.withOpacity(0.5)
                        : AppColors.border,
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      provider.registeredOnly ? Icons.verified_user : Icons.people,
                      size: 18,
                      color: provider.registeredOnly ? AppColors.primary : AppColors.textSecondary,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      provider.registeredOnly ? 'Registered Only' : 'All Drivers',
                      style: AppTypography.bodySmall.copyWith(
                        color: provider.registeredOnly ? AppColors.primary : AppColors.textSecondary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Switch(
                      value: provider.registeredOnly,
                      onChanged: (value) => provider.setRegisteredOnly(value),
                      activeTrackColor: AppColors.primary.withOpacity(0.5),
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                  ],
                ),
              );
            },
          ),
          const SizedBox(width: 16),
          
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
    return Consumer<DriversProvider>(
      builder: (context, provider, _) {
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Row 1: Search + Sort
              Row(
                children: [
                  // Search box
                  Expanded(
                    flex: 2,
                    child: TextField(
                      controller: _searchController,
                      decoration: InputDecoration(
                        hintText: 'Search by plate, phone, or name...',
                        prefixIcon: const Icon(Icons.search),
                        suffixIcon: _searchController.text.isNotEmpty
                            ? IconButton(
                                icon: const Icon(Icons.clear),
                                onPressed: () {
                                  _searchController.clear();
                                  provider.setSearchQuery('');
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
                      onChanged: (value) => provider.setSearchQuery(value),
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
                    child: DropdownButtonHideUnderline(
                      child: DropdownButton<String>(
                        value: '${provider.sortBy}_${provider.sortOrder}',
                        dropdownColor: AppColors.surface,
                        items: const [
                          DropdownMenuItem(value: 'current_score_desc', child: Text('Score: High \u2192 Low')),
                          DropdownMenuItem(value: 'current_score_asc', child: Text('Score: Low \u2192 High')),
                          DropdownMenuItem(value: 'total_violations_desc', child: Text('Most Violations')),
                          DropdownMenuItem(value: 'total_violations_asc', child: Text('Fewest Violations')),
                          DropdownMenuItem(value: 'total_fines_desc', child: Text('Highest Fines')),
                          DropdownMenuItem(value: 'total_fines_asc', child: Text('Lowest Fines')),
                        ],
                        onChanged: (value) {
                          if (value != null) {
                            final parts = value.split('_');
                            final order = parts.removeLast();
                            final field = parts.join('_');
                            provider.setSorting(field, order: order);
                          }
                        },
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              // Row 2: Risk level filter chips
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    _buildRiskFilterChip(provider, 'all', 'All', AppColors.primary),
                    const SizedBox(width: 8),
                    _buildRiskFilterChip(provider, 'excellent', 'Excellent', AppColors.success),
                    const SizedBox(width: 8),
                    _buildRiskFilterChip(provider, 'good', 'Good', AppColors.riskLow),
                    const SizedBox(width: 8),
                    _buildRiskFilterChip(provider, 'fair', 'Fair', AppColors.warning),
                    const SizedBox(width: 8),
                    _buildRiskFilterChip(provider, 'poor', 'Poor', AppColors.riskHigh),
                    const SizedBox(width: 8),
                    _buildRiskFilterChip(provider, 'critical', 'Critical', AppColors.error),
                  ],
                ),
              ),
              const SizedBox(height: 8),
            ],
          ),
        );
      },
    );
  }

  Widget _buildRiskFilterChip(DriversProvider provider, String value, String label, Color color) {
    final isSelected = provider.riskFilter == value;
    return FilterChip(
      selected: isSelected,
      label: Text(label),
      labelStyle: TextStyle(
        color: isSelected ? Colors.white : color,
        fontWeight: FontWeight.w600,
        fontSize: 12,
      ),
      backgroundColor: color.withOpacity(0.1),
      selectedColor: color,
      checkmarkColor: Colors.white,
      side: BorderSide(color: color.withOpacity(isSelected ? 0 : 0.4)),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      onSelected: (_) => provider.setRiskFilter(value),
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
                  // Score circle with label
                  Column(
                    children: [
                      _buildScoreCircle(driver.currentScore, driver.riskLevel),
                      const SizedBox(height: 4),
                      Text(
                        'Safety',
                        style: AppTypography.caption.copyWith(
                          color: AppColors.textSecondary,
                          fontSize: 10,
                        ),
                      ),
                    ],
                  ),
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
                          driver.plateNumber ?? driver.driverId,
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
                      value: 'LKR ${driver.totalFines.toStringAsFixed(0)}',
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
