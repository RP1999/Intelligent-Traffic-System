import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../providers/admin/drivers_provider.dart';
import '../../../models/driver.dart';
import '../../../widgets/admin/admin_sidebar.dart';
import '../../../widgets/common/empty_state_widget.dart';
import '../../../widgets/common/loading_widget.dart';
import 'driver_detail_screen.dart';

class DriversListScreen extends StatefulWidget {
  const DriversListScreen({super.key});

  @override
  State<DriversListScreen> createState() => _DriversListScreenState();
}

class _DriversListScreenState extends State<DriversListScreen> {
  final TextEditingController _searchController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DriversProvider>().loadDrivers(refresh: true);
    });
    
    _scrollController.addListener(_onScroll);
  }

  @override
