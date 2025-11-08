import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/config/app_config.dart';
import '../../../providers/admin/violations_provider.dart';
import '../../../models/violation.dart';
import '../../../widgets/common/loading_widget.dart';

class ViolationDetailScreen extends StatefulWidget {
  final String violationId;

  const ViolationDetailScreen({
    super.key,
    required this.violationId,
  });

  @override
  State<ViolationDetailScreen> createState() => _ViolationDetailScreenState();
}

class _ViolationDetailScreenState extends State<ViolationDetailScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ViolationsProvider>().loadViolationDetail(widget.violationId);
    });
  }

  @override
