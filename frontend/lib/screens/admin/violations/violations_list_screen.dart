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
