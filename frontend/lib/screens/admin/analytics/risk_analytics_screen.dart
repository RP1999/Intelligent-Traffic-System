import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../widgets/admin/admin_sidebar.dart';
import '../../../widgets/common/loading_widget.dart';

/// Risk Analytics Screen
/// Shows vehicle risk scores, abnormal behavior logs, and risk distribution
class RiskAnalyticsScreen extends StatefulWidget {
  const RiskAnalyticsScreen({super.key});

  @override
  State<RiskAnalyticsScreen> createState() => _RiskAnalyticsScreenState();
}

class _RiskAnalyticsScreenState extends State<RiskAnalyticsScreen> {
  final ApiClient _apiClient = ApiClient();
  
  bool _isLoading = true;
  Map<String, dynamic>? _riskStats;
  List<dynamic> _currentScores = [];
  List<dynamic> _highRiskVehicles = [];
  List<dynamic> _behaviorLog = [];
  String? _error;
  
  // Risk level filter for vehicles section
  String _selectedRiskLevel = 'ALL';

  @override
  void initState() {
    super.initState();
    _loadRiskData();
  }

  Future<void> _loadRiskData() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      // Load all risk data in parallel
      final results = await Future.wait([
        _apiClient.get(ApiEndpoints.riskStats),
        _apiClient.get(ApiEndpoints.riskCurrentScores),
        _apiClient.get(ApiEndpoints.riskHighRiskVehicles),
        _apiClient.get(ApiEndpoints.riskBehaviorLog),
      ]);

      if (!mounted) return;

      setState(() {
        _riskStats = results[0].data;
        
        // Handle current scores response
        if (results[1].data != null) {
          _currentScores = results[1].data!['scores'] ?? [];
        }
        
        // Handle high risk vehicles response  
        if (results[2].data != null) {
          _highRiskVehicles = results[2].data!['vehicles'] ?? [];
        }
        
        // Handle behavior log response
        if (results[3].data != null) {
          _behaviorLog = results[3].data!['events'] ?? [];
        }
        
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          AdminSidebar(
            selectedIndex: 6, // Risk Analytics index
            onItemSelected: (index) => _handleNavigation(index),
          ),
          Expanded(
            child: Container(
              color: AppColors.background,
              child: _isLoading
                  ? const Center(child: LoadingWidget())
                  : _error != null
                      ? _buildErrorState()
                      : CustomScrollView(
                          slivers: [
                            SliverToBoxAdapter(child: _buildHeader()),
                            SliverToBoxAdapter(child: _buildRiskSummaryCards()),
                            SliverToBoxAdapter(child: _buildRiskDistributionChart()),
                            SliverToBoxAdapter(child: _buildHighRiskVehiclesSection()),
                            SliverToBoxAdapter(child: _buildBehaviorLogSection()),
                          ],
                        ),
            ),
          ),
        ],
      ),
    );
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
        // Already here - Risk Analytics
        break;
      case 7:
        Navigator.of(context).pushReplacementNamed('/admin/settings');
        break;
      case 8:
        Navigator.of(context).pushReplacementNamed('/admin/iot-junction');
        break;
    }
  }

  Widget _buildErrorState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.error_outline, size: 64, color: AppColors.error),
          const SizedBox(height: 16),
          Text(
            'Failed to load risk data',
            style: AppTypography.h3,
          ),
          const SizedBox(height: 8),
          Text(
            _error ?? 'Unknown error',
            style: AppTypography.bodyMedium.copyWith(color: AppColors.textSecondary),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _loadRiskData,
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(24),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Risk Analytics',
                style: AppTypography.h1.copyWith(fontSize: 28),
              ),
              const SizedBox(height: 4),
              Text(
                'Accident Risk Prediction & Behavior Detection',
                style: AppTypography.bodyMedium.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
          Row(
            children: [
              _buildFormulaChip(),
              const SizedBox(width: 12),
              IconButton(
                onPressed: _loadRiskData,
                icon: const Icon(Icons.refresh),
                tooltip: 'Refresh data',
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildFormulaChip() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.primary.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.primary.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.functions, size: 16, color: AppColors.primary),
          const SizedBox(width: 8),
          Text(
            'Risk = (Speed × 0.6) + (History × 0.4)',
            style: AppTypography.bodySmall.copyWith(
              color: AppColors.primary,
              fontFamily: 'monospace',
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRiskSummaryCards() {
    final summary = _riskStats?['summary'] ?? {};
    
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        children: [
          Expanded(
            child: _buildStatCard(
              'Total Vehicles Tracked',
              '${summary['total_vehicles_tracked'] ?? 0}',
              Icons.directions_car,
              AppColors.primary,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: _buildStatCard(
              'High Risk Count',
              '${summary['high_risk_count'] ?? 0}',
              Icons.warning_amber,
              AppColors.error,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: _buildStatCard(
              'Average Risk Score',
              '${(summary['average_risk_score'] ?? 0).toStringAsFixed(1)}',
              Icons.speed,
              AppColors.warning,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: _buildStatCard(
              'Behavior Events',
              '${_riskStats?['behavior_events_count'] ?? 0}',
              Icons.psychology,
              AppColors.info,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatCard(String label, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, color: color, size: 20),
              ),
              const Spacer(),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            value,
            style: AppTypography.h2.copyWith(color: color),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: AppTypography.bodySmall.copyWith(color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }

  Widget _buildRiskDistributionChart() {
    final distribution = _riskStats?['risk_distribution'] as Map<String, dynamic>? ?? {};
    
    final low = (distribution['LOW'] ?? 0).toDouble();
    final medium = (distribution['MEDIUM'] ?? 0).toDouble();
    final high = (distribution['HIGH'] ?? 0).toDouble();
    final critical = (distribution['CRITICAL'] ?? 0).toDouble();
    final total = low + medium + high + critical;

    return Container(
      margin: const EdgeInsets.all(24),
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Risk Level Distribution', style: AppTypography.h4),
          const SizedBox(height: 24),
          Row(
            children: [
              // Pie chart
              SizedBox(
                width: 200,
                height: 200,
                child: total > 0
                    ? PieChart(
                        PieChartData(
                          sectionsSpace: 2,
                          centerSpaceRadius: 40,
                          sections: [
                            PieChartSectionData(
                              value: low,
                              title: '${(low / total * 100).toStringAsFixed(0)}%',
                              color: AppColors.success,
                              radius: 60,
                              titleStyle: AppTypography.bodySmall.copyWith(color: Colors.white),
                            ),
                            PieChartSectionData(
                              value: medium,
                              title: '${(medium / total * 100).toStringAsFixed(0)}%',
                              color: AppColors.warning,
                              radius: 60,
                              titleStyle: AppTypography.bodySmall.copyWith(color: Colors.white),
                            ),
                            PieChartSectionData(
                              value: high,
                              title: '${(high / total * 100).toStringAsFixed(0)}%',
                              color: Colors.orange,
                              radius: 60,
                              titleStyle: AppTypography.bodySmall.copyWith(color: Colors.white),
                            ),
                            PieChartSectionData(
                              value: critical,
                              title: '${(critical / total * 100).toStringAsFixed(0)}%',
                              color: AppColors.error,
                              radius: 60,
                              titleStyle: AppTypography.bodySmall.copyWith(color: Colors.white),
                            ),
                          ],
                        ),
                      )
                    : Center(
                        child: Text(
                          'No data',
                          style: AppTypography.bodyMedium.copyWith(color: AppColors.textSecondary),
                        ),
                      ),
              ),
              const SizedBox(width: 48),
              // Legend
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildLegendItem('LOW (0-30)', low.toInt(), AppColors.success),
                  const SizedBox(height: 12),
                  _buildLegendItem('MEDIUM (30-60)', medium.toInt(), AppColors.warning),
                  const SizedBox(height: 12),
                  _buildLegendItem('HIGH (60-80)', high.toInt(), Colors.orange),
                  const SizedBox(height: 12),
                  _buildLegendItem('CRITICAL (80-100)', critical.toInt(), AppColors.error),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildLegendItem(String label, int count, Color color) {
    return Row(
      children: [
        Container(
          width: 16,
          height: 16,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(4),
          ),
        ),
        const SizedBox(width: 8),
        Text(label, style: AppTypography.bodyMedium),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
          decoration: BoxDecoration(
            color: color.withOpacity(0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Text(
            '$count',
            style: AppTypography.bodySmall.copyWith(color: color, fontWeight: FontWeight.bold),
          ),
        ),
      ],
    );
  }

  Widget _buildHighRiskVehiclesSection() {
    // Filter vehicles by selected risk level
    List<dynamic> filteredVehicles;
    if (_selectedRiskLevel == 'ALL') {
      filteredVehicles = _currentScores;
    } else {
      filteredVehicles = _currentScores
          .where((v) => (v['risk_level'] ?? 'LOW') == _selectedRiskLevel)
          .toList();
    }
    
    // Count per level for badges
    final counts = <String, int>{
      'ALL': _currentScores.length,
      'CRITICAL': _currentScores.where((v) => v['risk_level'] == 'CRITICAL').length,
      'HIGH': _currentScores.where((v) => v['risk_level'] == 'HIGH').length,
      'MEDIUM': _currentScores.where((v) => v['risk_level'] == 'MEDIUM').length,
      'LOW': _currentScores.where((v) => v['risk_level'] == 'LOW').length,
    };
    
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 24),
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.directions_car, color: AppColors.primary),
              const SizedBox(width: 8),
              Text('Vehicles by Risk Level', style: AppTypography.h4),
              const Spacer(),
              Text(
                '${filteredVehicles.length} vehicles',
                style: AppTypography.bodySmall.copyWith(color: AppColors.textSecondary),
              ),
            ],
          ),
          const SizedBox(height: 16),
          
          // Risk level toggle chips
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                _buildRiskFilterChip('ALL', 'All', AppColors.primary, counts['ALL'] ?? 0),
                const SizedBox(width: 8),
                _buildRiskFilterChip('CRITICAL', 'Critical', AppColors.error, counts['CRITICAL'] ?? 0),
                const SizedBox(width: 8),
                _buildRiskFilterChip('HIGH', 'High', Colors.orange, counts['HIGH'] ?? 0),
                const SizedBox(width: 8),
                _buildRiskFilterChip('MEDIUM', 'Medium', AppColors.warning, counts['MEDIUM'] ?? 0),
                const SizedBox(width: 8),
                _buildRiskFilterChip('LOW', 'Low', AppColors.success, counts['LOW'] ?? 0),
              ],
            ),
          ),
          const SizedBox(height: 16),
          
          if (filteredVehicles.isEmpty)
            Container(
              padding: const EdgeInsets.all(32),
              child: Center(
                child: Column(
                  children: [
                    Icon(
                      _selectedRiskLevel == 'ALL' ? Icons.info_outline : Icons.check_circle,
                      size: 48,
                      color: _selectedRiskLevel == 'LOW' ? AppColors.success : AppColors.textSecondary,
                    ),
                    const SizedBox(height: 12),
                    Text(
                      _selectedRiskLevel == 'ALL'
                          ? 'No vehicles tracked yet'
                          : 'No ${_selectedRiskLevel.toLowerCase()} risk vehicles detected',
                      style: AppTypography.bodyMedium.copyWith(color: AppColors.textSecondary),
                    ),
                  ],
                ),
              ),
            )
          else
            ...filteredVehicles.take(20).map((vehicle) {
              final v = vehicle is Map<String, dynamic> ? vehicle : <String, dynamic>{};
              return _buildVehicleRiskItem(v);
            }),
        ],
      ),
    );
  }
  
  Widget _buildRiskFilterChip(String level, String label, Color color, int count) {
    final isSelected = _selectedRiskLevel == level;
    return GestureDetector(
      onTap: () => setState(() => _selectedRiskLevel = level),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          color: isSelected ? color : color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(24),
          border: Border.all(
            color: isSelected ? color : color.withOpacity(0.3),
            width: isSelected ? 2 : 1,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              label,
              style: AppTypography.bodySmall.copyWith(
                color: isSelected ? Colors.white : color,
                fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
              ),
            ),
            const SizedBox(width: 6),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
              decoration: BoxDecoration(
                color: isSelected ? Colors.white.withOpacity(0.25) : color.withOpacity(0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                '$count',
                style: AppTypography.caption.copyWith(
                  color: isSelected ? Colors.white : color,
                  fontWeight: FontWeight.bold,
                  fontSize: 11,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildVehicleRiskItem(Map<String, dynamic> vehicle) {
    final riskScore = (vehicle['risk_score'] ?? 0).toDouble();
    final riskLevel = vehicle['risk_level'] ?? 'UNKNOWN';
    final behaviors = vehicle['behaviors_detected'] as List<dynamic>? ?? [];
    final plateNumber = vehicle['plate_number'] as String?;
    
    Color riskColor;
    switch (riskLevel) {
      case 'CRITICAL':
        riskColor = AppColors.error;
        break;
      case 'HIGH':
        riskColor = Colors.orange;
        break;
      case 'MEDIUM':
        riskColor = AppColors.warning;
        break;
      default:
        riskColor = AppColors.success;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: riskColor.withOpacity(0.05),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: riskColor.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          Container(
            width: 50,
            height: 50,
            decoration: BoxDecoration(
              color: riskColor,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Center(
              child: Text(
                riskScore.toStringAsFixed(0),
                style: AppTypography.h4.copyWith(color: Colors.white),
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      'Vehicle ${vehicle['vehicle_id'] ?? 'Unknown'}',
                      style: AppTypography.h5,
                    ),
                    if (plateNumber != null && plateNumber.isNotEmpty) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: AppColors.background,
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(color: AppColors.border),
                        ),
                        child: Text(
                          plateNumber,
                          style: AppTypography.caption.copyWith(fontFamily: 'monospace'),
                        ),
                      ),
                    ],
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: riskColor,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        riskLevel,
                        style: AppTypography.caption.copyWith(color: Colors.white),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  'Speed Factor: ${vehicle['speed_factor']?.toStringAsFixed(1) ?? '0'} | '
                  'History Factor: ${vehicle['violation_history_factor']?.toStringAsFixed(1) ?? '0'}',
                  style: AppTypography.bodySmall.copyWith(color: AppColors.textSecondary),
                ),
                if (behaviors.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Wrap(
                    spacing: 4,
                    children: behaviors.take(3).map((b) => Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.warning.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        b.toString(),
                        style: AppTypography.caption.copyWith(color: AppColors.warning),
                      ),
                    )).toList(),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBehaviorLogSection() {
    final behaviorTypes = _riskStats?['behavior_types'] as Map<String, dynamic>? ?? {};
    
    return Container(
      margin: const EdgeInsets.all(24),
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.psychology, color: AppColors.info),
              const SizedBox(width: 8),
              Text('Abnormal Behavior Log', style: AppTypography.h4),
              const Spacer(),
              Text(
                '${_behaviorLog.length} events',
                style: AppTypography.bodySmall.copyWith(color: AppColors.textSecondary),
              ),
            ],
          ),
          const SizedBox(height: 16),
          
          // Behavior type summary
          if (behaviorTypes.isNotEmpty)
            Row(
              children: [
                _buildBehaviorTypeChip('Sudden Stop', behaviorTypes['sudden_stop'] ?? 0, Icons.stop_circle),
                const SizedBox(width: 8),
                _buildBehaviorTypeChip('Harsh Brake', behaviorTypes['harsh_brake'] ?? 0, Icons.warning),
                const SizedBox(width: 8),
                _buildBehaviorTypeChip('Lane Drift', behaviorTypes['lane_drift'] ?? 0, Icons.swap_horiz),
                const SizedBox(width: 8),
                _buildBehaviorTypeChip('Wrong Way', behaviorTypes['wrong_way'] ?? 0, Icons.wrong_location),
              ],
            ),
          
          const SizedBox(height: 16),
          const Divider(),
          const SizedBox(height: 16),
          
          // Recent events table
          if (_behaviorLog.isEmpty)
            Container(
              padding: const EdgeInsets.all(32),
              child: Center(
                child: Text(
                  'No abnormal behavior events recorded',
                  style: AppTypography.bodyMedium.copyWith(color: AppColors.textSecondary),
                ),
              ),
            )
          else
            _buildBehaviorTable(),
        ],
      ),
    );
  }

  Widget _buildBehaviorTypeChip(String label, int count, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: AppColors.textSecondary),
          const SizedBox(width: 8),
          Text(label, style: AppTypography.bodySmall),
          const SizedBox(width: 4),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: AppColors.primary.withOpacity(0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              '$count',
              style: AppTypography.caption.copyWith(color: AppColors.primary, fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBehaviorTable() {
    return ConstrainedBox(
      constraints: const BoxConstraints(maxHeight: 500),
      child: SingleChildScrollView(
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: SizedBox(
            width: 900,
            child: Table(
              columnWidths: const {
                0: FlexColumnWidth(1),
                1: FlexColumnWidth(1),
                2: FlexColumnWidth(1.2),
                3: FlexColumnWidth(0.8),
                4: FlexColumnWidth(2),
                5: FlexColumnWidth(1.5),
              },
              children: [
                TableRow(
                  decoration: BoxDecoration(
                    color: AppColors.background,
                    border: Border(bottom: BorderSide(color: AppColors.border)),
                  ),
                  children: [
                    _buildTableHeader('Vehicle'),
                    _buildTableHeader('Plate'),
                    _buildTableHeader('Behavior'),
                    _buildTableHeader('Severity'),
                    _buildTableHeader('Details'),
                    _buildTableHeader('Timestamp'),
                  ],
                ),
                ..._behaviorLog.map((event) => TableRow(
                  decoration: BoxDecoration(
                    border: Border(bottom: BorderSide(color: AppColors.border.withOpacity(0.5))),
                  ),
                  children: [
                    _buildTableCell('${event['vehicle_id'] ?? 'N/A'}'),
                    _buildTableCell('${event['plate_number'] ?? '-'}'),
                    _buildTableCell(_formatBehaviorType(event['behavior_type'] ?? '')),
                    _buildSeverityCell(event['severity'] ?? 'medium'),
                    _buildDetailsCell(event['behavior_type'] ?? '', event['details']),
                    _buildTableCell(_formatTimestamp(event['timestamp'] ?? '')),
                  ],
                )),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildDetailsCell(String behaviorType, dynamic details) {
    String text = '-';
    if (details != null && details is Map) {
      switch (behaviorType) {
        case 'sudden_stop':
          final before = details['speed_before'];
          final after = details['speed_after'];
          final drop = details['drop_percent'];
          if (before != null && after != null) {
            text = '${_num(before)} → ${_num(after)} km/h';
            if (drop != null) text += ' (${_num(drop)}% drop)';
          }
          break;
        case 'harsh_brake':
          final decel = details['deceleration'];
          if (decel != null) text = 'Decel: ${_num(decel)} px/f²';
          break;
        case 'lane_drift':
          final variance = details['x_variance'];
          final drift = details['drift_from_center'];
          if (variance != null) {
            text = 'Variance: ${_num(variance)}';
            if (drift != null) text += ', Drift: ${_num(drift)}px';
          }
          break;
        default:
          final entries = details.entries.take(2);
          if (entries.isNotEmpty) {
            text = entries.map((e) => '${e.key}: ${e.value}').join(', ');
          }
      }
    }
    return TableCell(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Text(
          text,
          style: AppTypography.tableCell.copyWith(fontSize: 11),
          overflow: TextOverflow.ellipsis,
          maxLines: 2,
        ),
      ),
    );
  }

  String _num(dynamic value) {
    if (value is double) return value.toStringAsFixed(1);
    return value.toString();
  }

  Widget _buildTableHeader(String text) {
    return TableCell(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Text(
          text,
          style: AppTypography.tableHeader,
        ),
      ),
    );
  }

  Widget _buildTableCell(String text) {
    return TableCell(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Text(
          text,
          style: AppTypography.tableCell,
        ),
      ),
    );
  }

  Widget _buildSeverityCell(String severity) {
    Color color;
    switch (severity.toLowerCase()) {
      case 'critical':
        color = AppColors.error;
        break;
      case 'high':
        color = Colors.orange;
        break;
      case 'medium':
        color = AppColors.warning;
        break;
      default:
        color = AppColors.success;
    }
    
    return TableCell(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: color.withOpacity(0.1),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Text(
            severity.toUpperCase(),
            style: AppTypography.caption.copyWith(color: color, fontWeight: FontWeight.bold),
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }

  String _formatBehaviorType(String type) {
    return type
        .split('_')
        .map((word) => word.isNotEmpty ? '${word[0].toUpperCase()}${word.substring(1)}' : '')
        .join(' ');
  }

  String _formatTimestamp(String timestamp) {
    try {
      final dt = DateTime.parse(timestamp);
      return '${dt.day}/${dt.month} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (e) {
      return timestamp;
    }
  }
}
