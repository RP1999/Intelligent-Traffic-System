import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../core/services/notification_service.dart';
import '../../providers/auth_provider.dart';
import '../../providers/driver/driver_home_provider.dart';
import '../../widgets/driver/score_circle.dart';
import '../../models/driver_profile.dart';
import '../../models/community.dart';

class DriverProfileScreen extends StatefulWidget {
  const DriverProfileScreen({super.key});

  @override
  State<DriverProfileScreen> createState() => _DriverProfileScreenState();
}

class _DriverProfileScreenState extends State<DriverProfileScreen> {
  List<SafetyTip> _tips = [];
  bool _loadingTips = true;
  bool _audioNotificationsEnabled = true;

  @override
  void initState() {
    super.initState();
    _loadSafetyTips();
    _loadAudioSetting();
  }
  
  void _loadAudioSetting() {
    _audioNotificationsEnabled = NotificationService().isTtsEnabled;
  }

  Future<void> _loadSafetyTips() async {
    // Hardcoded safety tips (matches backend /community/safety-tips response)
    await Future.delayed(const Duration(milliseconds: 300));
    if (!mounted) return;
    setState(() {
      _tips = [
        SafetyTip(
          id: '1',
          category: 'general',
          tip: 'Always maintain a safe following distance of at least 3 seconds.',
        ),
        SafetyTip(
          id: '2',
          category: 'lane_discipline',
          tip: 'Use turn signals at least 100 meters before changing lanes.',
        ),
        SafetyTip(
          id: '3',
          category: 'parking',
          tip: 'Never park in handicapped zones without proper authorization.',
        ),
        SafetyTip(
          id: '4',
          category: 'speed',
          tip: 'Reduce speed in areas with high pedestrian activity.',
        ),
        SafetyTip(
          id: '5',
          category: 'emergency',
          tip: 'Always yield to emergency vehicles and move to the side of the road.',
        ),
      ];
      _loadingTips = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final homeProvider = context.watch<DriverHomeProvider>();
    final authProvider = context.watch<AuthProvider>();
    final DriverProfile? profile = homeProvider.profile;
    final user = authProvider.user;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: RefreshIndicator(
        color: AppColors.primary,
        backgroundColor: AppColors.surface,
        onRefresh: () => homeProvider.refresh(),
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            // App Bar
            const SliverAppBar(
              floating: true,
              backgroundColor: AppColors.surface,
              automaticallyImplyLeading: false,
              title: Text(
                'Profile',
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
                  // Profile header
                  _buildProfileHeader(user, profile),
                  const SizedBox(height: 20),

                  // Score Card
                  _buildScoreCard(profile),
                  const SizedBox(height: 16),

                  // Stats
                  _buildStatsGrid(profile),
                  const SizedBox(height: 20),

                  // Safety Tips
                  _buildSafetyTips(),
                  const SizedBox(height: 20),

                  // Account Actions
                  _buildAccountActions(context),
                  const SizedBox(height: 80),
                ]),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProfileHeader(User? user, DriverProfile? profile) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppColors.surfaceVariant,
            AppColors.surface,
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.primary.withOpacity(0.2)),
      ),
      child: Row(
        children: [
          // Avatar
          Container(
            width: 70,
            height: 70,
            decoration: BoxDecoration(
              gradient: AppColors.primaryGradient,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Center(
              child: Text(
                (user?.name ?? 'D')[0].toUpperCase(),
                style: const TextStyle(
                  color: AppColors.background,
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  user?.name ?? profile?.displayName ?? 'Driver',
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Icon(Icons.phone, size: 14, color: AppColors.textSecondary),
                    const SizedBox(width: 4),
                    Text(
                      user?.phone ?? '',
                      style: const TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Icon(Icons.directions_car,
                        size: 14, color: AppColors.primary),
                    const SizedBox(width: 4),
                    Text(
                      user?.plateNumber ?? profile?.plateNumber ?? '',
                      style: const TextStyle(
                        color: AppColors.primary,
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          // Edit button
          GestureDetector(
            onTap: () => _showEditProfileDialog(context, user),
            child: Container(
              width: 38,
              height: 38,
              decoration: BoxDecoration(
                color: AppColors.primary.withOpacity(0.12),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(
                Icons.edit_outlined,
                color: AppColors.primary,
                size: 20,
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showEditProfileDialog(BuildContext context, User? user) {
    final nameController = TextEditingController(text: user?.name ?? '');
    final phoneController = TextEditingController(text: user?.phone ?? '');
    // Pull license number from DriverProfile if not yet in User cache
    final profile = context.read<DriverHomeProvider>().profile;
    final licenseNumber = user?.licenseNumber ?? profile?.licenseNumber ?? '';
    final formKey = GlobalKey<FormState>();
    bool isSaving = false;

    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return Padding(
              padding: EdgeInsets.only(
                left: 24,
                right: 24,
                top: 24,
                bottom: MediaQuery.of(context).viewInsets.bottom + 24,
              ),
              child: Form(
                key: formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Handle
                    Center(
                      child: Container(
                        width: 40,
                        height: 4,
                        decoration: BoxDecoration(
                          color: AppColors.border,
                          borderRadius: BorderRadius.circular(2),
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      'Edit Profile',
                      style: TextStyle(
                        color: AppColors.textPrimary,
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Update your personal information',
                      style: TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 13,
                      ),
                    ),
                    const SizedBox(height: 24),
                    // Name field
                    TextFormField(
                      controller: nameController,
                      style: const TextStyle(color: AppColors.textPrimary),
                      decoration: InputDecoration(
                        labelText: 'Full Name',
                        labelStyle: const TextStyle(color: AppColors.textSecondary),
                        prefixIcon: const Icon(Icons.person_outline, color: AppColors.textSecondary),
                        filled: true,
                        fillColor: AppColors.background,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide: BorderSide(color: AppColors.border),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide: BorderSide(color: AppColors.border.withOpacity(0.5)),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide: const BorderSide(color: AppColors.primary),
                        ),
                      ),
                      validator: (value) {
                        if (value == null || value.trim().isEmpty) {
                          return 'Please enter your name';
                        }
                        if (value.trim().length < 2) {
                          return 'Name must be at least 2 characters';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 16),
                    // Phone field
                    TextFormField(
                      controller: phoneController,
                      style: const TextStyle(color: AppColors.textPrimary),
                      keyboardType: TextInputType.phone,
                      decoration: InputDecoration(
                        labelText: 'Phone Number',
                        labelStyle: const TextStyle(color: AppColors.textSecondary),
                        prefixIcon: const Icon(Icons.phone_outlined, color: AppColors.textSecondary),
                        filled: true,
                        fillColor: AppColors.background,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide: BorderSide(color: AppColors.border),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide: BorderSide(color: AppColors.border.withOpacity(0.5)),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide: const BorderSide(color: AppColors.primary),
                        ),
                      ),
                      validator: (value) {
                        if (value == null || value.trim().isEmpty) {
                          return 'Please enter your phone number';
                        }
                        if (value.trim().length < 10) {
                          return 'Phone must be at least 10 digits';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 16),
                    // Licence number (read-only)
                    _ReadOnlyInfoField(
                      icon: Icons.credit_card_outlined,
                      label: 'Licence Number',
                      value: licenseNumber.isNotEmpty ? licenseNumber : 'Not set',
                    ),
                    const SizedBox(height: 12),
                    // Vehicle plate (read-only)
                    _ReadOnlyInfoField(
                      icon: Icons.directions_car_outlined,
                      label: 'Vehicle Plate',
                      value: (user?.plateNumber ?? profile?.plateNumber ?? '').isNotEmpty
                          ? (user?.plateNumber ?? profile?.plateNumber ?? '')
                          : 'Not set',
                    ),
                    const SizedBox(height: 24),
                    // Save button
                    SizedBox(
                      width: double.infinity,
                      height: 50,
                      child: ElevatedButton(
                        onPressed: isSaving
                            ? null
                            : () async {
                                if (!formKey.currentState!.validate()) return;
                                setModalState(() => isSaving = true);

                                final authProvider = context.read<AuthProvider>();
                                final newName = nameController.text.trim();
                                final newPhone = phoneController.text.trim();

                                // Only send changed fields
                                String? sendName = (newName != (user?.name ?? '')) ? newName : null;
                                String? sendPhone = (newPhone != (user?.phone ?? '')) ? newPhone : null;

                                if (sendName == null && sendPhone == null) {
                                  Navigator.pop(context);
                                  return;
                                }

                                final success = await authProvider.updateProfile(
                                  name: sendName,
                                  phone: sendPhone,
                                );

                                setModalState(() => isSaving = false);

                                if (success && context.mounted) {
                                  Navigator.pop(context);
                                  ScaffoldMessenger.of(this.context).showSnackBar(
                                    const SnackBar(
                                      content: Text('Profile updated successfully'),
                                      backgroundColor: AppColors.success,
                                    ),
                                  );
                                  // Refresh home provider data
                                  this.context.read<DriverHomeProvider>().refresh();
                                } else if (context.mounted) {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(
                                      content: Text(authProvider.error ?? 'Update failed'),
                                      backgroundColor: AppColors.error,
                                    ),
                                  );
                                }
                              },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.primary,
                          foregroundColor: AppColors.background,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(14),
                          ),
                        ),
                        child: isSaving
                            ? const SizedBox(
                                width: 22,
                                height: 22,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: AppColors.background,
                                ),
                              )
                            : const Text(
                                'Save Changes',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _buildScoreCard(DriverProfile? profile) {
    final score = profile?.currentScore ?? 100;
    final riskLevel = profile?.displayRiskLevel ?? 'Good';

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border.withOpacity(0.5)),
      ),
      child: Row(
        children: [
          ScoreCircle(
            score: score,
            size: 100,
            strokeWidth: 8,
          ),
          const SizedBox(width: 24),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Driver Safety Score',
                  style: TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '$score / 100',
                  style: TextStyle(
                    color: AppColors.getScoreColor(score),
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppColors.getScoreColor(score).withOpacity(0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    riskLevel,
                    style: TextStyle(
                      color: AppColors.getScoreColor(score),
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatsGrid(DriverProfile? profile) {
    final score = profile?.currentScore ?? 100;
    final riskLevel = profile?.displayRiskLevel ?? 'Good';
    // Pick a colour that matches the risk badge in the score card
    final riskColor = AppColors.getScoreColor(score);

    return Row(
      children: [
        Expanded(
          child: _StatBoxe(
            icon: Icons.shield_outlined,
            label: 'Safety Score',
            value: '$score pts',
            color: riskColor,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _StatBoxe(
            icon: Icons.verified_outlined,
            label: 'Risk Level',
            value: riskLevel,
            color: riskColor,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _StatBoxe(
            icon: Icons.warning_amber,
            label: 'Violations',
            value: '${profile?.totalViolations ?? 0}',
            color: AppColors.warning,
          ),
        ),
      ],
    );
  }

  Widget _buildSafetyTips() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.lightbulb_outline, color: AppColors.primary, size: 20),
            const SizedBox(width: 8),
            const Text(
              'Safety Tips',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        if (_loadingTips)
          const Center(
            child: CircularProgressIndicator(
                color: AppColors.primary, strokeWidth: 2),
          )
        else
          ..._tips.map((tip) => Container(
                margin: const EdgeInsets.only(bottom: 10),
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(12),
                  border:
                      Border.all(color: AppColors.border.withOpacity(0.3)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      _getTipIcon(tip.category),
                      color: AppColors.primary,
                      size: 18,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        tip.tip,
                        style: const TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 13,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              )),
      ],
    );
  }

  Widget _buildAccountActions(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Account',
          style: TextStyle(
            color: AppColors.textPrimary,
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 12),
        _ActionTile(
          icon: Icons.edit_outlined,
          label: 'Edit Profile',
          subtitle: 'Update your name or phone number',
          onTap: () {
            final user = context.read<AuthProvider>().user;
            _showEditProfileDialog(context, user);
          },
        ),
        // Audio notifications toggle
        _AudioToggleTile(
          enabled: _audioNotificationsEnabled,
          onChanged: (value) async {
            await NotificationService().setTtsEnabled(value);
            setState(() => _audioNotificationsEnabled = value);
          },
        ),
        _ActionTile(
          icon: Icons.info_outline,
          label: 'About App',
          subtitle: 'ITMS v1.0.0 • Intelligent Traffic Management',
          onTap: () {},
        ),
        _ActionTile(
          icon: Icons.help_outline,
          label: 'Help & Support',
          subtitle: 'FAQ, Contact us',
          onTap: () {},
        ),
        const SizedBox(height: 8),
        _ActionTile(
          icon: Icons.logout,
          label: 'Sign Out',
          subtitle: 'Log out of your account',
          color: AppColors.error,
          onTap: () async {
            final confirm = await showDialog<bool>(
              context: context,
              builder: (context) => AlertDialog(
                backgroundColor: AppColors.surface,
                title: const Text('Sign Out',
                    style: TextStyle(color: AppColors.textPrimary)),
                content: const Text('Are you sure you want to sign out?',
                    style: TextStyle(color: AppColors.textSecondary)),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Cancel',
                        style: TextStyle(color: AppColors.textSecondary)),
                  ),
                  TextButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: const Text('Sign Out',
                        style: TextStyle(color: AppColors.error)),
                  ),
                ],
              ),
            );
            if (confirm == true && context.mounted) {
              await context.read<AuthProvider>().logout();
              if (context.mounted) {
                Navigator.of(context)
                    .pushNamedAndRemoveUntil('/platform-router', (_) => false);
              }
            }
          },
        ),
      ],
    );
  }

  IconData _getTipIcon(String category) {
    switch (category) {
      case 'lane_discipline':
        return Icons.swap_horiz;
      case 'parking':
        return Icons.local_parking;
      case 'speed':
        return Icons.speed;
      case 'emergency':
        return Icons.emergency;
      default:
        return Icons.lightbulb;
    }
  }
}

class _StatBoxe extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;

  const _StatBoxe({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border.withOpacity(0.5)),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 22),
          const SizedBox(height: 8),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 13,
              fontWeight: FontWeight.bold,
            ),
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 10,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

class _ActionTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final String subtitle;
  final Color? color;
  final VoidCallback onTap;

  const _ActionTile({
    required this.icon,
    required this.label,
    required this.subtitle,
    this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.border.withOpacity(0.3)),
        ),
        child: Row(
          children: [
            Icon(icon, color: color ?? AppColors.textSecondary, size: 22),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: TextStyle(
                      color: color ?? AppColors.textPrimary,
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  Text(
                    subtitle,
                    style: const TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 11,
                    ),
                  ),
                ],
              ),
            ),
            Icon(Icons.chevron_right,
                color: AppColors.textSecondary.withOpacity(0.5), size: 20),
          ],
        ),
      ),
    );
  }
}

/// Toggle tile for audio notifications setting
class _AudioToggleTile extends StatelessWidget {
  final bool enabled;
  final ValueChanged<bool> onChanged;

  const _AudioToggleTile({
    required this.enabled,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          Icon(
            enabled ? Icons.volume_up : Icons.volume_off,
            color: enabled ? AppColors.primary : AppColors.textSecondary,
            size: 22,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: const [
                Text(
                  'Audio Notifications',
                  style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                Text(
                  'Speak violation alerts aloud',
                  style: TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
          Switch(
            value: enabled,
            onChanged: onChanged,
            activeColor: AppColors.primary,
          ),
        ],
      ),
    );
  }
}

/// A read-only info tile used inside the edit-profile bottom sheet.
class _ReadOnlyInfoField extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _ReadOnlyInfoField({
    required this.icon,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          Icon(icon, color: AppColors.textSecondary, size: 20),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: const TextStyle(color: AppColors.textSecondary, fontSize: 11),
                ),
                const SizedBox(height: 2),
                Text(
                  value,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: AppColors.textSecondary.withOpacity(0.1),
              borderRadius: BorderRadius.circular(6),
            ),
            child: const Text(
              'Read-only',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 10),
            ),
          ),
        ],
      ),
    );
  }
}
