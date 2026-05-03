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
  final VoidCallback? onSettingsPressed;

  const LiveVideoFeed({
    super.key,
    this.onZoneEditorPressed,
    this.onSettingsPressed,
  });

  @override
  State<LiveVideoFeed> createState() => _LiveVideoFeedState();
}

class _LiveVideoFeedState extends State<LiveVideoFeed> {
  WebSocketChannel? _channel;
  StreamSubscription? _streamSubscription;
  Uint8List? _currentFrame;
  bool _isStreaming = false;

  /// Shared notifier so fullscreen overlay gets frames without a second WebSocket.
  final ValueNotifier<Uint8List?> _frameNotifier = ValueNotifier<Uint8List?>(null);
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
  
  // Video seek position for timeline control
  double _videoSeekPosition = 0.0; // 0.0 to 1.0 for timeline
  bool _isSeekingVideo = false;

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

  /// FIX: Stats timer to fetch /video/status every 3 seconds for vehicle count updates
  void _startStatsTimer() {
    _statsTimer?.cancel();
    _statsTimer = Timer.periodic(const Duration(seconds: 3), (_) async {
      if (!mounted || !_isStreaming) return;
      
      try {
        final response = await http.get(
          Uri.parse('${AppConfig.videoBaseUrl}/video/status'),
        ).timeout(const Duration(seconds: 5));
        
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
        // Suppress timeout errors - non-critical polling
      }
    });
    debugPrint('[VideoFeed] Stats timer started (3s interval)');
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
            _frameNotifier.value = bytes;
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
    _frameNotifier.dispose();
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

  /// Seek video to position (0.0 to 1.0)
  void _seekVideo(double position) async {
    if (!_isStreaming) return;

    try {
      debugPrint('[VideoFeed] Seeking to ${(position * 100).toInt()}%');
      final response = await http.post(
        Uri.parse('${AppConfig.videoBaseUrl}/video/seek'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'position': position}),
      ).timeout(const Duration(seconds: 5));
      
      if (response.statusCode == 200) {
        debugPrint('[VideoFeed] Seek successful');
      } else {
        debugPrint('[VideoFeed] Seek failed: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('[VideoFeed] Seek error: $e');
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
          // Video Timeline Seek Bar
          Container(
            margin: const EdgeInsets.fromLTRB(16, 16, 16, 0),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: AppColors.background,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Video Timeline', style: AppTypography.labelSmall),
                const SizedBox(height: 8),
                Row(
                  children: [
                    IconButton(
                      onPressed: () {
                        final next = (_videoSeekPosition - 0.05).clamp(0.0, 1.0);
                        setState(() => _videoSeekPosition = next);
                        _seekVideo(next);
                      },
                      icon: const Icon(Icons.fast_rewind),
                      tooltip: 'Rewind 5%',
                      constraints: const BoxConstraints(minWidth: 40, minHeight: 40),
                      padding: EdgeInsets.zero,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Slider(
                        value: _videoSeekPosition,
                        min: 0.0,
                        max: 1.0,
                        divisions: 100,
                        label: '${(_videoSeekPosition * 100).toInt()}%',
                        onChanged: (value) {
                          setState(() => _videoSeekPosition = value);
                        },
                        onChangeStart: (_) => setState(() => _isSeekingVideo = true),
                        onChangeEnd: (value) {
                          setState(() => _isSeekingVideo = false);
                          _seekVideo(value);
                        },
                      ),
                    ),
                    const SizedBox(width: 8),
                    IconButton(
                      onPressed: () {
                        final next = (_videoSeekPosition + 0.05).clamp(0.0, 1.0);
                        setState(() => _videoSeekPosition = next);
                        _seekVideo(next);
                      },
                      icon: const Icon(Icons.fast_forward),
                      tooltip: 'Forward 5%',
                      constraints: const BoxConstraints(minWidth: 40, minHeight: 40),
                      padding: EdgeInsets.zero,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '${(_videoSeekPosition * 100).toInt()}%',
                      style: AppTypography.caption,
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
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
                  onTap: _openFullscreen,
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
                  onTap: widget.onSettingsPressed,
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
                  onTap: _openFullscreen,
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
                  onTap: widget.onSettingsPressed,
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

  /// Open the video feed full-screen inside the same browser tab (no new window).
  void _openFullscreen() {
    Navigator.of(context).push(
      MaterialPageRoute(
        fullscreenDialog: true,
        builder: (_) => _FullscreenVideoOverlay(frameNotifier: _frameNotifier),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Full-screen video overlay — listens to the shared ValueNotifier from the
// parent LiveVideoFeed so it receives frames instantly without opening a
// second WebSocket (the backend only serves one client at a time).
// ---------------------------------------------------------------------------
class _FullscreenVideoOverlay extends StatelessWidget {
  final ValueNotifier<Uint8List?> frameNotifier;
  const _FullscreenVideoOverlay({required this.frameNotifier});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Stack(
          fit: StackFit.expand,
          children: [
            // Video — fill entire area edge-to-edge
            Positioned.fill(
              child: ValueListenableBuilder<Uint8List?>(
                valueListenable: frameNotifier,
                builder: (_, frame, __) {
                  if (frame != null) {
                    return Image.memory(
                      frame,
                      gaplessPlayback: true,
                      fit: BoxFit.cover,
                      width: double.infinity,
                      height: double.infinity,
                    );
                  }
                  return const Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        CircularProgressIndicator(color: Colors.white54),
                        SizedBox(height: 16),
                        Text('Waiting for video...',
                            style: TextStyle(color: Colors.white54)),
                      ],
                    ),
                  );
                },
              ),
            ),
            // Exit fullscreen button — floating pill
            Positioned(
              top: 20,
              right: 20,
              child: Material(
                color: Colors.black.withOpacity(0.6),
                borderRadius: BorderRadius.circular(24),
                elevation: 4,
                child: InkWell(
                  borderRadius: BorderRadius.circular(24),
                  onTap: () => Navigator.of(context).pop(),
                  child: const Padding(
                    padding:
                        EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.fullscreen_exit,
                            color: Colors.white, size: 20),
                        SizedBox(width: 8),
                        Text('Exit Fullscreen',
                            style: TextStyle(
                                color: Colors.white,
                                fontSize: 13,
                                fontWeight: FontWeight.w500)),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
