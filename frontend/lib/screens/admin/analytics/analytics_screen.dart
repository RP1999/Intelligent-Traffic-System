import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:fl_chart/fl_chart.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../providers/admin/analytics_provider.dart';
import '../../../widgets/admin/admin_sidebar.dart';
import '../../../widgets/common/loading_widget.dart';

class AnalyticsScreen extends StatefulWidget {
  const AnalyticsScreen({super.key});

  @override
  State<AnalyticsScreen> createState() => _AnalyticsScreenState();
}

class _AnalyticsScreenState extends State<AnalyticsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AnalyticsProvider>().loadAllAnalytics();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          // Sidebar
          AdminSidebar(
            selectedIndex: 4, // Analytics
            onItemSelected: (index) => _handleNavigation(index),
          ),
          
          // Main content
          Expanded(
            child: Container(
              color: AppColors.background,
              child: CustomScrollView(
                slivers: [
                  SliverToBoxAdapter(child: _buildHeader()),
                  SliverToBoxAdapter(child: _buildStatsCards()),
                  SliverToBoxAdapter(child: _buildChartsRow()),
                  SliverToBoxAdapter(child: _buildHotspotsSection()),
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
        Navigator.of(context).pushReplacementNamed('/admin/violations');
        break;
      case 3:
        Navigator.of(context).pushReplacementNamed('/admin/drivers');
        break;
      case 4:
        // Already here - Analytics
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
                'Analytics Dashboard',
                style: AppTypography.h1.copyWith(fontSize: 28),
              ),
              const SizedBox(height: 4),
              Text(
                'Traffic violation statistics and trends',
                style: AppTypography.bodyMedium.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
          const Spacer(),
          
          // Period selector
          Consumer<AnalyticsProvider>(
            builder: (context, provider, _) {
              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                decoration: BoxDecoration(
                  color: AppColors.surfaceVariant,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<int>(
                    value: provider.trendPeriod,
                    dropdownColor: AppColors.surface,
                    items: const [
                      DropdownMenuItem(value: 7, child: Text('Last 7 Days')),
                      DropdownMenuItem(value: 14, child: Text('Last 14 Days')),
                      DropdownMenuItem(value: 30, child: Text('Last 30 Days')),
                    ],
                    onChanged: (value) {
                      if (value != null) {
                        provider.setTrendPeriod(value);
                      }
                    },
                  ),
                ),
              );
            },
          ),
          const SizedBox(width: 16),
          
          // Refresh button
          IconButton(
            onPressed: () {
              context.read<AnalyticsProvider>().loadAllAnalytics();
            },
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
          ),
        ],
      ),
    );
  }

  Widget _buildStatsCards() {
    return Consumer<AnalyticsProvider>(
      builder: (context, provider, _) {
        if (provider.statsState == LoadingState.loading) {
          return const SizedBox(
            height: 150,
            child: Center(child: CircularProgressIndicator()),
          );
        }

        final stats = provider.stats;
        if (stats == null) {
          return const SizedBox.shrink();
        }

        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Row(
            children: [
              Expanded(
                child: _buildStatCard(
                  'Violations Today',
                  stats.violationsToday.toString(),
                  Icons.warning_amber,
                  AppColors.warning,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: _buildStatCard(
                  'This Week',
                  stats.violationsThisWeek.toString(),
                  Icons.calendar_today,
                  AppColors.info,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: _buildStatCard(
                  'Avg Risk Score',
                  '${stats.averageRiskScore.toStringAsFixed(1)}%',
                  Icons.speed,
                  stats.averageRiskScore > 50 ? AppColors.error : AppColors.success,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: _buildStatCard(
                  'Pending Fines',
                  '\$${stats.pendingFines.toStringAsFixed(0)}',
                  Icons.attach_money,
                  AppColors.primary,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildStatCard(String title, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.2)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 10,
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: color.withOpacity(0.15),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: color, size: 28),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: AppTypography.bodySmall.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  value,
                  style: AppTypography.h3.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChartsRow() {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Line Chart - Violation Trends
          Expanded(
            flex: 2,
            child: _buildTrendChart(),
          ),
          const SizedBox(width: 24),
          
          // Pie Chart - Distribution
          Expanded(
            flex: 1,
            child: _buildDistributionChart(),
          ),
        ],
      ),
    );
  }

  Widget _buildTrendChart() {
    return Consumer<AnalyticsProvider>(
      builder: (context, provider, _) {
        return Container(
          height: 350,
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
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Container(
                padding: const EdgeInsets.all(20),
                decoration: const BoxDecoration(
                  border: Border(
                    bottom: BorderSide(color: AppColors.border),
                  ),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.show_chart, color: AppColors.primary),
                    const SizedBox(width: 12),
                    Text(
                      'Violation Trends (${provider.trendPeriod} Days)',
                      style: AppTypography.h3,
                    ),
                  ],
                ),
              ),
              
              // Chart
              Expanded(
                child: provider.trendsState == LoadingState.loading
                    ? const LoadingWidget(message: 'Loading trends...')
                    : provider.trends == null || provider.trends!.trends.isEmpty
                        ? _buildEmptyChart('No trend data available')
                        : Padding(
                            padding: const EdgeInsets.all(20),
                            child: LineChart(_buildLineChartData(provider)),
                          ),
              ),
            ],
          ),
        );
      },
    );
  }

  LineChartData _buildLineChartData(AnalyticsProvider provider) {
    final trends = provider.trends!.trends;
    
    final spots = trends.asMap().entries.map((entry) {
      return FlSpot(entry.key.toDouble(), entry.value.total.toDouble());
    }).toList();

    return LineChartData(
      gridData: FlGridData(
        show: true,
        drawVerticalLine: false,
        horizontalInterval: 5,
        getDrawingHorizontalLine: (value) {
          return FlLine(
            color: AppColors.border,
            strokeWidth: 1,
          );
        },
      ),
      titlesData: FlTitlesData(
        show: true,
        rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        bottomTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: true,
            reservedSize: 30,
            interval: 1,
            getTitlesWidget: (value, meta) {
              if (value.toInt() >= trends.length || value.toInt() < 0) {
                return const SizedBox.shrink();
              }
              final date = trends[value.toInt()].date;
              return Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  date.substring(5), // MM-DD
                  style: AppTypography.labelSmall.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              );
            },
          ),
        ),
        leftTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: true,
            reservedSize: 40,
            getTitlesWidget: (value, meta) {
              return Text(
                value.toInt().toString(),
                style: AppTypography.labelSmall.copyWith(
                  color: AppColors.textSecondary,
                ),
              );
            },
          ),
        ),
      ),
      borderData: FlBorderData(show: false),
      lineBarsData: [
        LineChartBarData(
          spots: spots,
          isCurved: true,
          color: AppColors.primary,
          barWidth: 3,
          isStrokeCapRound: true,
          dotData: FlDotData(
            show: true,
            getDotPainter: (spot, percent, barData, index) {
              return FlDotCirclePainter(
                radius: 4,
                color: AppColors.primary,
                strokeWidth: 2,
                strokeColor: AppColors.surface,
              );
            },
          ),
          belowBarData: BarAreaData(
            show: true,
            gradient: LinearGradient(
              colors: [
                AppColors.primary.withOpacity(0.3),
                AppColors.primary.withOpacity(0.05),
              ],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
          ),
        ),
      ],
      lineTouchData: LineTouchData(
        touchTooltipData: LineTouchTooltipData(
          getTooltipItems: (touchedSpots) {
            return touchedSpots.map((spot) {
              return LineTooltipItem(
                '${spot.y.toInt()} violations',
                AppTypography.bodySmall.copyWith(color: Colors.white),
              );
            }).toList();
          },
        ),
      ),
    );
  }

  Widget _buildDistributionChart() {
    return Consumer<AnalyticsProvider>(
      builder: (context, provider, _) {
        return Container(
          height: 350,
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
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Container(
                padding: const EdgeInsets.all(20),
                decoration: const BoxDecoration(
                  border: Border(
                    bottom: BorderSide(color: AppColors.border),
                  ),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.pie_chart, color: AppColors.primary),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'Violation Distribution',
                        style: AppTypography.h3,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ),
              
              // Chart
              Expanded(
                child: provider.trendsState == LoadingState.loading
                    ? const LoadingWidget(message: 'Loading...')
                    : _buildPieChart(provider),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildPieChart(AnalyticsProvider provider) {
    final distribution = provider.getViolationDistribution();
    
    if (distribution.isEmpty) {
      return _buildEmptyChart('No distribution data');
    }

    final colors = {
      'red_light': AppColors.error,
      'speeding': AppColors.warning,
      'parking': AppColors.info,
      'no_parking': AppColors.info,
      'lane_weaving': AppColors.riskMedium,
      'lane_drift': AppColors.riskHigh,
    };

    final sections = distribution.entries.map((entry) {
      final color = colors[entry.key] ?? AppColors.textSecondary;
      return PieChartSectionData(
        color: color,
        value: entry.value,
        title: '${entry.value.toStringAsFixed(0)}%',
        radius: 60,
        titleStyle: AppTypography.labelSmall.copyWith(
          color: Colors.white,
          fontWeight: FontWeight.bold,
        ),
      );
    }).toList();

    return Column(
      children: [
        Expanded(
          child: PieChart(
            PieChartData(
              sections: sections,
              centerSpaceRadius: 40,
              sectionsSpace: 2,
            ),
          ),
        ),
        
        // Legend
        Padding(
          padding: const EdgeInsets.all(16),
          child: Wrap(
            spacing: 16,
            runSpacing: 8,
            children: distribution.entries.map((entry) {
              final color = colors[entry.key] ?? AppColors.textSecondary;
              return Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 12,
                    height: 12,
                    decoration: BoxDecoration(
                      color: color,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    _formatTypeName(entry.key),
                    style: AppTypography.labelSmall,
                  ),
                ],
              );
            }).toList(),
          ),
        ),
      ],
    );
  }

  Widget _buildHotspotsSection() {
    return Consumer<AnalyticsProvider>(
      builder: (context, provider, _) {
        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          child: Container(
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
