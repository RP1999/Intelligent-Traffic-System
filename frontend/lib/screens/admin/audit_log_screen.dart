import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/network/api_client.dart';
import '../../core/network/api_endpoints.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/admin/admin_sidebar.dart';

class AuditLogScreen extends StatefulWidget {
  const AuditLogScreen({super.key});

  @override
  State<AuditLogScreen> createState() => _AuditLogScreenState();
}

class _AuditLogScreenState extends State<AuditLogScreen> {
  final ApiClient _apiClient = ApiClient();
  
  List<AuditLogEntry> _logs = [];
  bool _isLoading = true;
  int _currentPage = 1;
  int _totalPages = 1;
  String? _selectedAction;
  DateTimeRange? _dateRange;

  @override
  void initState() {
    super.initState();
    _loadLogs();
  }

  /// Handle unauthorized access - redirect to login
  void _handleUnauthorized() {
    if (!mounted) return;
    Navigator.of(context).pushNamedAndRemoveUntil('/platform-router', (route) => false);
  }

  Future<void> _loadLogs() async {
    if (!mounted) return;
    debugPrint('[AuditLog] _loadLogs() called, page=$_currentPage, action=$_selectedAction');
    setState(() => _isLoading = true);
    
    try {
      String url = '${ApiEndpoints.adminLogs}?page=$_currentPage&limit=20';
      if (_selectedAction != null) {
        url += '&action=$_selectedAction';
      }
      
      debugPrint('[AuditLog] Fetching logs from: $url');
      final response = await _apiClient.get(url);
      debugPrint('[AuditLog] API response received: success=${response.success}');
      
      if (!mounted) {
        debugPrint('[AuditLog] Widget unmounted after API call, aborting');
        return;
      }
      
      if (response.success && response.data != null) {
        final List<dynamic> logsData = response.data!['logs'] ?? [];
        debugPrint('[AuditLog] Parsing ${logsData.length} log entries...');
        
        if (mounted) {
          setState(() {
            _logs = logsData.map((l) => AuditLogEntry.fromJson(l)).toList();
            _totalPages = response.data!['total_pages'] ?? 1;
          });
          debugPrint('[AuditLog] Successfully loaded ${_logs.length} logs, $_totalPages total pages');
        }
      } else {
        debugPrint('[AuditLog] API error: ${response.error}');
        if (mounted && response.error != null) {
          _showError(response.error!);
        }
      }
    } on UnauthorizedException {
      debugPrint('[AuditLog] UnauthorizedException - redirecting to login');
      _handleUnauthorized();
    } catch (e) {
      debugPrint('[AuditLog] Exception loading logs: $e');
      if (mounted) {
        _showError('Failed to load audit logs: $e');
      }
    } finally {
      // CRITICAL: Always stop loading spinner, even on error
      debugPrint('[AuditLog] _loadLogs() finally block - setting _isLoading = false');
      if (mounted) {
        setState(() => _isLoading = false);
      }
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          // Sidebar
          AdminSidebar(
            selectedIndex: 3, // Audit Logs
            onItemSelected: (index) => _handleNavigation(context, index),
          ),
          
          // Main content
          Expanded(
            child: Container(
              color: AppColors.background,
              child: Column(
                children: [
                  _buildHeader(),
                  _buildFilters(),
                  Expanded(
                    child: _isLoading
                        ? const Center(child: CircularProgressIndicator())
                        : _buildDataTable(),
                  ),
                  _buildPagination(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _handleNavigation(BuildContext context, int index) {
    switch (index) {
      case 0: // Dashboard
        Navigator.of(context).pushReplacementNamed('/admin/dashboard');
        break;
      case 1: // Zone Editor
        Navigator.of(context).pushReplacementNamed('/admin/zones');
        break;
      case 2: // Violations
        Navigator.of(context).pushReplacementNamed('/admin/violations');
        break;
      case 3: // Audit Logs - already here
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
              Text('Audit Logs', style: AppTypography.h2),
              Text(
                'Track all administrative actions',
                style: AppTypography.bodySmall.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
          const Spacer(),
          OutlinedButton.icon(
            onPressed: _exportLogs,
            icon: const Icon(Icons.download),
            label: const Text('Export'),
          ),
          const SizedBox(width: 12),
          IconButton(
            onPressed: _loadLogs,
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
          ),
        ],
      ),
    );
  }

  Widget _buildFilters() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border(
          bottom: BorderSide(color: AppColors.border),
        ),
      ),
      child: Wrap(
        spacing: 16,
        runSpacing: 12,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          // Action filter
          SizedBox(
            width: 180,
            child: DropdownButtonFormField<String?>(
              value: _selectedAction,
              isExpanded: true,  // Fix overflow
              decoration: InputDecoration(
                labelText: 'Filter by Action',
                prefixIcon: const Icon(Icons.filter_list, size: 20),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
                contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                isDense: true,
              ),
              dropdownColor: AppColors.surface,
              items: const [
                DropdownMenuItem(value: null, child: Text('All Actions')),
                DropdownMenuItem(value: 'login', child: Text('Login')),
                DropdownMenuItem(value: 'logout', child: Text('Logout')),
                DropdownMenuItem(value: 'zone_create', child: Text('Zone Create')),
                DropdownMenuItem(value: 'zone_update', child: Text('Zone Update')),
                DropdownMenuItem(value: 'zone_delete', child: Text('Zone Delete')),
                DropdownMenuItem(value: 'violation_create', child: Text('Violation Create')),
                DropdownMenuItem(value: 'settings_update', child: Text('Settings Update')),
              ],
              onChanged: (value) {
                setState(() {
                  _selectedAction = value;
                  _currentPage = 1;
                });
                _loadLogs();
              },
            ),
          ),
          
          // Date range picker
          OutlinedButton.icon(
            onPressed: _selectDateRange,
            icon: const Icon(Icons.date_range),
            label: Text(
              _dateRange != null
                  ? '${DateFormat('MMM d').format(_dateRange!.start)} - ${DateFormat('MMM d').format(_dateRange!.end)}'
                  : 'Select Date Range',
            ),
          ),
          
          if (_dateRange != null || _selectedAction != null)
            TextButton.icon(
              onPressed: _clearFilters,
              icon: const Icon(Icons.clear),
              label: const Text('Clear Filters'),
            ),
          
          // Entries count at the end
          Text(
            '${_logs.length} entries',
            style: AppTypography.bodySmall.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _selectDateRange() async {
    final range = await showDateRangePicker(
      context: context,
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      lastDate: DateTime.now(),
      initialDateRange: _dateRange,
      builder: (context, child) {
        return Theme(
          data: ThemeData.dark().copyWith(
            colorScheme: ColorScheme.dark(
              primary: AppColors.primary,
              onPrimary: Colors.black,
              surface: AppColors.surface,
            ),
          ),
          child: child!,
        );
      },
    );
    
    if (range != null) {
      setState(() {
        _dateRange = range;
        _currentPage = 1;
      });
      _loadLogs();
    }
  }

  void _clearFilters() {
    setState(() {
      _selectedAction = null;
      _dateRange = null;
      _currentPage = 1;
    });
    _loadLogs();
  }

  Widget _buildDataTable() {
    if (_logs.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.history,
              size: 64,
              color: AppColors.textMuted,
            ),
            const SizedBox(height: 16),
            Text(
              'No audit logs found',
              style: AppTypography.bodyMedium.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ),
      );
    }
    
    return Container(
      margin: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: DataTable(
            headingRowColor: WidgetStateProperty.all(AppColors.background),
            columns: const [
              DataColumn(label: Text('Timestamp')),
              DataColumn(label: Text('Admin')),
              DataColumn(label: Text('Action')),
              DataColumn(label: Text('Details')),
              DataColumn(label: Text('IP Address')),
            ],
            rows: _logs.map((log) => _buildDataRow(log)).toList(),
          ),
        ),
      ),
    );
  }

  DataRow _buildDataRow(AuditLogEntry log) {
    return DataRow(
      cells: [
        DataCell(
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.access_time,
                size: 14,
                color: AppColors.textSecondary,
              ),
              const SizedBox(width: 8),
              Text(
                DateFormat('MMM d, yyyy HH:mm').format(log.timestamp),
                style: AppTypography.bodySmall,
              ),
            ],
          ),
        ),
        DataCell(
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircleAvatar(
                radius: 14,
                backgroundColor: AppColors.primary.withOpacity(0.2),
                child: Text(
                  log.adminUsername.isNotEmpty ? log.adminUsername[0].toUpperCase() : '?',
                  style: AppTypography.caption.copyWith(
                    color: AppColors.primary,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Text(log.adminUsername),
            ],
          ),
        ),
        DataCell(_buildActionBadge(log.action)),
        DataCell(
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 300),
            child: Text(
              log.details ?? '-',
              overflow: TextOverflow.ellipsis,
              style: AppTypography.bodySmall.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ),
        ),
        DataCell(
          Text(
            log.ipAddress ?? '-',
            style: AppTypography.bodySmall.copyWith(
              fontFamily: 'monospace',
              color: AppColors.textSecondary,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildActionBadge(String action) {
    Color color;
    IconData icon;
    
    switch (action) {
      case 'login':
        color = AppColors.success;
        icon = Icons.login;
        break;
      case 'logout':
        color = AppColors.info;
        icon = Icons.logout;
        break;
      case 'zone_create':
        color = AppColors.primary;
        icon = Icons.add_location;
        break;
      case 'zone_update':
        color = AppColors.warning;
        icon = Icons.edit_location;
        break;
      case 'zone_delete':
        color = AppColors.error;
        icon = Icons.location_off;
        break;
      case 'violation_create':
        color = AppColors.error;
        icon = Icons.warning;
        break;
      default:
        color = AppColors.textSecondary;
        icon = Icons.info;
    }
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 6),
          Text(
            action.replaceAll('_', ' ').toUpperCase(),
            style: AppTypography.caption.copyWith(
              color: color,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPagination() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border(
          top: BorderSide(color: AppColors.border),
        ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          IconButton(
            onPressed: _currentPage > 1
                ? () {
                    setState(() => _currentPage--);
                    _loadLogs();
                  }
                : null,
            icon: const Icon(Icons.chevron_left),
          ),
          const SizedBox(width: 16),
          ...List.generate(_totalPages.clamp(1, 5), (index) {
            final page = index + 1;
            final isSelected = page == _currentPage;
            
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: Material(
                color: isSelected ? AppColors.primary : AppColors.background,
                borderRadius: BorderRadius.circular(8),
                child: InkWell(
                  onTap: () {
                    setState(() => _currentPage = page);
                    _loadLogs();
                  },
                  borderRadius: BorderRadius.circular(8),
                  child: Container(
                    width: 36,
                    height: 36,
                    alignment: Alignment.center,
                    child: Text(
                      '$page',
                      style: AppTypography.bodyMedium.copyWith(
                        color: isSelected ? Colors.black : AppColors.textPrimary,
                        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                      ),
                    ),
                  ),
                ),
              ),
            );
          }),
          const SizedBox(width: 16),
          IconButton(
            onPressed: _currentPage < _totalPages
                ? () {
                    setState(() => _currentPage++);
                    _loadLogs();
                  }
                : null,
            icon: const Icon(Icons.chevron_right),
          ),
        ],
      ),
    );
  }

  void _exportLogs() {
    // Show export options dialog
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Export Logs'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.table_chart),
              title: const Text('Export as CSV'),
              onTap: () {
                Navigator.of(context).pop();
                _showExportSuccess('CSV');
              },
            ),
            ListTile(
              leading: const Icon(Icons.code),
              title: const Text('Export as JSON'),
              onTap: () {
                Navigator.of(context).pop();
                _showExportSuccess('JSON');
              },
            ),
          ],
        ),
      ),
    );
  }

