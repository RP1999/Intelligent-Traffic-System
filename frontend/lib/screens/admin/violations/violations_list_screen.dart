import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../providers/admin/violations_provider.dart';
import '../../../models/violation.dart';
import '../../../widgets/admin/admin_sidebar.dart';
import '../../../widgets/common/empty_state_widget.dart';
import '../../../widgets/common/loading_widget.dart';
import 'violation_detail_screen.dart';

class ViolationsListScreen extends StatefulWidget {
  const ViolationsListScreen({super.key});

  @override
  State<ViolationsListScreen> createState() => _ViolationsListScreenState();
}

class _ViolationsListScreenState extends State<ViolationsListScreen> {
  final TextEditingController _searchController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  String? _selectedStatus;
  String? _selectedType;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ViolationsProvider>().loadViolations(refresh: true);
    });
    
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >= 
        _scrollController.position.maxScrollExtent - 200) {
      context.read<ViolationsProvider>().loadNextPage();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          // Sidebar
          AdminSidebar(
            selectedIndex: 2, // Violations index
            onItemSelected: (index) => _handleNavigation(index),
          ),
          
          // Main content
          Expanded(
            child: Container(
              color: AppColors.background,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildHeader(),
                  _buildFilters(),
                  Expanded(child: _buildViolationsTable()),
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
        // Already here
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
        Navigator.of(context).pushReplacementNamed('/admin/settings');
        break;
    }
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(24),
      child: Row(
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Violation Management',
                style: AppTypography.h1.copyWith(fontSize: 28),
              ),
              const SizedBox(height: 4),
              Consumer<ViolationsProvider>(
                builder: (context, provider, _) {
                  return Text(
                    '${provider.total} total violations',
                    style: AppTypography.bodyMedium.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  );
                },
              ),
            ],
          ),
          const Spacer(),
          
          // Refresh button
          IconButton(
            onPressed: () {
              context.read<ViolationsProvider>().loadViolations(refresh: true);
            },
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
          ),
          const SizedBox(width: 8),
          
          // Analytics button
          ElevatedButton.icon(
            onPressed: () {
              Navigator.of(context).pushNamed('/admin/analytics');
            },
            icon: const Icon(Icons.analytics),
            label: const Text('Analytics'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: AppColors.background,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilters() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        children: [
          // Search box
          Expanded(
            flex: 2,
            child: TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: 'Search by license plate...',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchController.clear();
                          context.read<ViolationsProvider>().setSearchQuery('');
                        },
                      )
                    : null,
                filled: true,
                fillColor: AppColors.surfaceVariant,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              ),
              onChanged: (value) {
                context.read<ViolationsProvider>().setSearchQuery(value);
              },
            ),
          ),
          const SizedBox(width: 16),
          
          // Status filter dropdown
          Expanded(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              decoration: BoxDecoration(
                color: AppColors.surfaceVariant,
                borderRadius: BorderRadius.circular(12),
              ),
              child: DropdownButtonHideUnderline(
                child: DropdownButton<String>(
                  value: _selectedStatus,
                  hint: const Text('Status'),
                  isExpanded: true,
                  dropdownColor: AppColors.surface,
                  items: const [
                    DropdownMenuItem(value: null, child: Text('All Status')),
                    DropdownMenuItem(value: 'unpaid', child: Text('Unpaid')),
                    DropdownMenuItem(value: 'paid', child: Text('Paid')),
                    DropdownMenuItem(value: 'disputed', child: Text('Disputed')),
                  ],
                  onChanged: (value) {
                    setState(() => _selectedStatus = value);
                    context.read<ViolationsProvider>().setStatusFilter(value);
                  },
                ),
              ),
            ),
          ),
          const SizedBox(width: 16),
          
          // Type filter dropdown
          Expanded(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              decoration: BoxDecoration(
                color: AppColors.surfaceVariant,
                borderRadius: BorderRadius.circular(12),
              ),
              child: DropdownButtonHideUnderline(
                child: DropdownButton<String>(
                  value: _selectedType,
                  hint: const Text('Violation Type'),
                  isExpanded: true,
                  dropdownColor: AppColors.surface,
                  items: const [
                    DropdownMenuItem(value: null, child: Text('All Types')),
                    DropdownMenuItem(value: 'red_light', child: Text('Red Light')),
                    DropdownMenuItem(value: 'speeding', child: Text('Speeding')),
                    DropdownMenuItem(value: 'parking', child: Text('Parking')),
                    DropdownMenuItem(value: 'lane_weaving', child: Text('Lane Weaving')),
                  ],
                  onChanged: (value) {
                    setState(() => _selectedType = value);
                    context.read<ViolationsProvider>().setTypeFilter(value);
                  },
                ),
              ),
            ),
          ),
          const SizedBox(width: 16),
          
          // Clear filters button
          TextButton.icon(
            onPressed: () {
              setState(() {
                _selectedStatus = null;
                _selectedType = null;
                _searchController.clear();
              });
              context.read<ViolationsProvider>().clearFilters();
            },
            icon: const Icon(Icons.clear_all),
            label: const Text('Clear'),
          ),
        ],
      ),
    );
  }

  Widget _buildViolationsTable() {
    return Consumer<ViolationsProvider>(
      builder: (context, provider, _) {
        if (provider.state == LoadingState.loading && provider.violations.isEmpty) {
          return const LoadingWidget(message: 'Loading violations...');
        }

        if (provider.state == LoadingState.error && provider.violations.isEmpty) {
          return EmptyStateWidget(
            icon: Icons.error_outline,
            title: 'Error Loading Violations',
            message: provider.errorMessage ?? 'An unknown error occurred',
            actionLabel: 'Retry',
            onAction: () => provider.loadViolations(refresh: true),
          );
        }

        if (provider.violations.isEmpty) {
          return const EmptyStateWidget(
            icon: Icons.check_circle_outline,
            title: 'No Violations Found',
            message: 'There are no violations matching your filters.',
          );
        }

        return Container(
          margin: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.1),
                blurRadius: 10,
              ),
            ],
          ),
          child: Column(
            children: [
              // Table header
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.surfaceVariant,
                  borderRadius: const BorderRadius.vertical(
                    top: Radius.circular(16),
                  ),
                ),
                child: Row(
                  children: [
                    _buildHeaderCell('License Plate', flex: 2),
                    _buildHeaderCell('Type', flex: 2),
                    _buildHeaderCell('Fine', flex: 1),
                    _buildHeaderCell('Time', flex: 2),
                    _buildHeaderCell('Status', flex: 1),
                    _buildHeaderCell('Actions', flex: 1),
                  ],
                ),
              ),
              
              // Table body
              Expanded(
                child: ListView.builder(
                  controller: _scrollController,
                  itemCount: provider.violations.length + (provider.hasMore ? 1 : 0),
                  itemBuilder: (context, index) {
                    if (index >= provider.violations.length) {
                      return const Padding(
                        padding: EdgeInsets.all(16),
                        child: Center(
                          child: CircularProgressIndicator(
                            color: AppColors.primary,
                          ),
                        ),
                      );
                    }
                    
                    final violation = provider.violations[index];
                    return _buildViolationRow(violation, index);
                  },
                ),
              ),
              
              // Pagination info
              Container(
                padding: const EdgeInsets.all(16),
                decoration: const BoxDecoration(
                  border: Border(
                    top: BorderSide(color: AppColors.border),
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Showing ${provider.violations.length} of ${provider.total} violations',
                      style: AppTypography.bodySmall.copyWith(
                        color: AppColors.textSecondary,
                      ),
                    ),
                    Text(
                      'Page ${provider.currentPage} of ${provider.totalPages}',
                      style: AppTypography.bodySmall.copyWith(
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildHeaderCell(String text, {int flex = 1}) {
    return Expanded(
      flex: flex,
      child: Text(
        text,
        style: AppTypography.labelLarge.copyWith(
          color: AppColors.textSecondary,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _buildViolationRow(Violation violation, int index) {
    final isEven = index % 2 == 0;
    final dateFormat = DateFormat('MMM dd, yyyy HH:mm');

    return InkWell(
      onTap: () => _openViolationDetail(violation),
      child: Container(
        padding: const EdgeInsets.all(16),
        color: isEven ? AppColors.surface : AppColors.surfaceVariant.withOpacity(0.3),
        child: Row(
          children: [
            // License Plate
            Expanded(
              flex: 2,
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: AppColors.primary.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: AppColors.primary.withOpacity(0.3)),
                    ),
                    child: Text(
                      violation.licensePlate ?? violation.driverId,
                      style: AppTypography.labelLarge.copyWith(
                        fontWeight: FontWeight.bold,
                        color: AppColors.primary,
                        fontFamily: 'monospace',
                      ),
                    ),
                  ),
                ],
              ),
            ),
            
            // Type
            Expanded(
              flex: 2,
              child: Row(
                children: [
                  _buildViolationTypeIcon(violation.violationType),
                  const SizedBox(width: 8),
                  Flexible(
                    child: Text(
                      violation.displayType,
                      style: AppTypography.bodyMedium,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
            
            // Fine
            Expanded(
              flex: 1,
              child: Text(
                '\$${violation.fineAmount.toStringAsFixed(0)}',
                style: AppTypography.labelLarge.copyWith(
                  color: _getFineColor(violation.fineAmount),
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            
            // Time
            Expanded(
              flex: 2,
              child: Text(
                dateFormat.format(violation.timestamp),
                style: AppTypography.bodySmall.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ),
            
            // Status
            Expanded(
              flex: 1,
              child: _buildStatusBadge(violation.status),
            ),
            
            // Actions
            Expanded(
              flex: 1,
              child: Row(
                children: [
                  IconButton(
                    onPressed: () => _openViolationDetail(violation),
                    icon: const Icon(Icons.visibility),
                    tooltip: 'View Details',
                    iconSize: 20,
                  ),
                  IconButton(
                    onPressed: () => _showDeleteConfirmation(violation),
                    icon: const Icon(Icons.delete_outline),
                    tooltip: 'Dismiss',
                    iconSize: 20,
                    color: AppColors.error,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildViolationTypeIcon(String type) {
    IconData icon;
    Color color;
    
    switch (type.toLowerCase()) {
      case 'red_light':
        icon = Icons.traffic;
        color = AppColors.error;
        break;
      case 'speeding':
        icon = Icons.speed;
        color = AppColors.warning;
        break;
      case 'parking':
      case 'no_parking':
        icon = Icons.local_parking;
        color = AppColors.info;
        break;
      case 'lane_weaving':
      case 'lane_drift':
        icon = Icons.swap_horiz;
        color = AppColors.riskMedium;
        break;
      default:
        icon = Icons.warning;
        color = AppColors.textSecondary;
    }
    
    return Icon(icon, color: color, size: 20);
  }

  Color _getFineColor(double amount) {
    if (amount >= 200) return AppColors.error;
    if (amount >= 100) return AppColors.warning;
    return AppColors.success;
  }

  Widget _buildStatusBadge(String status) {
    Color bgColor;
    Color textColor;
    String displayText;
    
    switch (status.toLowerCase()) {
      case 'paid':
        bgColor = AppColors.success.withOpacity(0.2);
        textColor = AppColors.success;
        displayText = 'Paid';
        break;
      case 'disputed':
        bgColor = AppColors.warning.withOpacity(0.2);
        textColor = AppColors.warning;
        displayText = 'Disputed';
        break;
      case 'verified':
        bgColor = AppColors.info.withOpacity(0.2);
        textColor = AppColors.info;
        displayText = 'Verified';
        break;
      case 'dismissed':
        bgColor = AppColors.textSecondary.withOpacity(0.2);
        textColor = AppColors.textSecondary;
        displayText = 'Dismissed';
        break;
      default:
        bgColor = AppColors.error.withOpacity(0.2);
        textColor = AppColors.error;
        displayText = 'Unpaid';
    }
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        displayText,
        style: AppTypography.labelSmall.copyWith(
          color: textColor,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  void _openViolationDetail(Violation violation) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => ViolationDetailScreen(
          violationId: violation.violationId,
        ),
      ),
    );
  }

  Future<void> _showDeleteConfirmation(Violation violation) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Dismiss Violation'),
        content: Text(
          'Are you sure you want to dismiss this violation for ${violation.licensePlate ?? violation.driverId}?\n\nThis action cannot be undone.',
        ),
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
            child: const Text('Dismiss'),
          ),
        ],
      ),
    );
    
    if (confirmed == true && mounted) {
      final success = await context.read<ViolationsProvider>().deleteViolation(
        violation.violationId,
      );
      
      if (success && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Violation dismissed successfully'),
            backgroundColor: AppColors.success,
          ),
        );
      }
    }
  }
}
