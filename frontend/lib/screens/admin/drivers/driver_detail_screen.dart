import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../providers/admin/drivers_provider.dart';
import '../../../models/driver.dart';
import '../../../widgets/common/loading_widget.dart';

class DriverDetailScreen extends StatefulWidget {
  final String driverId;

  const DriverDetailScreen({
    super.key,
    required this.driverId,
  });

  @override
  State<DriverDetailScreen> createState() => _DriverDetailScreenState();
}

class _DriverDetailScreenState extends State<DriverDetailScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DriversProvider>().loadDriverDetail(widget.driverId);
    });
  }

  @override
  Widget build(BuildContext context) {
