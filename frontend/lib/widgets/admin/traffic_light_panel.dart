import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/config/app_config.dart';

class TrafficLightPanel extends StatefulWidget {
  const TrafficLightPanel({super.key});

  @override
  State<TrafficLightPanel> createState() => _TrafficLightPanelState();
}

class _TrafficLightPanelState extends State<TrafficLightPanel> 
    with TickerProviderStateMixin {
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;
  Timer? _pollTimer;
  
  // Signal state from backend (all 4 junctions coordinated)
  TrafficLightState _currentState = TrafficLightState.green;
  String _currentGreenLane = 'north';
  int _countdown = 45;
  bool _isManualOverride = false;
  bool _emergencyMode = false;
  bool _isYellowPhase = false;
  int _yellowRemaining = 0;
  Map<String, dynamic> _laneData = {};
  
  // Junction name mappings (backend lanes -> frontend junction names)
  static const Map<String, String> _laneToJunction = {
    'north': 'Junction A (North)',
    'south': 'Junction B (South)',
    'east': 'Junction C (East)',
    'west': 'Junction D (West)',
  };

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1000),
      vsync: this,
    )..repeat(reverse: true);
    
    _pulseAnimation = Tween<double>(begin: 0.8, end: 1.2).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
    
    // Fetch initial state and start polling
    _fetchSignalStatus();
    _startPolling();
  }

  void _startPolling() {
    // Poll every 3 seconds to reduce connection usage
    _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) {
      _fetchSignalStatus();
      // No more independent simulation - all 4 junctions use backend data
    });
  }

  Future<void> _fetchSignalStatus() async {
    try {
      final response = await http.get(
        Uri.parse('${AppConfig.apiBaseUrl}/signal/4way/status'),
      );
      
      if (response.statusCode == 200 && mounted) {
        final data = json.decode(response.body);
        setState(() {
          _currentGreenLane = data['current_green'] ?? 'north';
          _countdown = data['green_remaining'] ?? 0;
          _emergencyMode = data['emergency_mode'] ?? false;
          _isYellowPhase = data['is_yellow_phase'] ?? false;
          _yellowRemaining = data['yellow_remaining'] ?? 0;
          _laneData = data['lanes'] ?? {};
          
          // FIX: Main light ALWAYS shows NORTH lane state (the video feed)
          // This ensures the main light matches what's visible in the video
          final northLaneData = _laneData['north'];
          if (northLaneData != null) {
            final stateStr = northLaneData['state'] ?? 'red';
            if (stateStr == 'red') {
              _currentState = TrafficLightState.red;
            } else if (stateStr == 'yellow') {
              _currentState = TrafficLightState.yellow;
            } else {
              _currentState = TrafficLightState.green;
            }
          }
        });
      }
    } catch (e) {
      // Keep last known state on error
      debugPrint('[TrafficLight] Error fetching status: $e');
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildHeader(),
          const SizedBox(height: 16),
          
          // Main junction - Full traffic light
          _buildMainJunction(),
          const SizedBox(height: 16),
          
          // Timer for main junction
          _buildTimer(),
          const SizedBox(height: 16),
          
          // Divider
          Divider(color: AppColors.border, height: 1),
          const SizedBox(height: 12),
          
          // Other junctions label
          Text(
            'Other Junctions',
            style: AppTypography.caption.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 8),
          
          // 3 simulated junctions in a row
          _buildSimulatedJunctions(),
          const SizedBox(height: 16),
          
          // Controls
          _buildControls(),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Flexible(
              child: Text('Signal Control', style: AppTypography.h4, overflow: TextOverflow.ellipsis),
            ),
            const SizedBox(width: 4),
            if (_emergencyMode)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: Colors.red.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  '🚨',
                  style: AppTypography.caption.copyWith(fontSize: 10),
                ),
              ),
            if (_isManualOverride && !_emergencyMode)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: AppColors.warning.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  'MANUAL',
                  style: AppTypography.caption.copyWith(
                    color: AppColors.warning,
                    fontWeight: FontWeight.bold,
                    fontSize: 9,
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: 2),
        // FIX: Always show NORTH lane status (matches the video feed)
        Text(
          'North Lane: ${_currentState.name.toUpperCase()}',
          style: AppTypography.caption.copyWith(
            color: _getStateColor(),
            fontWeight: FontWeight.bold,
            fontSize: 10,
          ),
        ),
      ],
    );
  }

  Widget _buildMainJunction() {
    return Center(
      child: Column(
        children: [
          // FIX: Main light is always NORTH - the video feed lane
          Text(
            'North Lane (Video Feed)',
            style: AppTypography.caption.copyWith(
              color: AppColors.primary,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFF2A2A2A),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.primary, width: 2),
              boxShadow: [
                BoxShadow(
                  color: AppColors.primary.withOpacity(0.3),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Column(
              children: [
                _buildLight(
                  color: Colors.red,
                  isActive: _currentState == TrafficLightState.red,
                  size: 40,
                ),
                const SizedBox(height: 8),
                _buildLight(
                  color: Colors.amber,
                  isActive: _currentState == TrafficLightState.yellow,
                  size: 40,
                ),
                const SizedBox(height: 8),
                _buildLight(
                  color: Colors.green,
                  isActive: _currentState == TrafficLightState.green,
                  size: 40,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
  
  Widget _buildSimulatedJunctions() {
    // Show south, east, west lanes from backend (all coordinated)
    final otherLanes = ['south', 'east', 'west'];
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: otherLanes.map((lane) {
        final laneInfo = _laneData[lane];
        final stateStr = laneInfo?['state'] ?? 'red';
        final state = stateStr == 'green' ? TrafficLightState.green
            : stateStr == 'yellow' ? TrafficLightState.yellow
            : TrafficLightState.red;
        final junctionName = _laneToJunction[lane] ?? 'Junction';
        final isCurrentGreen = laneInfo?['is_current_green'] ?? false;
        
        return _buildMiniJunction(junctionName, state, isCurrentGreen, lane);
      }).toList(),
    );
  }
  
  Widget _buildMiniJunction(String name, TrafficLightState state, bool isCurrentGreen, String lane) {
    Color activeColor;
    switch (state) {
      case TrafficLightState.red:
        activeColor = Colors.red;
        break;
      case TrafficLightState.yellow:
        activeColor = Colors.amber;
        break;
      case TrafficLightState.green:
        activeColor = Colors.green;
        break;
    }
    
    // Display short name (just the letter)
    final shortName = name.split(' ')[1];  // e.g., "Junction B (South)" -> "B"
    final directionName = name.split('(').last.replaceAll(')', '');  // e.g., "South"
    
    return Column(
      children: [
        Text(
          '$shortName ($directionName)',
          style: AppTypography.caption.copyWith(
            color: isCurrentGreen ? AppColors.primary : AppColors.textSecondary,
            fontSize: 9,
            fontWeight: isCurrentGreen ? FontWeight.bold : FontWeight.normal,
          ),
        ),
        const SizedBox(height: 4),
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: const Color(0xFF2A2A2A),
            borderRadius: BorderRadius.circular(8),
            border: isCurrentGreen 
                ? Border.all(color: AppColors.primary, width: 1)
                : null,
          ),
          child: AnimatedBuilder(
            animation: _pulseAnimation,
            builder: (context, child) {
              return Container(
                width: 28,
                height: 28,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: activeColor,
                  boxShadow: [
                    BoxShadow(
                      color: activeColor.withOpacity(0.6),
                      blurRadius: 12 * _pulseAnimation.value,
                      spreadRadius: 2 * _pulseAnimation.value,
                    ),
                  ],
                ),
              );
            },
          ),
        ),
        const SizedBox(height: 2),
        // Show countdown only for current green lane
        if (isCurrentGreen)
          Text(
            '${_countdown}s',
            style: AppTypography.caption.copyWith(
              color: activeColor,
              fontSize: 9,
              fontFamily: 'monospace',
            ),
          )
        else
          Text(
            state == TrafficLightState.red ? 'WAIT' : '',
            style: AppTypography.caption.copyWith(
              color: AppColors.textSecondary,
              fontSize: 8,
