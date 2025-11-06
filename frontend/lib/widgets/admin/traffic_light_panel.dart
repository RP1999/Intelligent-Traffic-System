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
