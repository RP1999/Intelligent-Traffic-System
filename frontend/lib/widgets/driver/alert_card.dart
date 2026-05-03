import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../models/community.dart';

/// Card widget for displaying a community alert
class AlertCard extends StatelessWidget {
  final CommunityAlert alert;
  final VoidCallback? onTap;

  const AlertCard({
    super.key,
    required this.alert,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: _getSeverityColor().withOpacity(0.3),
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: _getSeverityColor().withOpacity(0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(
                _getAlertIcon(),
                color: _getSeverityColor(),
                size: 20,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: _getSeverityColor().withOpacity(0.15),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          alert.displayAlertType,
                          style: TextStyle(
                            color: _getSeverityColor(),
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                      const Spacer(),
                      Text(
                        alert.timeAgo,
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    alert.message,
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 13,
                      height: 1.4,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Color _getSeverityColor() {
    switch (alert.severity.toLowerCase()) {
      case 'critical':
        return AppColors.error;
      case 'high':
        return AppColors.riskHigh;
      case 'medium':
        return AppColors.warning;
      case 'low':
      default:
        return AppColors.info;
    }
  }

  IconData _getAlertIcon() {
    switch (alert.alertType) {
      case 'emergency':
        return Icons.emergency;
      case 'accident':
        return Icons.car_crash;
      case 'congestion':
        return Icons.traffic;
      case 'high_risk':
        return Icons.warning_amber;
      case 'construction':
        return Icons.construction;
      default:
        return Icons.info_outline;
    }
  }
}
