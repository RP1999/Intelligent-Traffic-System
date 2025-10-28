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
