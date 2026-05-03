import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../models/fine.dart';

/// Card widget for displaying a fine in a list
class FineCard extends StatelessWidget {
  final Fine fine;
  final VoidCallback? onTap;
  final VoidCallback? onPayTap;

  const FineCard({
    super.key,
    required this.fine,
    this.onTap,
    this.onPayTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: fine.isPaid
                ? AppColors.success.withOpacity(0.3)
                : AppColors.border.withOpacity(0.5),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header row
            Row(
              children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    color: _getStatusColor().withOpacity(0.15),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(
                    fine.isPaid ? Icons.check_circle : Icons.receipt_long,
                    color: _getStatusColor(),
                    size: 22,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        fine.displayType,
                        style: const TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        fine.issuedDateFormatted,
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
                // Amount
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      'LKR ${fine.amount.toStringAsFixed(0)}',
                      style: TextStyle(
                        color: fine.isPaid ? AppColors.success : AppColors.warning,
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 4),
                    _StatusBadge(status: fine.displayStatus, isPaid: fine.isPaid),
                  ],
                ),
              ],
            ),

            // Breakdown (if available)
            if (fine.breakdown != null && !fine.isPaid) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.background,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Column(
                  children: [
                    _BreakdownRow('Base Penalty', fine.breakdown!.base),
                    const SizedBox(height: 4),
                    _BreakdownRow('Duration Penalty', fine.breakdown!.duration),
                    const SizedBox(height: 4),
                    _BreakdownRow('Traffic Impact', fine.breakdown!.impact),
                  ],
                ),
              ),
            ],

            // Pay button
            if (!fine.isPaid && onPayTap != null) ...[
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: onPayTap,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    foregroundColor: AppColors.background,
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  child: const Text(
                    'Pay Now',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Color _getStatusColor() {
    if (fine.isPaid) return AppColors.success;
    if (fine.isOverdue) return AppColors.error;
    return AppColors.warning;
  }
}

class _StatusBadge extends StatelessWidget {
  final String status;
  final bool isPaid;

  const _StatusBadge({required this.status, required this.isPaid});

  @override
  Widget build(BuildContext context) {
    final color = isPaid ? AppColors.success : AppColors.warning;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        status,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _BreakdownRow extends StatelessWidget {
  final String label;
  final double amount;

  const _BreakdownRow(this.label, this.amount);

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: AppColors.textSecondary,
            fontSize: 12,
          ),
        ),
        Text(
          'LKR ${amount.toStringAsFixed(0)}',
          style: const TextStyle(
            color: AppColors.textPrimary,
            fontSize: 12,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }
}
