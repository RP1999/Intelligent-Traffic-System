import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../core/services/notification_service.dart';
import '../../providers/auth_provider.dart';
import '../../providers/driver/driver_home_provider.dart';
import '../../widgets/driver/score_circle.dart';
import '../../widgets/driver/alert_card.dart';

class DriverHomeScreen extends StatefulWidget {
  const DriverHomeScreen({super.key});

  @override
  State<DriverHomeScreen> createState() => _DriverHomeScreenState();
}

class _DriverHomeScreenState extends State<DriverHomeScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final provider = context.read<DriverHomeProvider>();
      provider.loadHomeData();
      provider.startLivePolling();
      _initNotifications();
    });
  }

  @override
  void dispose() {
    // Stop polling when screen is disposed
    // (Provider itself also cancels in its own dispose)
    super.dispose();
  }

  /// Initialize FCM push notifications and handle notification taps
  Future<void> _initNotifications() async {
    try {
      final notifService = NotificationService();
      await notifService.initialize();

      // Subscribe to traffic alerts topic
      await notifService.subscribeToTopic('traffic_alerts');

      // Handle notification tap → navigate to appropriate screen
      notifService.onNotificationTapped = (data) {
        if (!mounted) return;
        final type = data['type'] ?? '';
        switch (type) {
          case 'violation':
            // Navigate to violations tab
            _navigateToTab(1);
            break;
          case 'fine':
            // Navigate to fines tab
            _navigateToTab(2);
            break;
          default:
            // Refresh home data
            context.read<DriverHomeProvider>().refresh();
        }
      };
    } catch (e) {
      debugPrint('[Home] Push notification init error (non-fatal): $e');
    }
  }

  /// Navigate to a specific tab in the parent shell
  void _navigateToTab(int index) {
    // Find the DriverShellScreen ancestor and switch tabs
    // Using a simple approach: navigate to the route
    if (!mounted) return;
    final routes = ['/driver/home', '/driver/violations', '/driver/fines', '/driver/profile'];
    if (index >= 0 && index < routes.length) {
      Navigator.of(context).pushReplacementNamed(routes[index]);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<DriverHomeProvider>(
      builder: (context, provider, _) {
        return Scaffold(
          backgroundColor: AppColors.background,
          body: RefreshIndicator(
            color: AppColors.primary,
            backgroundColor: AppColors.surface,
            onRefresh: () => provider.refresh(),
            child: CustomScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              slivers: [
                // App Bar
                _buildAppBar(context, provider),

                // Content
                if (provider.isLoading && provider.profile == null)
                  const SliverFillRemaining(
                    child: Center(
                      child: CircularProgressIndicator(color: AppColors.primary),
                    ),
                  )
                else
                  SliverPadding(
                    padding: const EdgeInsets.all(16),
                    sliver: SliverList(
                      delegate: SliverChildListDelegate([
                        // Offline banner
                        if (provider.isOffline)
                          _buildOfflineBanner(),
                        if (provider.isOffline)
                          const SizedBox(height: 12),

                        // Score Card
                        _buildScoreCard(provider),
                        const SizedBox(height: 16),

                        // Quick Stats
                        _buildQuickStats(provider),
                        const SizedBox(height: 20),

                        // Junction Safety
                        if (provider.junctionScore != null)
                          _buildJunctionSafety(provider),
                        if (provider.junctionScore != null)
                          const SizedBox(height: 20),

                        // Community Alerts
                        _buildAlertsSection(provider),
                        const SizedBox(height: 20),
                      ]),
                    ),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildOfflineBanner() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.warning.withAlpha(30),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.warning.withAlpha(80)),
      ),
      child: Row(
        children: [
          Icon(Icons.wifi_off, color: AppColors.warning, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'You are offline. Showing cached data.',
              style: TextStyle(
                color: AppColors.warning,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAppBar(BuildContext context, DriverHomeProvider provider) {
    final user = context.watch<AuthProvider>().user;
    return SliverAppBar(
      floating: true,
      backgroundColor: AppColors.surface,
      automaticallyImplyLeading: false,
      title: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              gradient: AppColors.primaryGradient,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Center(
              child: Icon(Icons.drive_eta, color: AppColors.background, size: 22),
            ),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Hello, ${user?.name ?? 'Driver'} 👋',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
              Text(
                user?.plateNumber ?? '',
                style: const TextStyle(
                  fontSize: 12,
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
        ],
      ),
      actions: [
        Stack(
          children: [
            IconButton(
              icon: const Icon(Icons.notifications_outlined,
                  color: AppColors.textPrimary),
              onPressed: () => _showNotifications(context, provider),
            ),
            if (provider.unreadCount > 0)
              Positioned(
                right: 8,
                top: 8,
                child: Container(
                  padding: const EdgeInsets.all(4),
                  decoration: const BoxDecoration(
                    color: AppColors.error,
                    shape: BoxShape.circle,
                  ),
                  child: Text(
                    '${provider.unreadCount}',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(width: 4),
      ],
    );
  }

  Widget _buildScoreCard(DriverHomeProvider provider) {
    final profile = provider.profile;
    final score = profile?.currentScore ?? 100;
    final riskLevel = profile?.displayRiskLevel ?? 'Good';

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppColors.surface,
            AppColors.surfaceVariant.withOpacity(0.8),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: AppColors.getScoreColor(score).withOpacity(0.3),
        ),
      ),
      child: Column(
        children: [
          ScoreCircle(score: score, size: 150, strokeWidth: 12),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            decoration: BoxDecoration(
              color: AppColors.getScoreColor(score).withOpacity(0.15),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              riskLevel,
              style: TextStyle(
                color: AppColors.getScoreColor(score),
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Your Driving Safety Score',
            style: TextStyle(
              color: AppColors.textSecondary,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuickStats(DriverHomeProvider provider) {
    final profile = provider.profile;
    return Row(
      children: [
        Expanded(
          child: _QuickStatCard(
            icon: Icons.warning_amber_rounded,
            label: 'Violations',
            value: '${profile?.totalViolations ?? 0}',
            color: AppColors.warning,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _QuickStatCard(
            icon: Icons.receipt_long,
            label: 'Pending Fines',
            value: 'LKR ${(profile?.totalFines ?? 0).toStringAsFixed(0)}',
            color: AppColors.error,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _QuickStatCard(
            icon: Icons.calendar_today,
            label: 'Member',
            value: profile?.memberSinceFormatted ?? 'N/A',
            color: AppColors.info,
          ),
        ),
      ],
    );
  }

  Widget _buildJunctionSafety(DriverHomeProvider provider) {
    final junction = provider.junctionScore!;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border.withOpacity(0.5)),
      ),
      child: Row(
        children: [
          // Mini score circle
          ScoreCircle(
            score: junction.currentScore,
            size: 70,
            strokeWidth: 6,
            showLabel: false,
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Junction Safety',
                  style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  junction.junctionName ?? 'Main Junction',
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    _MiniChip(
                      label: junction.safetyColor,
                      color: junction.safetyColor == 'GREEN'
                          ? AppColors.success
                          : junction.safetyColor == 'YELLOW'
                              ? AppColors.warning
                              : AppColors.error,
                    ),
                    const SizedBox(width: 8),
                    _MiniChip(
                      label: junction.riskLevel.toUpperCase(),
                      color: junction.riskLevel.toLowerCase() == 'safe'
                          ? AppColors.success
                          : junction.riskLevel.toLowerCase() == 'caution'
                              ? AppColors.warning
                              : AppColors.error,
                    ),
                    const SizedBox(width: 8),
                    if (junction.activeAlerts > 0)
                      _MiniChip(
                        label: '${junction.activeAlerts} alerts',
                        color: AppColors.warning,
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

  Widget _buildAlertsSection(DriverHomeProvider provider) {
    if (provider.alerts.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          children: [
            Icon(Icons.check_circle, color: AppColors.success, size: 40),
            const SizedBox(height: 8),
            const Text(
              'No Active Alerts',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 4),
            const Text(
              'All clear! Drive safely.',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
            ),
          ],
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.campaign, color: AppColors.primary, size: 20),
            const SizedBox(width: 8),
            const Text(
              'Community Alerts',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
            const Spacer(),
            Text(
              '${provider.alerts.length} active',
              style: const TextStyle(
                color: AppColors.textSecondary,
                fontSize: 12,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        ...provider.alerts.take(5).map((alert) => AlertCard(alert: alert)),
      ],
    );
  }

  void _showNotifications(BuildContext context, DriverHomeProvider provider) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      isScrollControlled: true,
      builder: (context) {
        return DraggableScrollableSheet(
          initialChildSize: 0.6,
          maxChildSize: 0.9,
          minChildSize: 0.3,
          expand: false,
          builder: (context, scrollController) {
            return Column(
              children: [
                // Handle bar
                Container(
                  margin: const EdgeInsets.only(top: 12),
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AppColors.border,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      const Text(
                        'Notifications',
                        style: TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const Spacer(),
                      if (provider.unreadCount > 0)
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: AppColors.primary.withOpacity(0.15),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            '${provider.unreadCount} unread',
                            style: const TextStyle(
                              color: AppColors.primary,
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
                Expanded(
                  child: provider.notifications.isEmpty
                      ? const Center(
                          child: Text(
                            'No notifications yet',
                            style: TextStyle(color: AppColors.textSecondary),
                          ),
                        )
                      : ListView.builder(
                          controller: scrollController,
                          padding: const EdgeInsets.symmetric(horizontal: 16),
                          itemCount: provider.notifications.length,
                          itemBuilder: (context, index) {
                            final notif = provider.notifications[index];
                            return InkWell(
                              onTap: () async {
                                // Mark as read first, wait for it
                                if (!notif.read) {
                                  await provider.markNotificationRead(notif.notificationId);
                                }
                                if (!mounted) return;
                                // Close bottom sheet
                                Navigator.pop(context);
                                // Navigate based on type
                                switch (notif.notificationType) {
                                  case 'violation':
                                    _navigateToTab(1);
                                    break;
                                  case 'fine':
                                    _navigateToTab(2);
                                    break;
                                  case 'warning':
                                  default:
                                    provider.refresh();
                                    break;
                                }
                              },
                              borderRadius: BorderRadius.circular(12),
                              child: Container(
                              margin: const EdgeInsets.only(bottom: 8),
                              padding: const EdgeInsets.all(14),
                              decoration: BoxDecoration(
                                color: notif.read
                                    ? AppColors.background
                                    : AppColors.primary.withOpacity(0.05),
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(
                                  color: notif.read
                                      ? AppColors.border.withOpacity(0.3)
                                      : AppColors.primary.withOpacity(0.2),
                                ),
                              ),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Icon(
                                    _getNotifIcon(notif.notificationType),
                                    color: _getNotifColor(notif.notificationType),
                                    size: 20,
                                  ),
                                  const SizedBox(width: 12),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          notif.title,
                                          style: TextStyle(
                                            color: AppColors.textPrimary,
                                            fontSize: 13,
                                            fontWeight: notif.read
                                                ? FontWeight.w400
                                                : FontWeight.w600,
                                          ),
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          notif.message,
                                          style: const TextStyle(
                                            color: AppColors.textSecondary,
                                            fontSize: 12,
                                          ),
                                          maxLines: 2,
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      ],
                                    ),
                                  ),
                                  Text(
                                    notif.timeAgo,
                                    style: const TextStyle(
                                      color: AppColors.textSecondary,
                                      fontSize: 10,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            );
                          },
                        ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Color _getTrafficColor(String level) {
    switch (level.toLowerCase()) {
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

  IconData _getNotifIcon(String type) {
    switch (type) {
      case 'violation':
        return Icons.warning_amber;
      case 'warning':
        return Icons.notification_important;
      default:
        return Icons.info_outline;
    }
  }

  Color _getNotifColor(String type) {
    switch (type) {
      case 'violation':
        return AppColors.error;
      case 'warning':
        return AppColors.warning;
      default:
        return AppColors.info;
    }
  }
}

class _QuickStatCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;

  const _QuickStatCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border.withOpacity(0.5)),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 22),
          const SizedBox(height: 8),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 13,
              fontWeight: FontWeight.bold,
            ),
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 10,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

class _MiniChip extends StatelessWidget {
  final String label;
  final Color color;

  const _MiniChip({required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
