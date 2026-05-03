import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../models/violation.dart';

/// Card widget for displaying a violation in a list
class ViolationCard extends StatelessWidget {
  final Violation violation;
  final VoidCallback? onTap;

  const ViolationCard({
    super.key,
    required this.violation,
    this.onTap,
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
          border: Border.all(color: AppColors.border.withOpacity(0.5)),
        ),
        child: Row(
          children: [
            // Icon
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: _getTypeColor().withOpacity(0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(
                _getTypeIcon(),
                color: _getTypeColor(),
                size: 24,
              ),
            ),
            const SizedBox(width: 14),
            // Details
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    violation.displayType,
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Icon(
                        Icons.access_time,
                        size: 12,
                        color: AppColors.textSecondary,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        _formatDate(violation.timestamp),
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 12,
                        ),
                      ),
                      if (violation.location != null) ...[
                        const SizedBox(width: 12),
                        Icon(
                          Icons.location_on,
                          size: 12,
                          color: AppColors.textSecondary,
                        ),
                        const SizedBox(width: 2),
                        Flexible(
                          child: Text(
                            violation.location!,
                            style: const TextStyle(
                              color: AppColors.textSecondary,
                              fontSize: 12,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),
            // Fine & Points
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  'LKR ${violation.fineAmount.toStringAsFixed(0)}',
                  style: const TextStyle(
                    color: AppColors.warning,
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppColors.error.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    '-${violation.pointsDeducted} pts',
                    style: const TextStyle(
                      color: AppColors.error,
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(width: 4),
            Icon(
              Icons.chevron_right,
              color: AppColors.textSecondary.withOpacity(0.5),
              size: 20,
            ),
          ],
        ),
      ),
    );
  }

  Color _getTypeColor() {
    switch (violation.violationType.toLowerCase()) {
      case 'lane_weaving':
        return AppColors.warning;
      case 'wrong_way':
      case 'red_light':
        return AppColors.error;
      case 'parking':
      case 'no_parking':
      case 'illegal_parking':
        return AppColors.info;
      case 'speeding':
        return AppColors.riskHigh;
      default:
        return AppColors.primary;
    }
  }

  IconData _getTypeIcon() {
    switch (violation.violationType.toLowerCase()) {
      case 'lane_weaving':
      case 'lane_drift':
        return Icons.swap_horiz;
      case 'wrong_way':
        return Icons.wrong_location;
      case 'red_light':
        return Icons.traffic;
      case 'parking':
      case 'no_parking':
      case 'illegal_parking':
        return Icons.local_parking;
      case 'speeding':
        return Icons.speed;
      default:
        return Icons.warning_amber;
    }
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final diff = now.difference(date);
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${date.day}/${date.month}/${date.year}';
  }
}
