import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/config/app_config.dart';
import '../../../providers/admin/violations_provider.dart';
import '../../../models/violation.dart';
import '../../../widgets/common/loading_widget.dart';

class ViolationDetailScreen extends StatefulWidget {
  final String violationId;

  const ViolationDetailScreen({
    super.key,
    required this.violationId,
  });

  @override
  State<ViolationDetailScreen> createState() => _ViolationDetailScreenState();
}

class _ViolationDetailScreenState extends State<ViolationDetailScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ViolationsProvider>().loadViolationDetail(widget.violationId);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Violation Details'),
        backgroundColor: AppColors.surface,
        actions: [
          Consumer<ViolationsProvider>(
            builder: (context, provider, _) {
              if (provider.selectedViolation == null) return const SizedBox();
              return Row(
                children: [
                  TextButton.icon(
                    onPressed: () => _verifyViolation(provider.selectedViolation!),
                    icon: const Icon(Icons.check_circle, color: AppColors.success),
                    label: const Text('Verify', style: TextStyle(color: AppColors.success)),
                  ),
                  const SizedBox(width: 8),
                  TextButton.icon(
                    onPressed: () => _dismissViolation(provider.selectedViolation!),
                    icon: const Icon(Icons.cancel, color: AppColors.error),
                    label: const Text('Dismiss', style: TextStyle(color: AppColors.error)),
                  ),
                  const SizedBox(width: 16),
                ],
              );
            },
          ),
        ],
      ),
      body: Consumer<ViolationsProvider>(
        builder: (context, provider, _) {
          if (provider.detailState == LoadingState.loading) {
            return const LoadingWidget(message: 'Loading violation details...');
          }

          if (provider.detailState == LoadingState.error) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.error_outline, size: 64, color: AppColors.error),
                  const SizedBox(height: 16),
                  Text(
                    provider.errorMessage ?? 'Failed to load violation',
                    style: AppTypography.bodyLarge,
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton(
                    onPressed: () => provider.loadViolationDetail(widget.violationId),
                    child: const Text('Retry'),
                  ),
                ],
              ),
            );
          }

          final violation = provider.selectedViolation;
          if (violation == null) {
            return const Center(child: Text('No violation data'));
          }

          return SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Left side - Evidence Card
                Expanded(
                  flex: 3,
                  child: _buildEvidenceCard(violation),
                ),
                const SizedBox(width: 24),
                
                // Right side - Fine Breakdown
                Expanded(
                  flex: 2,
                  child: Column(
                    children: [
                      _buildFineBreakdownCard(violation),
                      const SizedBox(height: 24),
                      _buildViolationInfoCard(violation),
                    ],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildEvidenceCard(Violation violation) {
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
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Container(
            padding: const EdgeInsets.all(20),
            decoration: const BoxDecoration(
              border: Border(
                bottom: BorderSide(color: AppColors.border),
              ),
            ),
            child: Row(
              children: [
                const Icon(Icons.photo_library, color: AppColors.primary),
                const SizedBox(width: 12),
                Text(
                  'Evidence',
                  style: AppTypography.h3,
                ),
                const Spacer(),
                _buildViolationTypeBadge(violation.violationType),
              ],
            ),
          ),
          
          // Evidence Images
          Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Full Snapshot
                Text(
                  'Full Snapshot',
                  style: AppTypography.labelLarge.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
                const SizedBox(height: 12),
                Container(
                  height: 300,
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: AppColors.surfaceVariant,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.border),
                  ),
                  child: violation.snapshotPath != null
                      ? ClipRRect(
                          borderRadius: BorderRadius.circular(12),
                          child: Image.network(
                            '${AppConfig.apiBaseUrl}/snapshots/${violation.snapshotPath}',
                            fit: BoxFit.contain,
                            errorBuilder: (context, error, stackTrace) {
                              return _buildPlaceholderImage('Snapshot not available');
                            },
