import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/config/app_config.dart';

class LiveVideoFeed extends StatefulWidget {
  final VoidCallback? onZoneEditorPressed;

  const LiveVideoFeed({
    super.key,
    this.onZoneEditorPressed,
  });

  @override
  State<LiveVideoFeed> createState() => _LiveVideoFeedState();
}

class _LiveVideoFeedState extends State<LiveVideoFeed> {
  WebSocketChannel? _channel;
  StreamSubscription? _streamSubscription;
  Uint8List? _currentFrame;
  bool _isStreaming = false;
  bool _isConnecting = false;
  bool _hasError = false;
  String _errorMessage = '';
  int _vehicleCount = 0;
  int _totalDetections = 0;
  int _frameCount = 0;
  DateTime _startTime = DateTime.now();
  DateTime _currentTime = DateTime.now();
  Timer? _clockTimer;
  Timer? _reconnectTimer;
  Timer? _statsTimer;
  
  // FIX: User pause flag - don't auto-reconnect if user clicked Pause
  bool _userPaused = false;

  // WebSocket URL - use localhost to avoid connection pool issues
  String get _wsUrl => '${AppConfig.videoBaseUrl.replaceFirst('http', 'ws')}/video/ws';

  @override
  void initState() {
    super.initState();
    debugPrint('[VideoFeed] initState() called');
    _startClock();
    _startStatsTimer();
    _connectWebSocket();
  }

  void _startClock() {
    _clockTimer?.cancel();
    _clockTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) {
        setState(() {
          _currentTime = DateTime.now();
        });
      }
    });
  }

  /// FIX: Stats timer to fetch /video/status every 1 second for vehicle count updates
  void _startStatsTimer() {
    _statsTimer?.cancel();
    _statsTimer = Timer.periodic(const Duration(seconds: 1), (_) async {
      if (!mounted || !_isStreaming) return;
      
      try {
        final response = await http.get(
          Uri.parse('${AppConfig.videoBaseUrl}/video/status'),
        ).timeout(const Duration(seconds: 2));
        
        if (!mounted) return;
        
        if (response.statusCode == 200) {
          final data = json.decode(response.body);
          final detections = data['total_detections'] ?? 0;
          final frames = data['frames_processed'] ?? 1;
          
          setState(() {
            _totalDetections = detections;
            // Calculate average vehicle count from detections
            _vehicleCount = frames > 0 ? (detections / frames).round() : 0;
          });
        }
      } catch (e) {
        debugPrint('[VideoFeed] Stats fetch error: $e');
        // Don't update state on error - just log
      }
    });
    debugPrint('[VideoFeed] Stats timer started (1s interval)');
  }

  void _connectWebSocket() {
    if (_isConnecting) {
      debugPrint('[VideoFeed] Already connecting, ignoring');
      return;
    }
    
    // FIX: Clear user paused flag when user explicitly connects
    _userPaused = false;
    
    if (!mounted) {
      debugPrint('[VideoFeed] Widget not mounted, aborting connect');
      return;
    }
    
    setState(() {
      _isConnecting = true;
      _hasError = false;
      _errorMessage = '';
    });

    try {
      debugPrint('[VideoFeed] Connecting to WebSocket: $_wsUrl');
      _channel = WebSocketChannel.connect(Uri.parse(_wsUrl));
      
      // Cancel any previous subscription
      _streamSubscription?.cancel();
      
      _streamSubscription = _channel!.stream.listen(
        (data) {
          // FIX: Defensive mounted check before any setState
          if (!mounted) {
            debugPrint('[VideoFeed] Received frame but widget unmounted, ignoring');
            return;
          }
          
          // Decode Base64 to bytes
          try {
            final bytes = base64Decode(data as String);
            setState(() {
              _currentFrame = bytes;
              _isStreaming = true;
              _isConnecting = false;
              _hasError = false;
              _frameCount++;
            });
          } catch (e) {
            debugPrint('[VideoFeed] Error decoding frame: $e');
          }
        },
        onError: (error) {
          debugPrint('[VideoFeed] WebSocket error: $error');
          // FIX: Defensive mounted check
          if (!mounted) return;
          
          setState(() {
            _hasError = true;
            _errorMessage = 'Connection error: $error';
            _isStreaming = false;
            _isConnecting = false;
          });
          _scheduleReconnect();
        },
        onDone: () {
          debugPrint('[VideoFeed] WebSocket closed (onDone)');
          // FIX: Defensive mounted check
          if (!mounted) return;
          
          setState(() {
            _isStreaming = false;
            _isConnecting = false;
          });
          _scheduleReconnect();
        },
        cancelOnError: false,
      );

      if (mounted) {
        setState(() {
          _startTime = DateTime.now();
        });
      }
      debugPrint('[VideoFeed] WebSocket connection initiated');
    } catch (e) {
      debugPrint('[VideoFeed] Failed to connect: $e');
      if (!mounted) return;
      
      setState(() {
        _hasError = true;
        _errorMessage = 'Failed to connect: $e';
        _isConnecting = false;
      });
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    // FIX: Don't auto-reconnect if user clicked Pause
    if (_userPaused) {
      debugPrint('[VideoFeed] User paused, skipping auto-reconnect');
      return;
    }
    
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 3), () {
      // FIX: Check both mounted AND userPaused
      if (mounted && !_isStreaming && !_userPaused) {
        debugPrint('[VideoFeed] Auto-reconnecting after 3s...');
        _connectWebSocket();
      }
    });
  }

  void _disconnect() async {
    debugPrint('[VideoFeed] _disconnect() called');
    
    // FIX: Set user paused flag to prevent auto-reconnect
    _userPaused = true;
    
    _reconnectTimer?.cancel();
    _streamSubscription?.cancel();
    _streamSubscription = null;
    
    // Close WebSocket gracefully
    try {
      _channel?.sink.close();
    } catch (e) {
      debugPrint('[VideoFeed] Error closing WebSocket: $e');
    }
    _channel = null;
    
    if (mounted) {
      setState(() {
        _isStreaming = false;
        _currentFrame = null;
      });
    }
    
    // CRITICAL: Tell backend to stop video processing
    try {
      final response = await http.post(
        Uri.parse('${AppConfig.videoBaseUrl}/video/stop'),
      ).timeout(const Duration(seconds: 5));
      
      if (response.statusCode == 200) {
        debugPrint('[VideoFeed] Backend video worker stopped');
      } else {
        debugPrint('[VideoFeed] Failed to stop backend: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('[VideoFeed] Error stopping backend: $e');
    }
    
    debugPrint('[VideoFeed] Disconnected, _userPaused=true');
  }

  @override
  void dispose() {
    debugPrint('[VideoFeed] dispose() called');
    _clockTimer?.cancel();
    _reconnectTimer?.cancel();
    _statsTimer?.cancel();
    _streamSubscription?.cancel();
    
    // Close WebSocket without calling setState (widget is being disposed)
    try {
      _channel?.sink.close();
    } catch (e) {
      debugPrint('[VideoFeed] Error closing WebSocket in dispose: $e');
    }
    
    super.dispose();
  }

  void _toggleStream() {
    debugPrint('[VideoFeed] _toggleStream() called, _isStreaming=$_isStreaming');
    if (_isStreaming) {
      _disconnect();
    } else {
      _connectWebSocket();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildHeader(),
          AspectRatio(
            aspectRatio: 16 / 9,
            child: Container(
              margin: const EdgeInsets.symmetric(horizontal: 16),
              decoration: BoxDecoration(
                color: Colors.black,
                borderRadius: BorderRadius.circular(12),
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: _buildVideoContent(),
              ),
            ),
          ),
          _buildControls(),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(
              color: _hasError 
                  ? AppColors.error 
                  : (_isStreaming ? AppColors.success : Colors.orange),
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: (_hasError ? AppColors.error : AppColors.success)
                      .withOpacity(0.5),
                  blurRadius: 8,
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Text('Live Feed', style: AppTypography.h4),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: AppColors.primary.withOpacity(0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              'Junction A',
              style: AppTypography.caption.copyWith(color: AppColors.primary),
            ),
          ),
          const Spacer(),
          Flexible(
            child: Text(
              '$_vehicleCount vehicles detected',
              style: AppTypography.bodySmall.copyWith(color: AppColors.textSecondary),
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildVideoContent() {
    if (_isConnecting) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(color: AppColors.primary),
            const SizedBox(height: 16),
            Text(
              'Connecting to video stream...',
              style: AppTypography.bodyMedium.copyWith(color: Colors.white54),
            ),
          ],
        ),
      );
    }

    if (_hasError) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: Colors.red.shade400),
            const SizedBox(height: 16),
            Text(
              'Stream Error',
              style: AppTypography.bodyMedium.copyWith(color: Colors.white54),
            ),
            if (_errorMessage.isNotEmpty) ...[
              const SizedBox(height: 8),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Text(
                  _errorMessage,
                  style: AppTypography.caption.copyWith(color: Colors.white38),
                  textAlign: TextAlign.center,
                ),
              ),
            ],
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _connectWebSocket,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    if (!_isStreaming || _currentFrame == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.videocam_off, size: 64, color: Colors.white30),
            const SizedBox(height: 16),
            Text(
              'Stream paused',
              style: AppTypography.bodyMedium.copyWith(color: Colors.white54),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _connectWebSocket,
              icon: const Icon(Icons.play_arrow),
              label: const Text('Start Stream'),
            ),
          ],
        ),
      );
    }

    return Stack(
      children: [
        // Video frame from WebSocket
        Positioned.fill(
          child: Image.memory(
            _currentFrame!,
            gaplessPlayback: true, // Prevents flickering between frames
            fit: BoxFit.contain,
            errorBuilder: (context, error, stackTrace) {
              return Center(
                child: Icon(Icons.broken_image, size: 64, color: Colors.white30),
              );
            },
          ),
        ),

        // CCTV-style timestamp overlay
        Positioned(
          top: 12,
          right: 12,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: Colors.black87,
              borderRadius: BorderRadius.circular(4),
              border: Border.all(color: Colors.red.withOpacity(0.5)),
            ),
            child: Row(
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: Colors.red,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: Colors.red.withOpacity(0.8),
                        blurRadius: 4,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  _formatCCTVTimestamp(_currentTime),
                  style: AppTypography.caption.copyWith(
                    color: Colors.white,
                    fontFamily: 'monospace',
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1.2,
                  ),
                ),
              ],
            ),
          ),
        ),

        // Stream info overlay
        Positioned(
          bottom: 12,
          left: 12,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: Colors.black54,
              borderRadius: BorderRadius.circular(6),
            ),
            child: Row(
              children: [
                Icon(Icons.circle, size: 8, color: AppColors.success),
                const SizedBox(width: 6),
                Text(
                  'LIVE • YOLOv8 Detection Active',
                  style: AppTypography.caption.copyWith(color: Colors.white),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  String _formatCCTVTimestamp(DateTime time) {
    return '${time.year}-'
        '${time.month.toString().padLeft(2, '0')}-'
        '${time.day.toString().padLeft(2, '0')} '
        '${time.hour.toString().padLeft(2, '0')}:'
        '${time.minute.toString().padLeft(2, '0')}:'
        '${time.second.toString().padLeft(2, '0')}';
  }

  Widget _buildControls() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: LayoutBuilder(
        builder: (context, constraints) {
          if (constraints.maxWidth < 400) {
            return Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: [
                _buildControlButton(
                  icon: _isStreaming ? Icons.pause : Icons.play_arrow,
                  label: _isStreaming ? 'Pause' : 'Play',
                  onTap: _toggleStream,
                ),
                _buildControlButton(
                  icon: Icons.fullscreen,
                  label: 'Fullscreen',
                  onTap: () {},
                ),
                _buildControlButton(
                  icon: Icons.edit_location_alt,
                  label: 'Zones',
                  onTap: widget.onZoneEditorPressed,
                  isPrimary: true,
                ),
                _buildControlButton(
                  icon: Icons.settings,
                  label: 'Settings',
                  onTap: () {},
                ),
              ],
            );
          }
          return Row(
            children: [
              Flexible(
                child: _buildControlButton(
                  icon: _isStreaming ? Icons.pause : Icons.play_arrow,
                  label: _isStreaming ? 'Pause' : 'Play',
                  onTap: _toggleStream,
                ),
              ),
              const SizedBox(width: 8),
              Flexible(
                child: _buildControlButton(
                  icon: Icons.fullscreen,
                  label: 'Fullscreen',
                  onTap: () {},
                ),
              ),
              const SizedBox(width: 8),
              Flexible(
                child: _buildControlButton(
                  icon: Icons.edit_location_alt,
                  label: 'Edit Zones',
                  onTap: widget.onZoneEditorPressed,
                  isPrimary: true,
                ),
              ),
              const Spacer(),
              Flexible(
                child: _buildControlButton(
                  icon: Icons.settings,
                  label: 'Settings',
                  onTap: () {},
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildControlButton({
    required IconData icon,
    required String label,
    VoidCallback? onTap,
    bool isPrimary = false,
  }) {
    return Material(
      color: isPrimary ? AppColors.primary : AppColors.background,
      borderRadius: BorderRadius.circular(8),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Row(
            children: [
              Icon(
                icon,
                size: 18,
                color: isPrimary ? Colors.black : AppColors.textSecondary,
              ),
              const SizedBox(width: 8),
              Text(
                label,
                style: AppTypography.bodySmall.copyWith(
                  color: isPrimary ? Colors.black : AppColors.textPrimary,
                  fontWeight: isPrimary ? FontWeight.w600 : FontWeight.normal,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
