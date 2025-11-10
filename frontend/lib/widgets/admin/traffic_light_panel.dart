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
