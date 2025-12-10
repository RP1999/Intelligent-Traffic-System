import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../providers/admin/drivers_provider.dart';
import '../../../models/driver.dart';
import '../../../widgets/common/loading_widget.dart';

class DriverDetailScreen extends StatefulWidget {
  final String driverId;

  const DriverDetailScreen({
    super.key,
    required this.driverId,
  });

  @override
  State<DriverDetailScreen> createState() => _DriverDetailScreenState();
}

class _DriverDetailScreenState extends State<DriverDetailScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DriversProvider>().loadDriverDetail(widget.driverId);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Driver Profile'),
        backgroundColor: AppColors.surface,
      ),
      body: Consumer<DriversProvider>(
        builder: (context, provider, _) {
          if (provider.detailState == LoadingState.loading) {
            return const LoadingWidget(message: 'Loading driver details...');
          }

          if (provider.detailState == LoadingState.error) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.error_outline, size: 64, color: AppColors.error),
                  const SizedBox(height: 16),
                  Text(
                    provider.errorMessage ?? 'Failed to load driver',
                    style: AppTypography.bodyLarge,
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton(
                    onPressed: () => provider.loadDriverDetail(widget.driverId),
                    child: const Text('Retry'),
                  ),
                ],
              ),
            );
          }

          final driver = provider.selectedDriver;
          if (driver == null) {
            return const Center(child: Text('No driver data'));
          }

          return SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Left side - Profile Card
                Expanded(
                  flex: 2,
                  child: Column(
                    children: [
                      _buildProfileCard(driver),
                      const SizedBox(height: 24),
                      _buildScoreCard(driver),
                    ],
                  ),
                ),
                const SizedBox(width: 24),
                
                // Right side - Violation Timeline
                Expanded(
                  flex: 3,
                  child: _buildViolationTimeline(driver),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildProfileCard(Driver driver) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 10,
          ),
        ],
      ),
      child: Column(
        children: [
          // Header with avatar
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  _getRiskColor(driver.riskLevel),
                  _getRiskColor(driver.riskLevel).withOpacity(0.6),
                ],
              ),
              borderRadius: const BorderRadius.vertical(
                top: Radius.circular(16),
              ),
            ),
            child: Column(
              children: [
                Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: Colors.white,
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.2),
                        blurRadius: 10,
                      ),
                    ],
                  ),
                  child: const Icon(
                    Icons.person,
                    size: 40,
                    color: AppColors.surfaceVariant,
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  driver.name ?? 'Unknown Driver',
                  style: AppTypography.h3.copyWith(color: Colors.white),
                ),
                const SizedBox(height: 4),
                Text(
                  driver.driverId,
                  style: AppTypography.bodyMedium.copyWith(
