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
                            loadingBuilder: (context, child, loadingProgress) {
                              if (loadingProgress == null) return child;
                              return Center(
                                child: CircularProgressIndicator(
                                  value: loadingProgress.expectedTotalBytes != null
                                      ? loadingProgress.cumulativeBytesLoaded /
                                          loadingProgress.expectedTotalBytes!
                                      : null,
                                ),
                              );
                            },
                          ),
                        )
                      : _buildPlaceholderImage('No snapshot available'),
                ),
                
                const SizedBox(height: 24),
                
                // Cropped Plate Image
                Text(
                  'License Plate Crop',
                  style: AppTypography.labelLarge.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
                const SizedBox(height: 12),
                Container(
                  height: 120,
                  width: 280,
                  decoration: BoxDecoration(
                    color: AppColors.surfaceVariant,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.border),
                  ),
                  child: violation.evidencePath != null
                      ? ClipRRect(
                          borderRadius: BorderRadius.circular(12),
                          child: Image.network(
                            '${AppConfig.apiBaseUrl}/evidence/${violation.evidencePath}',
                            fit: BoxFit.contain,
                            errorBuilder: (context, error, stackTrace) {
                              return _buildPlaceholderImage('Plate image not available');
                            },
                          ),
                        )
                      : _buildPlaceholderImage('No plate image'),
                ),
                
                const SizedBox(height: 24),
                
                // Detected Plate Number
                Row(
                  children: [
                    Text(
                      'Detected Plate:',
                      style: AppTypography.bodyMedium.copyWith(
                        color: AppColors.textSecondary,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      decoration: BoxDecoration(
                        color: AppColors.primary.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: AppColors.primary.withOpacity(0.5)),
                      ),
                      child: Text(
                        violation.licensePlate ?? 'UNKNOWN',
                        style: AppTypography.h4.copyWith(
                          color: AppColors.primary,
                          fontFamily: 'monospace',
                          letterSpacing: 2,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPlaceholderImage(String message) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.image_not_supported,
            size: 48,
            color: AppColors.textSecondary,
          ),
          const SizedBox(height: 8),
          Text(
            message,
            style: AppTypography.bodySmall.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildViolationTypeBadge(String type) {
    Color color;
    IconData icon;
    
    switch (type.toLowerCase()) {
      case 'red_light':
        color = AppColors.error;
        icon = Icons.traffic;
        break;
      case 'speeding':
        color = AppColors.warning;
        icon = Icons.speed;
        break;
      case 'parking':
      case 'no_parking':
        color = AppColors.info;
        icon = Icons.local_parking;
        break;
      default:
        color = AppColors.textSecondary;
        icon = Icons.warning;
    }
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 6),
          Text(
            type.replaceAll('_', ' ').toUpperCase(),
            style: AppTypography.labelSmall.copyWith(
              color: color,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFineBreakdownCard(Violation violation) {
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
                const Icon(Icons.receipt_long, color: AppColors.primary),
                const SizedBox(width: 12),
                Text(
                  'Fine Breakdown',
                  style: AppTypography.h3,
                ),
              ],
            ),
          ),
          
          // Fine details
          Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                _buildFineRow('Base Fine', violation.fineAmount * 0.7),
                const SizedBox(height: 12),
                _buildFineRow('Processing Fee', violation.fineAmount * 0.1),
                const SizedBox(height: 12),
                _buildFineRow('Admin Fee', violation.fineAmount * 0.1),
                const SizedBox(height: 12),
                _buildFineRow('Impact Score Adjustment', violation.fineAmount * 0.1),
                
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 16),
                  child: Divider(color: AppColors.border),
                ),
                
                // Total
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Total Fine',
                      style: AppTypography.h4,
                    ),
                    Text(
                      '\$${violation.fineAmount.toStringAsFixed(2)}',
                      style: AppTypography.h3.copyWith(
                        color: AppColors.primary,
                      ),
                    ),
                  ],
                ),
                
                const SizedBox(height: 16),
                
                // Points
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppColors.error.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.remove_circle, color: AppColors.error, size: 20),
                          const SizedBox(width: 8),
                          Text(
                            'Points Deducted',
                            style: AppTypography.bodyMedium,
                          ),
                        ],
                      ),
                      Text(
                        '-${violation.pointsDeducted}',
                        style: AppTypography.h4.copyWith(
                          color: AppColors.error,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFineRow(String label, double amount) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: AppTypography.bodyMedium.copyWith(
            color: AppColors.textSecondary,
          ),
        ),
        Text(
          '\$${amount.toStringAsFixed(2)}',
          style: AppTypography.bodyMedium,
        ),
      ],
    );
  }

  Widget _buildViolationInfoCard(Violation violation) {
    final dateFormat = DateFormat('EEEE, MMMM dd, yyyy');
    final timeFormat = DateFormat('HH:mm:ss');

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
                const Icon(Icons.info_outline, color: AppColors.primary),
                const SizedBox(width: 12),
                Text(
                  'Violation Details',
                  style: AppTypography.h3,
                ),
              ],
            ),
          ),
          
          // Info rows
          Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                _buildInfoRow('Violation ID', violation.violationId),
                const SizedBox(height: 12),
                _buildInfoRow('Driver ID', violation.driverId),
                const SizedBox(height: 12),
                _buildInfoRow('Date', dateFormat.format(violation.timestamp)),
                const SizedBox(height: 12),
                _buildInfoRow('Time', timeFormat.format(violation.timestamp)),
                if (violation.location != null) ...[
                  const SizedBox(height: 12),
                  _buildInfoRow('Location', violation.location!),
                ],
                const SizedBox(height: 12),
                _buildInfoRow('Status', violation.status.toUpperCase()),
                if (violation.notes != null && violation.notes!.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  const Divider(color: AppColors.border),
                  const SizedBox(height: 16),
                  Align(
                    alignment: Alignment.centerLeft,
