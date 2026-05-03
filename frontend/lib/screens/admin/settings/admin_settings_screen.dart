import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../providers/auth_provider.dart';
import '../../../widgets/admin/admin_sidebar.dart';

/// Admin Settings Screen
/// Allows configuration of fines, penalties, and detection thresholds.
/// Fine Formula: Base Penalty + (Duration × Rate) + (Traffic Impact × Cost)
class AdminSettingsScreen extends StatefulWidget {
  const AdminSettingsScreen({super.key});

  @override
  State<AdminSettingsScreen> createState() => _AdminSettingsScreenState();
}

class _AdminSettingsScreenState extends State<AdminSettingsScreen> {
  final ApiClient _apiClient = ApiClient();
  
  bool _isLoading = true;
  bool _isSaving = false;
  Map<String, dynamic>? _settings;
  int _selectedTab = 0;

  // Controllers for Fine Settings
  final Map<String, TextEditingController> _fineControllers = {};
  final Map<String, TextEditingController> _pointsControllers = {};
  
  // Controllers for Junction Safety
  final _junctionDecayRateController = TextEditingController();
  final _junctionInitialScoreController = TextEditingController();
  final _junctionMinScoreController = TextEditingController();
  final _junctionMaxScoreController = TextEditingController();
  final Map<String, TextEditingController> _junctionPenaltyControllers = {};
  
  // Controllers for Detection Settings
  final _speedLimitController = TextEditingController();
  final _stopLineYController = TextEditingController();
  final _yellowLightDurationController = TextEditingController();
  final _xVelocityThresholdController = TextEditingController();
  final _directionChangesController = TextEditingController();
  final _wrongWayAngleController = TextEditingController();
  
  // Controllers for Parking Settings
  final _gracePeriodController = TextEditingController();
  final _durationRateController = TextEditingController();
  final _trafficImpactCostController = TextEditingController();
  final _maxDurationPenaltyController = TextEditingController();

  final List<String> _violationTypes = [
    'parking_no_parking',
    'parking_no_stopping',
    'parking_overtime',
    'parking_handicap',
    'parking_loading',
    'speeding',
    'red_light',
    'wrong_way',
    'lane_weaving',
  ];
  
  final List<String> _junctionPenaltyTypes = [
    'lane_weaving',
    'wrong_way',
    'speeding',
    'parking_violation',
    'running_red_light',
    'tailgating',
  ];

  @override
  void initState() {
    super.initState();
    _initControllers();
    _loadSettings();
  }

  void _initControllers() {
    for (final type in _violationTypes) {
      _fineControllers[type] = TextEditingController();
      _pointsControllers[type] = TextEditingController();
    }
    for (final type in _junctionPenaltyTypes) {
      _junctionPenaltyControllers[type] = TextEditingController();
    }
  }

  @override
  void dispose() {
    for (final c in _fineControllers.values) { c.dispose(); }
    for (final c in _pointsControllers.values) { c.dispose(); }
    for (final c in _junctionPenaltyControllers.values) { c.dispose(); }
    _junctionDecayRateController.dispose();
    _junctionInitialScoreController.dispose();
    _junctionMinScoreController.dispose();
    _junctionMaxScoreController.dispose();
    _speedLimitController.dispose();
    _stopLineYController.dispose();
    _yellowLightDurationController.dispose();
    _xVelocityThresholdController.dispose();
    _directionChangesController.dispose();
    _wrongWayAngleController.dispose();
    _gracePeriodController.dispose();
    _durationRateController.dispose();
    _trafficImpactCostController.dispose();
    _maxDurationPenaltyController.dispose();
    super.dispose();
  }

  void _handleUnauthorized() {
    if (!mounted) return;
    Navigator.of(context).pushNamedAndRemoveUntil('/platform-router', (route) => false);
  }

  Future<void> _loadSettings() async {
    if (!mounted) return;
    setState(() => _isLoading = true);
    
    try {
      final response = await _apiClient.get(ApiEndpoints.systemSettings);
      if (!mounted) return;
      
      if (response.success && response.data != null) {
        setState(() {
          _settings = response.data;
          _populateControllers();
          _isLoading = false;
        });
      } else {
        _showError(response.error ?? 'Failed to load settings');
        setState(() => _isLoading = false);
      }
    } on UnauthorizedException {
      _handleUnauthorized();
    } catch (e) {
      if (!mounted) return;
      _showError('Error loading settings: $e');
      setState(() => _isLoading = false);
    }
  }

  void _populateControllers() {
    if (_settings == null) return;
    
    // Populate fine settings
    final fines = _settings!['fines'] as Map<String, dynamic>?;
    if (fines != null) {
      for (final type in _violationTypes) {
        final penalty = fines[type] as Map<String, dynamic>?;
        if (penalty != null) {
          _fineControllers[type]?.text = (penalty['fine'] ?? 0).toString();
          _pointsControllers[type]?.text = (penalty['points'] ?? 0).toString();
        }
      }
    }
    
    // Populate junction safety settings
    final junction = _settings!['junction_safety'] as Map<String, dynamic>?;
    if (junction != null) {
      _junctionDecayRateController.text = (junction['score_decay_rate'] ?? 0.1).toString();
      _junctionInitialScoreController.text = (junction['initial_score'] ?? 100).toString();
      _junctionMinScoreController.text = (junction['min_score'] ?? 0).toString();
      _junctionMaxScoreController.text = (junction['max_score'] ?? 100).toString();
      _junctionPenaltyControllers['lane_weaving']?.text = (junction['lane_weaving_penalty'] ?? 5).toString();
      _junctionPenaltyControllers['wrong_way']?.text = (junction['wrong_way_penalty'] ?? 20).toString();
      _junctionPenaltyControllers['speeding']?.text = (junction['speeding_penalty'] ?? 8).toString();
      _junctionPenaltyControllers['parking_violation']?.text = (junction['parking_violation_penalty'] ?? 10).toString();
      _junctionPenaltyControllers['running_red_light']?.text = (junction['running_red_light_penalty'] ?? 25).toString();
      _junctionPenaltyControllers['tailgating']?.text = (junction['tailgating_penalty'] ?? 3).toString();
    }
    
    // Populate detection settings
    final detection = _settings!['detection'] as Map<String, dynamic>?;
    if (detection != null) {
      _speedLimitController.text = (detection['speed_limit'] ?? 60).toString();
      _stopLineYController.text = (detection['stop_line_y_position'] ?? 400).toString();
      _yellowLightDurationController.text = (detection['yellow_light_duration'] ?? 3).toString();
      _xVelocityThresholdController.text = (detection['x_velocity_threshold'] ?? 15).toString();
      _directionChangesController.text = (detection['direction_changes_threshold'] ?? 3).toString();
      _wrongWayAngleController.text = (detection['wrong_way_angle_threshold'] ?? 120).toString();
    }
    
    // Populate parking settings
    final parking = _settings!['parking'] as Map<String, dynamic>?;
    if (parking != null) {
      _gracePeriodController.text = (parking['grace_period_seconds'] ?? 30).toString();
      _durationRateController.text = (parking['duration_rate_per_minute'] ?? 100).toString();
      _trafficImpactCostController.text = (parking['traffic_impact_cost'] ?? 500).toString();
      _maxDurationPenaltyController.text = (parking['max_duration_penalty'] ?? 10000).toString();
    }
  }

  Map<String, dynamic> _buildSettingsPayload() {
    return {
      'fines': {
        for (final type in _violationTypes)
          type: {
            'points': int.tryParse(_pointsControllers[type]?.text ?? '0') ?? 0,
            'fine': double.tryParse(_fineControllers[type]?.text ?? '0') ?? 0.0,
            'severity': _getSeverity(type),
          },
      },
      'junction_safety': {
        'initial_score': int.tryParse(_junctionInitialScoreController.text) ?? 100,
        'min_score': int.tryParse(_junctionMinScoreController.text) ?? 0,
        'max_score': int.tryParse(_junctionMaxScoreController.text) ?? 100,
        'score_decay_rate': double.tryParse(_junctionDecayRateController.text) ?? 0.1,
        'lane_weaving_penalty': int.tryParse(_junctionPenaltyControllers['lane_weaving']?.text ?? '5') ?? 5,
        'wrong_way_penalty': int.tryParse(_junctionPenaltyControllers['wrong_way']?.text ?? '20') ?? 20,
        'speeding_penalty': int.tryParse(_junctionPenaltyControllers['speeding']?.text ?? '8') ?? 8,
        'parking_violation_penalty': int.tryParse(_junctionPenaltyControllers['parking_violation']?.text ?? '10') ?? 10,
        'running_red_light_penalty': int.tryParse(_junctionPenaltyControllers['running_red_light']?.text ?? '25') ?? 25,
        'tailgating_penalty': int.tryParse(_junctionPenaltyControllers['tailgating']?.text ?? '3') ?? 3,
      },
      'detection': {
        'speed_limit': double.tryParse(_speedLimitController.text) ?? 60.0,
        'stop_line_y_position': int.tryParse(_stopLineYController.text) ?? 400,
        'yellow_light_duration': double.tryParse(_yellowLightDurationController.text) ?? 3.0,
        'x_velocity_threshold': double.tryParse(_xVelocityThresholdController.text) ?? 15.0,
        'direction_changes_threshold': int.tryParse(_directionChangesController.text) ?? 3,
        'wrong_way_angle_threshold': int.tryParse(_wrongWayAngleController.text) ?? 120,
      },
      'parking': {
        'grace_period_seconds': int.tryParse(_gracePeriodController.text) ?? 30,
        'duration_rate_per_minute': double.tryParse(_durationRateController.text) ?? 100.0,
        'traffic_impact_cost': double.tryParse(_trafficImpactCostController.text) ?? 500.0,
        'max_duration_penalty': double.tryParse(_maxDurationPenaltyController.text) ?? 10000.0,
      },
    };
  }

  String _getSeverity(String type) {
    switch (type) {
      case 'parking_overtime':
      case 'parking_loading':
        return 'low';
      case 'parking_no_parking':
      case 'parking_no_stopping':
      case 'speeding':
      case 'lane_weaving':
        return 'medium';
      case 'parking_handicap':
      case 'red_light':
        return 'high';
      case 'wrong_way':
        return 'critical';
      default:
        return 'medium';
    }
  }

  Future<void> _saveSettings() async {
    setState(() => _isSaving = true);
    
    try {
      final payload = _buildSettingsPayload();
      final response = await _apiClient.put(ApiEndpoints.systemSettings, body: payload);
      
      if (!mounted) return;
      
      if (response.success) {
        _showSuccess('Settings saved successfully');
        setState(() {
          _settings = response.data;
          _isSaving = false;
        });
      } else {
        _showError(response.error ?? 'Failed to save settings');
        setState(() => _isSaving = false);
      }
    } on UnauthorizedException {
      _handleUnauthorized();
    } catch (e) {
      if (!mounted) return;
      _showError('Error saving settings: $e');
      setState(() => _isSaving = false);
    }
  }

  Future<void> _resetSettings() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Reset Settings'),
        content: const Text('Reset all settings to default values? This cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.error),
            child: const Text('Reset'),
          ),
        ],
      ),
    );
    
    if (confirmed != true) return;
    
    setState(() => _isSaving = true);
    
    try {
      final response = await _apiClient.post(ApiEndpoints.resetSettings, body: {});
      
      if (!mounted) return;
      
      if (response.success) {
        _showSuccess('Settings reset to defaults');
        setState(() {
          _settings = response.data;
          _populateControllers();
          _isSaving = false;
        });
      } else {
        _showError(response.error ?? 'Failed to reset settings');
        setState(() => _isSaving = false);
      }
    } on UnauthorizedException {
      _handleUnauthorized();
    } catch (e) {
      if (!mounted) return;
      _showError('Error resetting settings: $e');
      setState(() => _isSaving = false);
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: AppColors.error,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  void _showSuccess(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: AppColors.success,
        behavior: SnackBarBehavior.floating,
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
        Navigator.of(context).pushReplacementNamed('/admin/risk');
        break;
      case 7:
        // Already on settings
        break;
      case 8:
        Navigator.of(context).pushReplacementNamed('/admin/iot-junction');
        break;
    }
  }

  Future<void> _handleLogout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Confirm Logout'),
        content: const Text('Are you sure you want to logout?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.error),
            child: const Text('Logout'),
          ),
        ],
      ),
    );
    
    if (confirmed == true && mounted) {
      await context.read<AuthProvider>().logout();
      Navigator.of(context).pushReplacementNamed('/');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          AdminSidebar(
            selectedIndex: 7, // Settings is at index 7
            onItemSelected: _handleNavigation,
          ),
          Expanded(
            child: Container(
              color: AppColors.background,
              child: _isLoading
                  ? const Center(child: CircularProgressIndicator())
                  : _buildMainContent(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMainContent() {
    return Column(
      children: [
        // Header
        Container(
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: AppColors.surface,
            border: Border(bottom: BorderSide(color: AppColors.border)),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('System Settings', style: AppTypography.h1),
                  const SizedBox(height: 4),
                  Text(
                    'Configure fines, penalties, and detection thresholds',
                    style: AppTypography.bodyMedium.copyWith(color: AppColors.textSecondary),
                  ),
                ],
              ),
              Row(
                children: [
                  OutlinedButton.icon(
                    onPressed: _isSaving ? null : _resetSettings,
                    icon: const Icon(Icons.restore),
                    label: const Text('Reset to Defaults'),
                  ),
                  const SizedBox(width: 12),
                  ElevatedButton.icon(
                    onPressed: _isSaving ? null : _saveSettings,
                    icon: _isSaving
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Icon(Icons.save),
                    label: Text(_isSaving ? 'Saving...' : 'Save Changes'),
                  ),
                ],
              ),
            ],
          ),
        ),
        
        // Tabs
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          decoration: BoxDecoration(
            color: AppColors.surface,
            border: Border(bottom: BorderSide(color: AppColors.border)),
          ),
          child: Row(
            children: [
              _buildTab(0, 'Fines & Penalties', Icons.monetization_on),
              _buildTab(1, 'Junction Safety', Icons.traffic),
              _buildTab(2, 'Detection', Icons.videocam),
              _buildTab(3, 'Parking', Icons.local_parking),
            ],
          ),
        ),
        
        // Tab Content
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: _buildTabContent(),
          ),
        ),
      ],
    );
  }

  Widget _buildTab(int index, String title, IconData icon) {
    final isSelected = _selectedTab == index;
    return InkWell(
      onTap: () => setState(() => _selectedTab = index),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              color: isSelected ? AppColors.primary : Colors.transparent,
              width: 2,
            ),
          ),
        ),
        child: Row(
          children: [
            Icon(
              icon,
              size: 20,
              color: isSelected ? AppColors.primary : AppColors.textSecondary,
            ),
            const SizedBox(width: 8),
            Text(
              title,
              style: AppTypography.bodyMedium.copyWith(
                color: isSelected ? AppColors.primary : AppColors.textSecondary,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTabContent() {
    switch (_selectedTab) {
      case 0:
        return _buildFinesTab();
      case 1:
        return _buildJunctionSafetyTab();
      case 2:
        return _buildDetectionTab();
      case 3:
        return _buildParkingTab();
      default:
        return _buildFinesTab();
    }
  }

  Widget _buildFinesTab() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionHeader(
          'Violation Fines & Penalty Points',
          'Configure the base fine (LKR) and points deducted for each violation type',
        ),
        const SizedBox(height: 16),
        _buildCard(
          child: Table(
            columnWidths: const {
              0: FlexColumnWidth(2),
              1: FlexColumnWidth(1),
              2: FlexColumnWidth(1),
              3: FlexColumnWidth(1),
            },
            children: [
              TableRow(
                decoration: BoxDecoration(color: AppColors.background),
                children: [
                  _buildTableHeader('Violation Type'),
                  _buildTableHeader('Fine (LKR)'),
                  _buildTableHeader('Points'),
                  _buildTableHeader('Severity'),
                ],
              ),
              ..._violationTypes.map((type) => _buildFineRow(type)),
            ],
          ),
        ),
      ],
    );
  }

  TableRow _buildFineRow(String type) {
    return TableRow(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Text(_formatViolationType(type), style: AppTypography.bodyMedium),
        ),
        Padding(
          padding: const EdgeInsets.all(8),
          child: TextField(
            controller: _fineControllers[type],
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              isDense: true,
              prefixText: 'LKR ',
              border: OutlineInputBorder(),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(8),
          child: TextField(
            controller: _pointsControllers[type],
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              isDense: true,
              border: OutlineInputBorder(),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(12),
          child: _buildSeverityChip(_getSeverity(type)),
        ),
      ],
    );
  }

  Widget _buildJunctionSafetyTab() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionHeader(
          'Junction Safety Scoring (LiveSafeScore)',
          'Configure penalties for the real-time junction safety score (0-100)',
        ),
        const SizedBox(height: 16),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: _buildCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Scoring Configuration', style: AppTypography.h4),
                    const SizedBox(height: 16),
                    _buildFormField(
                      'Initial Safety Score',
                      'Starting score for a junction',
                      _junctionInitialScoreController,
                      suffix: 'pts',
                    ),
                    const SizedBox(height: 8),
                    _buildFormField(
                      'Minimum Score',
                      'Lowest possible score',
                      _junctionMinScoreController,
                      suffix: 'pts',
                    ),
                    const SizedBox(height: 8),
                    _buildFormField(
                      'Maximum Score',
                      'Highest possible score',
                      _junctionMaxScoreController,
                      suffix: 'pts',
                    ),
                    const SizedBox(height: 8),
                    _buildFormField(
                      'Score Recovery Rate',
                      'Points recovered per second',
                      _junctionDecayRateController,
                      suffix: 'pts/sec',
                    ),
                    const SizedBox(height: 24),
                    Text('Penalty Points per Incident', style: AppTypography.h5),
                    const SizedBox(height: 12),
                    ...['lane_weaving', 'wrong_way', 'speeding', 'parking_violation', 'running_red_light', 'tailgating']
                        .map((type) => Column(
                              children: [
                                _buildFormField(
                                  _formatViolationType(type),
                                  '',
                                  _junctionPenaltyControllers[type]!,
                                  suffix: 'points',
                                ),
                                const SizedBox(height: 8),
                              ],
                            )),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 24),
            Expanded(
              child: _buildCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Formula Reference', style: AppTypography.h4),
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: AppColors.background,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: AppColors.border),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'LiveSafeScore Calculation',
                            style: AppTypography.h5.copyWith(color: AppColors.primary),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Score = 100 - (Violation_Penalty × Decay_Factor)',
                            style: AppTypography.bodyMedium.copyWith(fontFamily: 'monospace'),
                          ),
                          const SizedBox(height: 16),
                          const Text('• Score ranges from 0 (dangerous) to 100 (safe)'),
                          const Text('• Penalties deducted on each violation detection'),
                          const Text('• Score recovers over time based on decay rate'),
                          const Text('• Displayed on community dashboards and alerts'),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildDetectionTab() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionHeader(
          'Detection Thresholds',
          'Configure YOLO detection thresholds and traffic parameters',
        ),
        const SizedBox(height: 16),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: _buildCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Traffic Parameters', style: AppTypography.h4),
                    const SizedBox(height: 16),
                    _buildFormField(
                      'Speed Limit',
                      'Maximum allowed speed',
                      _speedLimitController,
                      suffix: 'km/h',
                    ),
                    const SizedBox(height: 12),
                    _buildFormField(
                      'Stop Line Y Position',
                      'Pixel position of stop line',
                      _stopLineYController,
                      suffix: 'px',
                    ),
                    const SizedBox(height: 12),
                    _buildFormField(
                      'Yellow Light Duration',
                      'Duration of yellow phase',
                      _yellowLightDurationController,
                      suffix: 'seconds',
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 24),
            Expanded(
              child: _buildCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Lane Weaving Detection', style: AppTypography.h4),
                    const SizedBox(height: 16),
                    _buildFormField(
                      'X Velocity Threshold',
                      'Lateral movement threshold',
                      _xVelocityThresholdController,
                      suffix: 'px/frame',
                    ),
                    const SizedBox(height: 12),
                    _buildFormField(
                      'Direction Changes',
                      'Min changes to detect weaving',
                      _directionChangesController,
                      suffix: 'changes',
                    ),
                    const SizedBox(height: 12),
                    _buildFormField(
                      'Wrong-Way Angle',
                      'Deviation from expected direction',
                      _wrongWayAngleController,
                      suffix: 'degrees',
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildParkingTab() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionHeader(
          'Parking Violation Settings',
          'Configure dynamic fine calculation parameters',
        ),
        const SizedBox(height: 16),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: _buildCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Fine Calculation Parameters', style: AppTypography.h4),
                    const SizedBox(height: 16),
                    _buildFormField(
                      'Grace Period',
                      'Warning period before violation',
                      _gracePeriodController,
                      suffix: 'seconds',
                    ),
                    const SizedBox(height: 12),
                    _buildFormField(
                      'Duration Rate',
                      'Fine per minute over limit',
                      _durationRateController,
                      suffix: 'LKR/min',
                    ),
                    const SizedBox(height: 12),
                    _buildFormField(
                      'Traffic Impact Cost',
                      'Multiplier for traffic impact',
                      _trafficImpactCostController,
                      suffix: 'LKR',
                    ),
                    const SizedBox(height: 12),
                    _buildFormField(
                      'Max Duration Penalty',
                      'Cap on duration penalty',
                      _maxDurationPenaltyController,
                      suffix: 'LKR',
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 24),
            Expanded(
              child: _buildCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Formula Reference', style: AppTypography.h4),
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: AppColors.background,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: AppColors.border),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Dynamic Fine Calculation',
                            style: AppTypography.h5.copyWith(color: AppColors.primary),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Fine = Base + (Duration × Rate) + (Impact × Cost)',
                            style: AppTypography.bodyMedium.copyWith(fontFamily: 'monospace'),
                          ),
                          const Divider(height: 24),
                          Text(
                            'Formula Reference:',
                            style: AppTypography.h5,
                          ),
                          const SizedBox(height: 8),
                          const Text('• Base Penalty: Type-specific base fine'),
                          const Text('• Duration: Minutes exceeding grace period'),
                          const Text('• Rate: LKR charged per minute'),
                          const Text('• Traffic Impact: 0-1 congestion factor'),
                          const Text('• Cost: Multiplier for traffic disruption'),
                          const SizedBox(height: 16),
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: AppColors.warning.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Row(
                              children: [
                                Icon(Icons.info_outline, color: AppColors.warning, size: 20),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    '30-second grace period with warning before violation',
                                    style: AppTypography.bodySmall,
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
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildSectionHeader(String title, String subtitle) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: AppTypography.h3),
        const SizedBox(height: 4),
        Text(
          subtitle,
          style: AppTypography.bodyMedium.copyWith(color: AppColors.textSecondary),
        ),
      ],
    );
  }

  Widget _buildCard({required Widget child}) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: child,
    );
  }

  Widget _buildTableHeader(String text) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Text(
        text,
        style: AppTypography.labelLarge.copyWith(color: AppColors.textSecondary),
      ),
    );
  }

  Widget _buildFormField(
    String label,
    String hint,
    TextEditingController controller, {
    String? suffix,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: AppTypography.labelMedium),
        if (hint.isNotEmpty) ...[
          const SizedBox(height: 2),
          Text(hint, style: AppTypography.bodySmall.copyWith(color: AppColors.textSecondary)),
        ],
        const SizedBox(height: 6),
        TextField(
          controller: controller,
          keyboardType: TextInputType.number,
          decoration: InputDecoration(
            isDense: true,
            suffixText: suffix,
            border: const OutlineInputBorder(),
          ),
        ),
      ],
    );
  }

  Widget _buildSeverityChip(String severity) {
    Color color;
    switch (severity) {
      case 'low':
        color = AppColors.success;
        break;
      case 'medium':
        color = AppColors.warning;
        break;
      case 'high':
        color = AppColors.error;
        break;
      case 'critical':
        color = Colors.deepPurple;
        break;
      default:
        color = AppColors.textSecondary;
    }
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Text(
        severity.toUpperCase(),
        style: AppTypography.labelSmall.copyWith(color: color),
      ),
    );
  }

  String _formatViolationType(String type) {
    return type
        .replaceAll('_', ' ')
        .split(' ')
        .map((word) => word[0].toUpperCase() + word.substring(1))
        .join(' ');
  }
}
