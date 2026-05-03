import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../models/iot_junction.dart';
import '../../../providers/admin/iot_junction_provider.dart';
import '../../../widgets/admin/admin_sidebar.dart';
import '../../../widgets/common/loading_widget.dart';
import '../../../widgets/common/empty_state_widget.dart';

class IotJunctionScreen extends StatefulWidget {
  const IotJunctionScreen({super.key});

  @override
  State<IotJunctionScreen> createState() => _IotJunctionScreenState();
}

class _IotJunctionScreenState extends State<IotJunctionScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final provider = context.read<IotJunctionProvider>();
      provider.loadLatest(forceRefresh: true);
      provider.startPolling(interval: const Duration(seconds: 5));
    });
  }

  @override
  void dispose() {
    context.read<IotJunctionProvider>().stopPolling();
    super.dispose();
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
        Navigator.of(context).pushReplacementNamed('/admin/drivers');
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
        // Already here
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          AdminSidebar(
            selectedIndex: 8,
            onItemSelected: _handleNavigation,
          ),
          Expanded(
            child: Container(
              color: AppColors.background,
              child: Consumer<IotJunctionProvider>(
                builder: (context, provider, _) {
                  return CustomScrollView(
                    slivers: [
                      SliverToBoxAdapter(child: _buildHeader(provider)),
                      SliverToBoxAdapter(child: _buildBody(provider)),
                    ],
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(IotJunctionProvider provider) {
    final status = provider.status;
    final isConnected = provider.state != IotJunctionLoadingState.error;
    final deviceId = (status?.junctionId ?? '').trim();

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border(
          bottom: BorderSide(color: AppColors.border, width: 1),
        ),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'IoT Traffic Control',
                    style: AppTypography.h1.copyWith(fontSize: 32, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      Container(
                        width: 10,
                        height: 10,
                        decoration: BoxDecoration(
                          color: isConnected ? AppColors.trafficGreen : AppColors.trafficRed,
                          shape: BoxShape.circle,
                          boxShadow: [
                            BoxShadow(
                              color: (isConnected ? AppColors.trafficGreen : AppColors.trafficRed)
                                  .withOpacity(0.5),
                              blurRadius: 6,
                              spreadRadius: 1,
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        isConnected ? 'IoT Device Connected' : 'Device Disconnected',
                        style: AppTypography.bodyMedium.copyWith(
                          color: isConnected ? AppColors.trafficGreen : AppColors.trafficRed,
                        ),
                      ),
                      const SizedBox(width: 16),
                      Text(
                        deviceId.isEmpty ? 'Awaiting device data...' : deviceId,
                        style: AppTypography.caption.copyWith(color: AppColors.textSecondary),
                      ),
                    ],
                  ),
                ],
              ),
              const Spacer(),
              OutlinedButton.icon(
                onPressed: () => provider.loadLatest(forceRefresh: true),
                icon: const Icon(Icons.refresh),
                label: const Text('Refresh Latest'),
              ),
              const SizedBox(width: 12),
              OutlinedButton.icon(
                onPressed: () => provider.triggerManualSync(),
                icon: const Icon(Icons.sync),
                label: const Text('Sync Now'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (status != null) ...[
            Row(
              children: [
                Text(
                  'Last Updated: ${_formatTimestamp(status.syncedAt ?? status.timestamp)}',
                  style: AppTypography.bodySmall.copyWith(color: AppColors.textSecondary),
                ),
                const SizedBox(width: 16),
                Text(
                  'DB timestamp: ${status.rawTimestamp}',
                  style: AppTypography.caption.copyWith(color: AppColors.textSecondary),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildBody(IotJunctionProvider provider) {
    if (provider.state == IotJunctionLoadingState.loading && provider.status == null) {
      return const Padding(
        padding: EdgeInsets.only(top: 40),
        child: LoadingWidget(message: 'Loading IoT junction data...'),
      );
    }

    if (provider.state == IotJunctionLoadingState.error && provider.status == null) {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child: EmptyStateWidget(
          icon: Icons.wifi_off,
          title: 'No IoT Data Available',
          message: provider.errorMessage ?? 'Could not load synced junction status.',
          actionLabel: 'Retry',
          onAction: () => provider.loadLatest(forceRefresh: true),
        ),
      );
    }

    final status = provider.status;
    if (status == null) {
      return const SizedBox.shrink();
    }

    return Column(
      children: [
        // Emergency Vehicle Alert Banner
        if (status.southEmergency) ...[
          _buildEmergencyAlert(status),
          const SizedBox(height: 16),
        ],
        _buildActiveLaneSection(status),
        const SizedBox(height: 32),
        _buildLaneSummaryRow(status),
        const SizedBox(height: 32),
        _buildRealTimeVehicleCountsSection(status),
        const SizedBox(height: 24),
      ],
    );
  }

  Widget _buildEmergencyAlert(IotJunctionStatus status) {
    return Container(
      margin: const EdgeInsets.fromLTRB(24, 24, 24, 0),
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.error,
            AppColors.error.withOpacity(0.85),
          ],
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.red.shade900, width: 2),
        boxShadow: [
          BoxShadow(
            color: AppColors.error.withOpacity(0.4),
            blurRadius: 20,
            spreadRadius: 2,
          ),
        ],
      ),
      child: Row(
        children: [
          // Flashing Siren Icon
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white,
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: Colors.white.withOpacity(0.5),
                  blurRadius: 12,
                  spreadRadius: 2,
                ),
              ],
            ),
            child: Icon(
              Icons.emergency,
              color: AppColors.error,
              size: 32,
            ),
          ),
          const SizedBox(width: 20),
          
          // Alert Text
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '🚨 EMERGENCY VEHICLE DETECTED',
                  style: AppTypography.h2.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.w800,
                    fontSize: 22,
                    letterSpacing: 0.5,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Ambulance detected in Lane 1 (South) - Priority clearance activated',
                  style: AppTypography.bodyMedium.copyWith(
                    color: Colors.white.withOpacity(0.95),
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
          
          // Lane Badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              boxShadow: [
                BoxShadow(
                  color: Colors.white.withOpacity(0.3),
                  blurRadius: 8,
                ),
              ],
            ),
            child: Column(
              children: [
                Text(
                  'LANE 1',
                  style: AppTypography.labelSmall.copyWith(
                    color: AppColors.error,
                    fontWeight: FontWeight.w800,
                    fontSize: 14,
                  ),
                ),
                Text(
                  'SOUTH',
                  style: AppTypography.caption.copyWith(
                    color: AppColors.error,
                    fontWeight: FontWeight.w700,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActiveLaneSection(IotJunctionStatus status) {
    final priorityLane = status.priorityLane;
    final count = status.counts[priorityLane] ?? 0;
    final light = status.lights[priorityLane] ?? 'red';
    final isEmergency = status.priorityReason == 'emergency';

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 24),
      padding: const EdgeInsets.all(32),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.surface,
            AppColors.surface.withOpacity(0.7),
          ],
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.primary.withOpacity(0.3), width: 2),
        boxShadow: [
          BoxShadow(
            color: AppColors.primary.withOpacity(0.15),
            blurRadius: 20,
            spreadRadius: 0,
          ),
        ],
      ),
      child: Column(
        children: [
          // Section Title
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: AppColors.primary.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: AppColors.primary.withOpacity(0.4)),
                ),
                child: Text(
                  'ACTIVE: ${_laneTitle(priorityLane)} (Lane ${_getLaneNumber(priorityLane)})',
                  style: AppTypography.labelSmall.copyWith(
                    color: AppColors.primary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              const Spacer(),
              if (isEmergency)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppColors.error.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    '🚨 Emergency Mode',
                    style: AppTypography.labelSmall.copyWith(
                      color: AppColors.error,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 28),

          // Traffic Light Visualization
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _buildTrafficLightCircle('RED', light == 'red'),
              const SizedBox(width: 20),
              _buildTrafficLightCircle('YELLOW', light == 'yellow'),
              const SizedBox(width: 20),
              _buildTrafficLightCircle('GREEN', light == 'green'),
            ],
          ),
          const SizedBox(height: 32),

          // Status Row
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              Column(
                children: [
                  Text(
                    'VEHICLES WAITING',
                    style: AppTypography.caption.copyWith(
                      color: AppColors.textSecondary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '$count vehicle${count != 1 ? 's' : ''}',
                    style: AppTypography.h2.copyWith(
                      color: AppColors.textPrimary,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
              Container(
                width: 1,
                height: 60,
                color: AppColors.border,
              ),
              Column(
                children: [
                  Text(
                    'CURRENT STATE',
                    style: AppTypography.caption.copyWith(
                      color: AppColors.textSecondary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    light.toUpperCase(),
                    style: AppTypography.h2.copyWith(
                      color: _lightColor(light),
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildTrafficLightCircle(String label, bool isActive) {
    final isRed = label == 'RED';
    final isYellow = label == 'YELLOW';

    Color getColor() {
      if (isRed) return AppColors.trafficRed;
      if (isYellow) return AppColors.trafficYellow;
      return AppColors.trafficGreen;
    }

    return Column(
      children: [
        Container(
          width: 80,
          height: 80,
          decoration: BoxDecoration(
            color: isActive ? getColor() : AppColors.border.withOpacity(0.3),
            shape: BoxShape.circle,
            boxShadow: isActive
                ? [
                    BoxShadow(
                      color: getColor().withOpacity(0.6),
                      blurRadius: 20,
                      spreadRadius: 4,
                    ),
                  ]
                : [],
          ),
        ),
        const SizedBox(height: 12),
        Text(
          label,
          style: AppTypography.labelSmall.copyWith(
            color: isActive ? getColor() : AppColors.textSecondary,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }

  Widget _buildLaneSummaryRow(IotJunctionStatus status) {
    final lanes = const ['south', 'east', 'north', 'west'];

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'All Lanes - IoT Sensor Data',
            style: AppTypography.h3.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: lanes.map((lane) => _buildLaneSummaryItem(status, lane)).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildLaneSummaryItem(IotJunctionStatus status, String lane) {
    final isInactive = lane == 'west';
    final count = status.counts[lane] ?? 0;
    final light = isInactive ? 'red' : (status.lights[lane] ?? 'red');
    final isPriority = status.priorityLane == lane;

    return Expanded(
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 6),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: isPriority ? AppColors.primary : AppColors.border,
            width: isPriority ? 2 : 1,
          ),
          boxShadow: isPriority
              ? [
                  BoxShadow(
                    color: AppColors.primary.withOpacity(0.15),
                    blurRadius: 12,
                    spreadRadius: 0,
                  ),
                ]
              : [],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            // Lane Label
            Text(
              _getLaneLabelShort(lane),
              style: AppTypography.h2.copyWith(
                color: AppColors.textSecondary,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 12),

            // Light Circle
            Container(
              width: 50,
              height: 50,
              decoration: BoxDecoration(
                color: _lightColor(light),
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: _lightColor(light).withOpacity(0.4),
                    blurRadius: 12,
                    spreadRadius: 2,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),

            // Vehicle Count
            Text(
              '$count',
              style: AppTypography.h1.copyWith(
                fontSize: 28,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'vehicle${count != 1 ? 's' : ''}',
              style: AppTypography.caption.copyWith(
                color: AppColors.textSecondary,
              ),
            ),

            if (isInactive) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.textSecondary.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  'Inactive',
                  style: AppTypography.caption.copyWith(
                    color: AppColors.textSecondary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildRealTimeVehicleCountsSection(IotJunctionStatus status) {
    final lanes = const [
      ('south', 'South (Lane 1)'),
      ('east', 'East (Lane 2)'),
      ('north', 'North (Lane 3)'),
      ('west', 'West (Lane 4)'),
    ];

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Real-time Vehicle Counts',
            style: AppTypography.h3.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 16),
          Container(
            width: double.infinity,
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppColors.border),
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(14),
              child: Table(
                columnWidths: const {
                  0: FlexColumnWidth(2.4),
                  1: FlexColumnWidth(1.1),
                  2: FlexColumnWidth(1.5),
                },
                border: TableBorder(
                  horizontalInside: BorderSide(
                    color: AppColors.border.withOpacity(0.45),
                    width: 1,
                  ),
                ),
                children: [
                  TableRow(
                    decoration: BoxDecoration(
                      color: AppColors.surfaceVariant.withOpacity(0.65),
                    ),
                    children: [
                      _buildRealtimeHeaderCell('Lane'),
                      _buildRealtimeHeaderCell('Vehicles', align: TextAlign.center),
                      _buildRealtimeHeaderCell('Status'),
                    ],
                  ),
                  ...lanes.map((lane) {
                    final laneKey = lane.$1;
                    final laneName = lane.$2;
                    final count = status.counts[laneKey] ?? 0;
                    final light = status.lights[laneKey] ?? 'red';
                    final isInactive = laneKey == 'west';

                    return TableRow(
                      children: [
                        _buildRealtimeValueCell(value: laneName),
                        _buildRealtimeValueCell(
                          value: '$count',
                          align: TextAlign.center,
                          bold: true,
                        ),
                        _buildRealtimeStatusCell(
                          lightColor: isInactive ? AppColors.textSecondary : _lightColor(light),
                          label: isInactive ? 'Inactive' : light.toUpperCase(),
                        ),
                      ],
                    );
                  }),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRealtimeHeaderCell(
    String label, {
    TextAlign align = TextAlign.left,
  }) {
    final alignment = align == TextAlign.center
        ? Alignment.center
        : (align == TextAlign.right ? Alignment.centerRight : Alignment.centerLeft);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      child: Align(
        alignment: alignment,
        child: Text(
          label,
          textAlign: align,
          style: AppTypography.labelSmall.copyWith(
            color: AppColors.textSecondary,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    );
  }

  Widget _buildRealtimeValueCell({
    required String value,
    TextAlign align = TextAlign.left,
    bool bold = false,
  }) {
    final alignment = align == TextAlign.center
        ? Alignment.center
        : (align == TextAlign.right ? Alignment.centerRight : Alignment.centerLeft);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      child: Align(
        alignment: alignment,
        child: Text(
          value,
          textAlign: align,
          style: AppTypography.bodySmall.copyWith(
            fontWeight: bold ? FontWeight.w700 : FontWeight.w500,
          ),
        ),
      ),
    );
  }

  Widget _buildRealtimeStatusCell({
    required Color lightColor,
    required String label,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      child: Row(
        children: [
          Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(
              color: lightColor,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            label,
            style: AppTypography.caption.copyWith(color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }

  String _getLaneNumber(String lane) {
    switch (lane.toLowerCase()) {
      case 'south':
        return '1';
      case 'east':
        return '2';
      case 'north':
        return '3';
      case 'west':
        return '4';
      default:
        return '0';
    }
  }

  String _getLaneLabelShort(String lane) {
    switch (lane.toLowerCase()) {
      case 'north':
        return 'N';
      case 'south':
        return 'S';
      case 'east':
        return 'E';
      case 'west':
        return 'W';
      default:
        return lane[0].toUpperCase();
    }
  }



  Color _lightColor(String light) {
    switch (light.toLowerCase()) {
      case 'green':
        return AppColors.trafficGreen;
      case 'yellow':
        return AppColors.trafficYellow;
      case 'red':
      default:
        return AppColors.trafficRed;
    }
  }

  String _laneTitle(String lane) {
    switch (lane.toLowerCase()) {
      case 'north':
        return 'North';
      case 'south':
        return 'South';
      case 'east':
        return 'East';
      case 'west':
        return 'West';
      default:
        return lane;
    }
  }

  String _formatTimestamp(DateTime? value) {
    if (value == null) return 'N/A';
    final local = value.toLocal();
    final hh = local.hour.toString().padLeft(2, '0');
    final mm = local.minute.toString().padLeft(2, '0');
    final ss = local.second.toString().padLeft(2, '0');
    return '${local.year}-${local.month.toString().padLeft(2, '0')}-${local.day.toString().padLeft(2, '0')} $hh:$mm:$ss';
  }
}
