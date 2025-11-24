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
