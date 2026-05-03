import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../models/community.dart';

/// Card showing traffic summary for a junction
class TrafficSummaryCard extends StatelessWidget {
  final TrafficSummary summary;

  const TrafficSummaryCard({super.key, required this.summary});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border.withOpacity(0.5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.traffic, color: AppColors.primary, size: 20),
              const SizedBox(width: 8),
              const Text(
                'Traffic Status',
                style: TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const Spacer(),
              if (summary.signalPhase == 'emergency')
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.error.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.warning, color: AppColors.error, size: 12),
                      SizedBox(width: 4),
                      Text(
                        'EMERGENCY',
                        style: TextStyle(
                          color: AppColors.error,
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _InfoColumn(
                  icon: Icons.directions_car,
                  label: 'Density',
                  value: summary.currentDensity.toUpperCase(),
                  color: _getDensityColor(),
                ),
              ),
              Container(
                width: 1,
                height: 40,
                color: AppColors.border,
              ),
              Expanded(
                child: _InfoColumn(
                  icon: Icons.timer,
                  label: 'Wait Time',
                  value: summary.waitTimeFormatted,
                  color: AppColors.primary,
                ),
              ),
              Container(
                width: 1,
                height: 40,
                color: AppColors.border,
              ),
              Expanded(
                child: _InfoColumn(
                  icon: Icons.signal_cellular_alt,
                  label: 'Signal',
                  value: summary.signalPhase.toUpperCase(),
                  color: summary.signalPhase == 'emergency'
                      ? AppColors.error
                      : AppColors.success,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Color _getDensityColor() {
    switch (summary.currentDensity.toLowerCase()) {
      case 'low':
        return AppColors.success;
      case 'moderate':
        return AppColors.primary;
      case 'high':
        return AppColors.warning;
      case 'congested':
        return AppColors.error;
      default:
        return AppColors.textSecondary;
    }
  }
}

class _InfoColumn extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;

  const _InfoColumn({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Icon(icon, color: color, size: 20),
        const SizedBox(height: 6),
        Text(
          value,
          style: TextStyle(
            color: color,
            fontSize: 12,
            fontWeight: FontWeight.bold,
          ),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: const TextStyle(
            color: AppColors.textSecondary,
            fontSize: 10,
          ),
          textAlign: TextAlign.center,
        ),
      ],
    );
  }
}
