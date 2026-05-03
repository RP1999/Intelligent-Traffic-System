import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../providers/driver/driver_fines_provider.dart';
import '../../widgets/driver/fine_card.dart';
import '../../models/fine.dart';

class DriverFinesScreen extends StatefulWidget {
  const DriverFinesScreen({super.key});

  @override
  State<DriverFinesScreen> createState() => _DriverFinesScreenState();
}

class _DriverFinesScreenState extends State<DriverFinesScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DriverFinesProvider>().loadFines();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<DriverFinesProvider>(
      builder: (context, provider, _) {
        return Scaffold(
          backgroundColor: AppColors.background,
          body: RefreshIndicator(
            color: AppColors.primary,
            backgroundColor: AppColors.surface,
            onRefresh: () => provider.refresh(),
            child: CustomScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              slivers: [
                // App Bar
                const SliverAppBar(
                  floating: true,
                  backgroundColor: AppColors.surface,
                  automaticallyImplyLeading: false,
                  title: Text(
                    'My Fines',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ),

                SliverPadding(
                  padding: const EdgeInsets.all(16),
                  sliver: SliverList(
                    delegate: SliverChildListDelegate([
                      // Offline banner
                      if (provider.isOffline)
                        _buildOfflineBanner(),
                      if (provider.isOffline)
                        const SizedBox(height: 12),

                      // Summary header
                      _buildSummary(provider),
                      const SizedBox(height: 16),

                      // Filter tabs
                      _buildFilterTabs(provider),
                      const SizedBox(height: 16),
                    ]),
                  ),
                ),

                // Fines list
                if (provider.isLoading)
                  const SliverFillRemaining(
                    child: Center(
                      child: CircularProgressIndicator(
                          color: AppColors.primary),
                    ),
                  )
                else if (provider.fines.isEmpty)
                  SliverFillRemaining(
                    child: Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.check_circle,
                              color: AppColors.success, size: 60),
                          const SizedBox(height: 16),
                          const Text(
                            'No Fines',
                            style: TextStyle(
                              color: AppColors.textPrimary,
                              fontSize: 18,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            provider.statusFilter == 'all'
                                ? 'You have no fines recorded.'
                                : 'No ${provider.statusFilter} fines.',
                            style: const TextStyle(
                              color: AppColors.textSecondary,
                              fontSize: 14,
                            ),
                          ),
                        ],
                      ),
                    ),
                  )
                else
                  SliverPadding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    sliver: SliverList(
                      delegate: SliverChildBuilderDelegate(
                        (context, index) {
                          if (index == provider.fines.length) {
                            return const SizedBox(height: 80);
                          }
                          final fine = provider.fines[index];
                          return FineCard(
                            fine: fine,
                            onPayTap: fine.isPaid
                                ? null
                                : () => _navigateToPayment(context, fine),
                          );
                        },
                        childCount: provider.fines.length + 1,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildOfflineBanner() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.warning.withAlpha(30),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.warning.withAlpha(80)),
      ),
      child: Row(
        children: [
          Icon(Icons.wifi_off, color: AppColors.warning, size: 18),
          const SizedBox(width: 10),
          const Expanded(
            child: Text(
              'You are offline. Showing cached data.',
              style: TextStyle(
                color: AppColors.warning,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSummary(DriverFinesProvider provider) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppColors.surface,
            AppColors.surfaceVariant.withOpacity(0.8),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border.withOpacity(0.5)),
      ),
      child: Column(
        children: [
          // Total unpaid
          Text(
            '${provider.currency} ${provider.totalUnpaid.toStringAsFixed(0)}',
            style: const TextStyle(
              color: AppColors.warning,
              fontSize: 32,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Total Unpaid',
            style: TextStyle(
              color: AppColors.textSecondary,
              fontSize: 13,
            ),
          ),
          const SizedBox(height: 16),
          // Stats row
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _SummaryItem(
                label: 'Unpaid',
                value: '${provider.unpaidCount}',
                color: AppColors.warning,
              ),
              Container(width: 1, height: 30, color: AppColors.border),
              _SummaryItem(
                label: 'Paid',
                value: '${provider.paidCount}',
                color: AppColors.success,
              ),
              Container(width: 1, height: 30, color: AppColors.border),
              _SummaryItem(
                label: 'Total Paid',
                value: '${provider.currency} ${provider.totalPaid.toStringAsFixed(0)}',
                color: AppColors.success,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildFilterTabs(DriverFinesProvider provider) {
    final filters = ['all', 'unpaid', 'paid'];
    return Row(
      children: filters.map((filter) {
        final isSelected = provider.statusFilter == filter;
        return Expanded(
          child: GestureDetector(
            onTap: () => provider.setStatusFilter(filter),
            child: Container(
              margin: EdgeInsets.only(
                right: filter != filters.last ? 8 : 0,
              ),
              padding: const EdgeInsets.symmetric(vertical: 10),
              decoration: BoxDecoration(
                color: isSelected
                    ? AppColors.primary.withOpacity(0.15)
                    : AppColors.surface,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: isSelected
                      ? AppColors.primary.withOpacity(0.5)
                      : AppColors.border.withOpacity(0.3),
                ),
              ),
              child: Text(
                filter[0].toUpperCase() + filter.substring(1),
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: isSelected ? AppColors.primary : AppColors.textSecondary,
                  fontSize: 13,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                ),
              ),
            ),
          ),
        );
      }).toList(),
    );
  }

  void _navigateToPayment(BuildContext context, Fine fine) {
    Navigator.of(context).pushNamed('/driver/payment', arguments: fine);
  }
}

class _SummaryItem extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _SummaryItem({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            color: color,
            fontSize: 16,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: const TextStyle(
            color: AppColors.textSecondary,
            fontSize: 11,
          ),
        ),
      ],
    );
  }
}
