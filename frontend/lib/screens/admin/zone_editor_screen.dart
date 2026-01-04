import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/network/api_client.dart';
import '../../core/network/api_endpoints.dart';
import '../../core/config/app_config.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/admin/admin_sidebar.dart';

class ZoneEditorScreen extends StatefulWidget {
  const ZoneEditorScreen({super.key});

  @override
  State<ZoneEditorScreen> createState() => _ZoneEditorScreenState();
}

class _ZoneEditorScreenState extends State<ZoneEditorScreen> {
  final ApiClient _apiClient = ApiClient();
  
  List<ParkingZone> _zones = [];
  ParkingZone? _selectedZone;
  List<Offset> _currentPoints = [];
  bool _isDrawing = false;
  bool _isLoading = true;
  bool _isLoadingSnapshot = true;
  String _selectedZoneType = 'no_parking';
  String? _snapshotUrl;
  String? _authToken;
  
  final TextEditingController _labelController = TextEditingController();
  
  // Image dimensions for coordinate conversion
  Size _imageSize = const Size(1920, 1080);
  Size _displaySize = Size.zero;
  
  // Actual image display area (accounting for BoxFit.contain letterboxing)
  Rect _imageRect = Rect.zero;

  @override
  void initState() {
    super.initState();
    _loadZones();
    _loadVideoSnapshot();
  }
  
  /// Handle unauthorized access - redirect to login
  void _handleUnauthorized() {
    if (!mounted) return;
    Navigator.of(context).pushNamedAndRemoveUntil('/platform-router', (route) => false);
  }
  
  Future<void> _loadVideoSnapshot() async {
    if (!mounted) return;
    
    try {
      // Get auth token for image request
      final token = await _apiClient.token;
      
      if (!mounted) return;
      
      setState(() {
        _authToken = token;
        // Use videoBaseUrl (localhost) to avoid blocking API connection pool (127.0.0.1)
        _snapshotUrl = '${AppConfig.videoBaseUrl}${ApiEndpoints.videoSnapshot}?t=${DateTime.now().millisecondsSinceEpoch}';
        _isLoadingSnapshot = false;
      });
    } on UnauthorizedException {
      _handleUnauthorized();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoadingSnapshot = false;
      });
    }
  }
  
  /// Refresh the snapshot - requests a new clean frame from the backend
  Future<void> _refreshSnapshot() async {
    if (!mounted) return;
    
    setState(() => _isLoadingSnapshot = true);
    
    try {
      // Request a fresh clean snapshot from the backend
      await _apiClient.post(ApiEndpoints.videoSnapshotRefresh, body: {});
      
      // Get auth token for image request
      final token = await _apiClient.token;
      
      if (!mounted) return;
      
      setState(() {
        _authToken = token;
        // Add timestamp to force reload
        _snapshotUrl = '${AppConfig.videoBaseUrl}${ApiEndpoints.videoSnapshot}?t=${DateTime.now().millisecondsSinceEpoch}';
        _isLoadingSnapshot = false;
      });
      
      _showSuccess('Snapshot refreshed');
    } on UnauthorizedException {
      _handleUnauthorized();
    } catch (e) {
      if (!mounted) return;
      setState(() => _isLoadingSnapshot = false);
      _showError('Failed to refresh snapshot');
    }
  }

  Future<void> _loadZones() async {
    if (!mounted) return;
    debugPrint('[ZoneEditor] _loadZones() called');
    setState(() => _isLoading = true);
    
    try {
      debugPrint('[ZoneEditor] Fetching zones from API...');
      final response = await _apiClient.get(ApiEndpoints.adminZones);
      debugPrint('[ZoneEditor] API response received: success=${response.success}');
      
      if (!mounted) {
        debugPrint('[ZoneEditor] Widget unmounted after API call, aborting');
        return;
      }
      
      if (response.success && response.data != null) {
        final dynamic zonesRaw = response.data!['zones'];
        final List<dynamic> zonesData = zonesRaw ?? [];
        debugPrint('[ZoneEditor] Parsing ${zonesData.length} zones...');
        
        final parsedZones = <ParkingZone>[];
        for (var i = 0; i < zonesData.length; i++) {
          try {
            final zone = ParkingZone.fromJson(zonesData[i]);
            parsedZones.add(zone);
          } catch (e) {
            debugPrint('[ZoneEditor] Error parsing zone $i: $e');
          }
        }
        
        if (mounted) {
          setState(() {
            _zones = parsedZones;
          });
          debugPrint('[ZoneEditor] Successfully loaded ${parsedZones.length} zones');
        }
      } else {
        debugPrint('[ZoneEditor] API error: ${response.error}');
        if (mounted && response.error != null) {
          _showError(response.error!);
        }
      }
    } on UnauthorizedException {
      debugPrint('[ZoneEditor] UnauthorizedException - redirecting to login');
      _handleUnauthorized();
    } catch (e) {
      debugPrint('[ZoneEditor] Exception loading zones: $e');
      if (mounted) {
        _showError('Failed to load zones: $e');
      }
    } finally {
      // CRITICAL: Always stop loading spinner, even on error
      debugPrint('[ZoneEditor] _loadZones() finally block - setting _isLoading = false');
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _saveZone() async {
    if (_currentPoints.length < 3) {
      _showError('Please draw at least 3 points to create a zone');
      return;
    }
    
    if (_labelController.text.trim().isEmpty) {
      _showError('Please enter a zone label');
      return;
    }
    
    // Convert screen coordinates to image coordinates (accounting for letterboxing)
    final List<List<double>> coordinates = _currentPoints.map((p) {
      final imageCoord = _screenToImage(p);
      return [imageCoord.dx, imageCoord.dy];
    }).toList();
    
    try {
      final response = await _apiClient.post(
        ApiEndpoints.adminZones,
        body: {
          'zone_type': _selectedZoneType,
          'label': _labelController.text.trim(),
          'coordinates': coordinates,
        },
      );
      
      if (!mounted) return;
      
      if (response.success) {
        _showSuccess('Zone saved successfully');
        _cancelDrawing();
        _loadZones();
      } else {
        _showError(response.error ?? 'Failed to save zone');
      }
    } on UnauthorizedException {
      _handleUnauthorized();
    } catch (e) {
      if (!mounted) return;
      _showError('Failed to save zone');
    }
  }

  Future<void> _deleteZone(ParkingZone zone) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Delete Zone'),
        content: Text('Are you sure you want to delete "${zone.label}"?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.error),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    
    if (!mounted) return;
    
    if (confirmed == true) {
      try {
        final response = await _apiClient.delete(
          '${ApiEndpoints.adminZones}/${zone.id}',
        );
        
        if (!mounted) return;
        
        if (response.success) {
          _showSuccess('Zone deleted');
          _loadZones();
        } else {
          _showError(response.error ?? 'Failed to delete zone');
        }
      } on UnauthorizedException {
        _handleUnauthorized();
      } catch (e) {
        if (!mounted) return;
        _showError('Failed to delete zone');
      }
    }
  }

  /// Calculate the actual image display rect within the container
  /// This accounts for BoxFit.contain letterboxing
  void _calculateImageRect() {
    if (_displaySize == Size.zero) return;
    
    final containerAspect = _displaySize.width / _displaySize.height;
    final imageAspect = _imageSize.width / _imageSize.height;
    
    double displayedWidth, displayedHeight;
    double offsetX = 0, offsetY = 0;
    
    if (containerAspect > imageAspect) {
      // Container is wider - black bars on left/right
      displayedHeight = _displaySize.height;
      displayedWidth = displayedHeight * imageAspect;
      offsetX = (_displaySize.width - displayedWidth) / 2;
    } else {
      // Container is taller - black bars on top/bottom
      displayedWidth = _displaySize.width;
      displayedHeight = displayedWidth / imageAspect;
      offsetY = (_displaySize.height - displayedHeight) / 2;
    }
    
    _imageRect = Rect.fromLTWH(offsetX, offsetY, displayedWidth, displayedHeight);
  }
  
  /// Convert image coordinates to screen coordinates
  Offset _imageToScreen(double imageX, double imageY) {
    return Offset(
      _imageRect.left + (imageX / _imageSize.width) * _imageRect.width,
      _imageRect.top + (imageY / _imageSize.height) * _imageRect.height,
    );
  }
  
  /// Convert screen coordinates to image coordinates
  Offset _screenToImage(Offset screenPoint) {
    return Offset(
      ((screenPoint.dx - _imageRect.left) / _imageRect.width) * _imageSize.width,
      ((screenPoint.dy - _imageRect.top) / _imageRect.height) * _imageSize.height,
    );
  }

  void _startDrawing() {
    setState(() {
      _isDrawing = true;
      _currentPoints = [];
      _selectedZone = null;
    });
  }

  void _cancelDrawing() {
    setState(() {
      _isDrawing = false;
      _currentPoints = [];
      _labelController.clear();
    });
  }

  void _undoLastPoint() {
    if (_currentPoints.isNotEmpty) {
      setState(() {
        _currentPoints.removeLast();
      });
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

  void _handleNavigation(BuildContext context, int index) {
    switch (index) {
      case 0: // Dashboard
        Navigator.of(context).pushReplacementNamed('/admin/dashboard');
        break;
      case 1: // Zone Editor - already here
        break;
      case 2: // Violations
        Navigator.of(context).pushReplacementNamed('/admin/violations');
        break;
      case 3: // Audit Logs
        Navigator.of(context).pushReplacementNamed('/admin/logs');
        break;
      case 4: // Settings
        Navigator.of(context).pushReplacementNamed('/admin/settings');
        break;
      case 5: // Logout
        _handleLogout();
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
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.error,
            ),
            child: const Text('Logout'),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      await Provider.of<AuthProvider>(context, listen: false).logout();
      if (mounted) {
        Navigator.of(context).pushReplacementNamed('/');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          // Sidebar
          AdminSidebar(
            selectedIndex: 1, // Zone Editor
            onItemSelected: (index) => _handleNavigation(context, index),
          ),
          
          // Main content
          Expanded(
            child: Container(
              color: AppColors.background,
              child: Column(
                children: [
                  _buildHeader(),
                  Expanded(
                    child: Row(
                      children: [
                        // Canvas area
                        Expanded(
                          flex: 3,
                          child: _buildCanvas(),
                        ),
                        
                        // Zone list panel
                        Container(
                          width: 320,
                          decoration: BoxDecoration(
                            color: AppColors.surface,
                            border: Border(
                              left: BorderSide(color: AppColors.border),
                            ),
                          ),
                          child: _buildZonePanel(),
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
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border(
          bottom: BorderSide(color: AppColors.border),
        ),
      ),
      child: Row(
        children: [
          IconButton(
            onPressed: () => Navigator.of(context).pop(),
            icon: const Icon(Icons.arrow_back),
          ),
          const SizedBox(width: 16),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Zone Editor', style: AppTypography.h2),
              Text(
                'Draw and manage no-parking zones',
                style: AppTypography.bodySmall.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
          const Spacer(),
          if (_isDrawing) ...[
            OutlinedButton.icon(
              onPressed: _cancelDrawing,
              icon: const Icon(Icons.close),
              label: const Text('Cancel'),
              style: OutlinedButton.styleFrom(
                foregroundColor: AppColors.error,
                side: BorderSide(color: AppColors.error),
              ),
            ),
            const SizedBox(width: 12),
            ElevatedButton.icon(
              onPressed: _saveZone,
              icon: const Icon(Icons.save),
              label: const Text('Save Zone'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.success,
              ),
            ),
          ] else ...[
            IconButton(
              onPressed: _refreshSnapshot,
              icon: const Icon(Icons.refresh),
              tooltip: 'Refresh video frame',
            ),
            const SizedBox(width: 8),
            ElevatedButton.icon(
              onPressed: _startDrawing,
              icon: const Icon(Icons.add_location_alt),
              label: const Text('New Zone'),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildCanvas() {
    return Container(
      margin: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.black,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.3),
            blurRadius: 20,
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: LayoutBuilder(
          builder: (context, constraints) {
            _displaySize = Size(constraints.maxWidth, constraints.maxHeight);
            _calculateImageRect(); // Calculate actual image display area
            
            return GestureDetector(
              onTapDown: _isDrawing ? _handleTap : null,
              child: Stack(
                children: [
                  // Background - video snapshot for zone drawing
                  _isLoadingSnapshot
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              CircularProgressIndicator(color: AppColors.primary),
                              const SizedBox(height: 16),
                              Text(
                                'Loading video frame...',
                                style: AppTypography.bodySmall.copyWith(color: Colors.white54),
                              ),
                            ],
                          ),
                        )
                      : _buildSnapshotImage(),
                  
                  // Existing zones
                  ..._buildExistingZones(),
                  
                  // Current drawing
                  if (_isDrawing)
                    CustomPaint(
                      size: Size.infinite,
                      painter: ZonePainter(
                        points: _currentPoints,
                        color: _getZoneColor(_selectedZoneType),
                        isComplete: false,
                      ),
                    ),
                  
                  // Points
                  ..._buildPoints(),
                  
                  // Instructions overlay
                  if (_isDrawing)
                    Positioned(
                      bottom: 16,
                      left: 16,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 10,
                        ),
                        decoration: BoxDecoration(
                          color: Colors.black87,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          children: [
                            const Icon(
                              Icons.info_outline,
                              color: Colors.white70,
                              size: 18,
                            ),
                            const SizedBox(width: 8),
                            Text(
                              'Points: ${_currentPoints.length} • Minimum: 3',
                              style: AppTypography.bodySmall.copyWith(
                                color: Colors.white70,
                              ),
                            ),
                            if (_currentPoints.isNotEmpty) ...[
                              const SizedBox(width: 16),
                              TextButton.icon(
                                onPressed: _undoLastPoint,
                                icon: const Icon(Icons.undo, size: 16),
                                label: const Text('Undo'),
                                style: TextButton.styleFrom(
                                  foregroundColor: Colors.white70,
                                  padding: EdgeInsets.zero,
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  void _handleTap(TapDownDetails details) {
    setState(() {
      _currentPoints.add(details.localPosition);
    });
  }
  
  Widget _buildPlaceholderBackground() {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Colors.grey.shade900,
            Colors.grey.shade800,
          ],
        ),
      ),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.videocam_off,
              size: 80,
              color: Colors.white24,
            ),
            const SizedBox(height: 16),
            Text(
              _isDrawing 
                  ? 'Tap to add points • Click "Save Zone" when done'
                  : 'No video frame available',
              style: AppTypography.bodyLarge.copyWith(
                color: Colors.white38,
              ),
            ),
            const SizedBox(height: 8),
            TextButton.icon(
              onPressed: _refreshSnapshot,
              icon: const Icon(Icons.refresh, size: 16),
              label: const Text('Retry loading frame'),
              style: TextButton.styleFrom(
                foregroundColor: AppColors.primary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Build snapshot image with proper auth token handling for web
  Widget _buildSnapshotImage() {
    return FutureBuilder<Uint8List?>(
      future: _fetchSnapshotBytes(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                CircularProgressIndicator(color: AppColors.primary),
                const SizedBox(height: 16),
                Text(
                  'Loading video frame...',
                  style: AppTypography.bodySmall.copyWith(color: Colors.white54),
                ),
              ],
            ),
          );
        }
        
        if (snapshot.hasError || snapshot.data == null) {
          return _buildPlaceholderBackground();
        }
        
        return Image.memory(
          snapshot.data!,
          fit: BoxFit.contain,
          errorBuilder: (context, error, stackTrace) => _buildPlaceholderBackground(),
        );
      },
    );
  }

  /// Fetch snapshot bytes with proper authorization header
  Future<Uint8List?> _fetchSnapshotBytes() async {
    if (_snapshotUrl == null) return null;
    
    try {
      final headers = <String, String>{};
      if (_authToken != null) {
        headers['Authorization'] = 'Bearer $_authToken';
      }
      
      // Increased timeout to 20s - backend may need time to load YOLO models
      final response = await http.get(
        Uri.parse(_snapshotUrl!),
        headers: headers,
      ).timeout(const Duration(seconds: 20));
      
      if (response.statusCode == 200) {
        return response.bodyBytes;
      }
      // If 503, wait and retry once (models still loading)
      if (response.statusCode == 503) {
        await Future.delayed(const Duration(seconds: 3));
        final retryResponse = await http.get(
          Uri.parse(_snapshotUrl!),
          headers: headers,
        ).timeout(const Duration(seconds: 15));
        if (retryResponse.statusCode == 200) {
          return retryResponse.bodyBytes;
        }
      }
      return null;
    } catch (e) {
      print('Error fetching snapshot: $e');
      return null;
    }
  }

  List<Widget> _buildExistingZones() {
    return _zones.map((zone) {
      final points = zone.coordinates.map((coord) {
        // Use proper coordinate conversion accounting for letterboxing
        return _imageToScreen(coord[0], coord[1]);
      }).toList();
      
      final isSelected = _selectedZone?.id == zone.id;
      
      return CustomPaint(
        size: Size.infinite,
        painter: ZonePainter(
          points: points,
          color: _getZoneColor(zone.zoneType),
          isComplete: true,
          isSelected: isSelected,
          label: zone.label,
        ),
      );
    }).toList();
  }

  List<Widget> _buildPoints() {
    return _currentPoints.asMap().entries.map((entry) {
      final index = entry.key;
      final point = entry.value;
      
      return Positioned(
        left: point.dx - 10,
        top: point.dy - 10,
        child: Container(
          width: 20,
          height: 20,
          decoration: BoxDecoration(
            color: _getZoneColor(_selectedZoneType),
            shape: BoxShape.circle,
            border: Border.all(color: Colors.white, width: 2),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.5),
                blurRadius: 4,
              ),
            ],
          ),
          child: Center(
            child: Text(
              '${index + 1}',
              style: const TextStyle(
                color: Colors.white,
                fontSize: 10,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ),
      );
    }).toList();
  }

  Color _getZoneColor(String zoneType) {
    switch (zoneType) {
      case 'no_parking':
        return Colors.red;
      case 'loading':
        return Colors.orange;
      case 'handicap':
        return Colors.blue;
      default:
        return Colors.red;
    }
  }

  Widget _buildZonePanel() {
    return Column(
      children: [
        // Zone form (when drawing)
        if (_isDrawing) _buildZoneForm(),
        
        // Zone list
        Expanded(
          child: _isLoading
              ? const Center(child: CircularProgressIndicator())
              : _buildZoneList(),
        ),
      ],
    );
  }

  Widget _buildZoneForm() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.background,
        border: Border(
          bottom: BorderSide(color: AppColors.border),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('New Zone', style: AppTypography.h4),
          const SizedBox(height: 16),
          
          // Zone type dropdown
          Text('Zone Type', style: AppTypography.inputLabel),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.border),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: _selectedZoneType,
                isExpanded: true,
                dropdownColor: AppColors.surface,
                items: const [
                  DropdownMenuItem(
                    value: 'no_parking',
                    child: Row(
                      children: [
                        Icon(Icons.block, color: Colors.red, size: 18),
                        SizedBox(width: 8),
                        Text('No Parking'),
                      ],
                    ),
                  ),
                  DropdownMenuItem(
                    value: 'loading',
                    child: Row(
                      children: [
                        Icon(Icons.local_shipping, color: Colors.orange, size: 18),
                        SizedBox(width: 8),
                        Text('Loading Zone'),
                      ],
                    ),
                  ),
                  DropdownMenuItem(
                    value: 'handicap',
                    child: Row(
                      children: [
                        Icon(Icons.accessible, color: Colors.blue, size: 18),
                        SizedBox(width: 8),
                        Text('Handicap'),
                      ],
                    ),
                  ),
                ],
                onChanged: (value) {
                  if (value != null) {
                    setState(() => _selectedZoneType = value);
                  }
                },
              ),
            ),
          ),
          
          const SizedBox(height: 16),
          
          // Label field
          Text('Label', style: AppTypography.inputLabel),
          const SizedBox(height: 8),
          TextField(
            controller: _labelController,
            decoration: InputDecoration(
              hintText: 'e.g., Main Street No Parking',
              filled: true,
              fillColor: AppColors.surface,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: BorderSide(color: AppColors.border),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildZoneList() {
    if (_zones.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.location_off,
              size: 64,
              color: AppColors.textMuted,
            ),
            const SizedBox(height: 16),
            Text(
              'No zones defined',
              style: AppTypography.bodyMedium.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Click "New Zone" to create one',
              style: AppTypography.caption.copyWith(
                color: AppColors.textMuted,
              ),
            ),
          ],
        ),
      );
    }
    
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _zones.length,
      itemBuilder: (context, index) {
        final zone = _zones[index];
        final isSelected = _selectedZone?.id == zone.id;
        
        return Container(
          margin: const EdgeInsets.only(bottom: 8),
          decoration: BoxDecoration(
            color: isSelected 
                ? _getZoneColor(zone.zoneType).withOpacity(0.15)
                : AppColors.background,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isSelected 
                  ? _getZoneColor(zone.zoneType)
                  : AppColors.border,
            ),
          ),
          child: ListTile(
            onTap: () {
              setState(() {
                _selectedZone = isSelected ? null : zone;
              });
            },
            leading: Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: _getZoneColor(zone.zoneType).withOpacity(0.2),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(
                _getZoneIcon(zone.zoneType),
                color: _getZoneColor(zone.zoneType),
                size: 20,
              ),
            ),
            title: Text(
              zone.label,
              style: AppTypography.bodyMedium.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            subtitle: Text(
              '${zone.coordinates.length} points • ${zone.zoneType.replaceAll('_', ' ')}',
              style: AppTypography.caption.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Active toggle
                Switch(
                  value: zone.active,
                  onChanged: (value) => _toggleZoneActive(zone, value),
                  activeColor: AppColors.success,
                ),
                IconButton(
                  onPressed: () => _deleteZone(zone),
                  icon: const Icon(Icons.delete_outline),
                  color: AppColors.error,
                  iconSize: 20,
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  IconData _getZoneIcon(String zoneType) {
    switch (zoneType) {
      case 'no_parking':
        return Icons.block;
      case 'loading':
        return Icons.local_shipping;
      case 'handicap':
        return Icons.accessible;
      default:
        return Icons.location_on;
    }
  }

  Future<void> _toggleZoneActive(ParkingZone zone, bool active) async {
    try {
      final response = await _apiClient.put(
        '${ApiEndpoints.adminZones}/${zone.id}',
        body: {'active': active},
      );
      
      if (response.success) {
        _loadZones();
      }
    } catch (e) {
      _showError('Failed to update zone');
    }
  }
}

class ParkingZone {
  final int id;
  final String zoneType;
  final String label;
  final List<List<double>> coordinates;
  final bool active;
  
  ParkingZone({
    required this.id,
    required this.zoneType,
    required this.label,
    required this.coordinates,
    required this.active,
  });
  
  factory ParkingZone.fromJson(Map<String, dynamic> json) {
    return ParkingZone(
      id: json['id'],
      zoneType: json['zone_type'] ?? 'no_parking',
      label: json['label'] ?? 'Zone',
      coordinates: (json['coordinates'] as List)
          .map((c) => (c as List).map((v) => (v as num).toDouble()).toList())
          .toList(),
      active: json['active'] ?? true,
    );
  }
}

class ZonePainter extends CustomPainter {
  final List<Offset> points;
  final Color color;
  final bool isComplete;
  final bool isSelected;
  final String? label;
  
  ZonePainter({
    required this.points,
    required this.color,
    required this.isComplete,
    this.isSelected = false,
    this.label,
  });
  
  @override
  void paint(Canvas canvas, Size size) {
    if (points.isEmpty) return;
    
    final fillPaint = Paint()
      ..color = color.withOpacity(isSelected ? 0.4 : 0.25)
      ..style = PaintingStyle.fill;
    
    final strokePaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = isSelected ? 3 : 2;
    
    final path = Path();
    path.moveTo(points.first.dx, points.first.dy);
    
    for (int i = 1; i < points.length; i++) {
      path.lineTo(points[i].dx, points[i].dy);
    }
    
    if (isComplete) {
      path.close();
    }
    
    canvas.drawPath(path, fillPaint);
    canvas.drawPath(path, strokePaint);
    
    // Draw label
    if (label != null && points.length >= 3) {
      final center = _getPolygonCenter();
      final textPainter = TextPainter(
        text: TextSpan(
          text: label,
          style: TextStyle(
            color: Colors.white,
            fontSize: 12,
            fontWeight: FontWeight.bold,
            shadows: [
              Shadow(
                color: Colors.black,
                blurRadius: 4,
              ),
            ],
          ),
        ),
        textDirection: ui.TextDirection.ltr,
      );
      textPainter.layout();
      textPainter.paint(
        canvas,
        Offset(
          center.dx - textPainter.width / 2,
          center.dy - textPainter.height / 2,
        ),
      );
    }
  }
  
  Offset _getPolygonCenter() {
    double x = 0, y = 0;
    for (final point in points) {
      x += point.dx;
      y += point.dy;
    }
    return Offset(x / points.length, y / points.length);
  }
  
  @override
  bool shouldRepaint(covariant ZonePainter oldDelegate) {
    return points != oldDelegate.points || 
           isSelected != oldDelegate.isSelected ||
           isComplete != oldDelegate.isComplete;
  }
}
