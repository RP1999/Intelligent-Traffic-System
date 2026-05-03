import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/common/common.dart';

class AdminLoginScreen extends StatefulWidget {
  const AdminLoginScreen({super.key});

  @override
  State<AdminLoginScreen> createState() => _AdminLoginScreenState();
}

class _AdminLoginScreenState extends State<AdminLoginScreen>
    with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  
  late AnimationController _bgController;
  late AnimationController _formController;
  late Animation<double> _formSlideAnimation;
  late Animation<double> _formFadeAnimation;

  @override
  void initState() {
    super.initState();
    _bgController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 10),
    )..repeat();
    
    _formController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    );
    
    _formSlideAnimation = Tween<double>(begin: 50, end: 0).animate(
      CurvedAnimation(parent: _formController, curve: Curves.easeOutCubic),
    );
    
    _formFadeAnimation = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(parent: _formController, curve: Curves.easeOut),
    );
    
    _formController.forward();
  }

  @override
  void dispose() {
    _bgController.dispose();
    _formController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _handleLogin() async {
    if (!_formKey.currentState!.validate()) return;
    
    final authProvider = context.read<AuthProvider>();
    final success = await authProvider.adminLogin(
      _usernameController.text.trim(),
      _passwordController.text,
    );
    
    if (success && mounted) {
      Navigator.of(context).pushReplacementNamed('/admin/dashboard');
    }
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    final isWideScreen = size.width > 1000;
    
    return Scaffold(
      body: Stack(
        children: [
          // Animated background
          _buildAnimatedBackground(),
          
          // Grid overlay
          _buildGridOverlay(),
          
          // Main content
          Row(
            children: [
              // Left side - branding (only on wide screens)
              if (isWideScreen)
                Expanded(
                  flex: 5,
                  child: _buildBrandingSection(),
                ),
              
              // Right side - login form
              Expanded(
                flex: isWideScreen ? 4 : 1,
                child: Center(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(32),
                    child: AnimatedBuilder(
                      animation: _formController,
                      builder: (context, child) {
                        return Transform.translate(
                          offset: Offset(0, _formSlideAnimation.value),
                          child: Opacity(
                            opacity: _formFadeAnimation.value,
                            child: child,
                          ),
                        );
                      },
                      child: _buildLoginForm(),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildAnimatedBackground() {
    return AnimatedBuilder(
      animation: _bgController,
      builder: (context, child) {
        return CustomPaint(
          painter: _BackgroundPainter(_bgController.value),
          size: Size.infinite,
        );
      },
    );
  }

  Widget _buildGridOverlay() {
    return Opacity(
      opacity: 0.03,
      child: CustomPaint(
        painter: _GridPainter(),
        size: Size.infinite,
      ),
    );
  }

  Widget _buildBrandingSection() {
    return Container(
      padding: const EdgeInsets.all(48),
      child: SingleChildScrollView(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Traffic light logo
            _buildAnimatedTrafficLight(),
            
            const SizedBox(height: 48),
            
            // Title
            ShaderMask(
              shaderCallback: (bounds) => const LinearGradient(
                colors: [AppColors.primary, AppColors.accent],
              ).createShader(bounds),
              child: Text(
                'TRAFFIC CONTROL',
                style: AppTypography.h1.copyWith(
                  fontSize: 48,
                  fontWeight: FontWeight.w900,
                  color: Colors.white,
                  letterSpacing: 4,
                ),
              ),
            ),
            
            const SizedBox(height: 8),
            
            Text(
              'COMMAND CENTER',
              style: AppTypography.h2.copyWith(
                color: AppColors.textSecondary,
                letterSpacing: 8,
              ),
            ),
            
            const SizedBox(height: 24),
            
            Container(
              width: 100,
              height: 4,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [AppColors.primary, AppColors.accent],
                ),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            
            const SizedBox(height: 24),
            
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: Text(
                'Real-time traffic monitoring, violation detection, and intelligent signal control powered by AI.',
                style: AppTypography.bodyLarge.copyWith(
                  color: AppColors.textSecondary,
                  height: 1.6,
                ),
              ),
            ),
            
            const SizedBox(height: 48),
            
            // Stats row - use Wrap for responsiveness
            Wrap(
              spacing: 40,
              runSpacing: 20,
              children: [
                _buildStatItem('24/7', 'Monitoring'),
                _buildStatItem('99.9%', 'Uptime'),
                _buildStatItem('AI', 'Powered'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAnimatedTrafficLight() {
    return AnimatedBuilder(
      animation: _bgController,
      builder: (context, _) {
        final value = (_bgController.value * 3) % 1;
        return Container(
          width: 60,
          height: 160,
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.border, width: 2),
            boxShadow: [
              BoxShadow(
                color: _getTrafficColor(value).withOpacity(0.3),
                blurRadius: 30,
                spreadRadius: 10,
              ),
            ],
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _buildTrafficLightDot(
                AppColors.trafficRed,
                value < 0.33,
              ),
              _buildTrafficLightDot(
                AppColors.trafficYellow,
                value >= 0.33 && value < 0.66,
              ),
              _buildTrafficLightDot(
                AppColors.trafficGreen,
                value >= 0.66,
              ),
            ],
          ),
        );
      },
    );
  }

  Color _getTrafficColor(double value) {
    if (value < 0.33) return AppColors.trafficRed;
    if (value < 0.66) return AppColors.trafficYellow;
    return AppColors.trafficGreen;
  }

  Widget _buildTrafficLightDot(Color color, bool isActive) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      width: 36,
      height: 36,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: isActive ? color : color.withOpacity(0.15),
        boxShadow: isActive
            ? [
                BoxShadow(
                  color: color.withOpacity(0.8),
                  blurRadius: 16,
                  spreadRadius: 4,
                ),
              ]
            : null,
      ),
    );
  }

  Widget _buildStatItem(String value, String label) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          value,
          style: AppTypography.h3.copyWith(
            color: AppColors.primary,
            fontWeight: FontWeight.w700,
          ),
        ),
        Text(
          label,
          style: AppTypography.bodySmall.copyWith(
            color: AppColors.textSecondary,
          ),
        ),
      ],
    );
  }

  Widget _buildLoginForm() {
    return Consumer<AuthProvider>(
      builder: (context, authProvider, _) {
        return Container(
          width: 400,
          padding: const EdgeInsets.all(40),
          decoration: BoxDecoration(
            color: AppColors.surface.withOpacity(0.9),
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: AppColors.border),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.3),
                blurRadius: 40,
                spreadRadius: 0,
              ),
            ],
          ),
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Lock icon
                Container(
                  width: 64,
                  height: 64,
                  margin: const EdgeInsets.only(bottom: 24),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: LinearGradient(
                      colors: [
                        AppColors.primary.withOpacity(0.2),
                        AppColors.accent.withOpacity(0.1),
                      ],
                    ),
                    border: Border.all(
                      color: AppColors.primary.withOpacity(0.3),
                    ),
                  ),
                  child: const Icon(
                    Icons.admin_panel_settings,
                    size: 32,
                    color: AppColors.primary,
                  ),
                ),
                
                Text(
                  'Admin Login',
                  style: AppTypography.h2,
                  textAlign: TextAlign.center,
                ),
                
                const SizedBox(height: 8),
                
                Text(
                  'Sign in to access the control center',
                  style: AppTypography.bodyMedium.copyWith(
                    color: AppColors.textSecondary,
                  ),
                  textAlign: TextAlign.center,
                ),
                
                const SizedBox(height: 32),
                
                // Error message
                if (authProvider.error != null) ...[
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.error.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: AppColors.error.withOpacity(0.3),
                      ),
                    ),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.error_outline,
                          color: AppColors.error,
                          size: 20,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            authProvider.error!,
                            style: AppTypography.bodySmall.copyWith(
                              color: AppColors.error,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                ],
                
                // Username field
                AppTextField(
                  label: 'Username',
                  hint: 'admin',
                  controller: _usernameController,
                  prefixIcon: Icons.person_outline,
                  keyboardType: TextInputType.text,
                  textInputAction: TextInputAction.next,
                  validator: (value) {
                    if (value == null || value.isEmpty) {
                      return 'Please enter your username';
                    }
                    return null;
                  },
                ),
                
                const SizedBox(height: 20),
                
                // Password field
                AppTextField(
                  label: 'Password',
                  hint: '••••••••',
                  controller: _passwordController,
                  prefixIcon: Icons.lock_outline,
                  obscureText: true,
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => _handleLogin(),
                  validator: (value) {
                    if (value == null || value.isEmpty) {
                      return 'Please enter your password';
                    }
                    if (value.length < 6) {
                      return 'Password must be at least 6 characters';
                    }
                    return null;
                  },
                ),
                
                const SizedBox(height: 32),
                
                // Login button
                AppButton(
                  text: 'Sign In',
                  onPressed: _handleLogin,
                  isLoading: authProvider.isLoading,
                  icon: Icons.login,
                  size: AppButtonSize.large,
                ),
                
                const SizedBox(height: 24),
                
                // Footer
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(
                      Icons.shield_outlined,
                      size: 14,
                      color: AppColors.textMuted,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      'Secured by 256-bit encryption',
                      style: AppTypography.caption.copyWith(
                        color: AppColors.textMuted,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

// Background painter with animated gradient orbs
class _BackgroundPainter extends CustomPainter {
  final double animationValue;

  _BackgroundPainter(this.animationValue);

  @override
  void paint(Canvas canvas, Size size) {
    // Base gradient
    final baseGradient = LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [
        AppColors.background,
        const Color(0xFF0D0D0D),
        const Color(0xFF1A1A1A),
      ],
    );
    
    final rect = Offset.zero & size;
    canvas.drawRect(rect, Paint()..shader = baseGradient.createShader(rect));
    
    // Animated orbs
    final orb1Center = Offset(
      size.width * (0.2 + 0.1 * _sin(animationValue)),
      size.height * (0.3 + 0.1 * _cos(animationValue)),
    );
    
    final orb2Center = Offset(
      size.width * (0.8 + 0.1 * _cos(animationValue)),
      size.height * (0.7 + 0.1 * _sin(animationValue)),
    );
    
    // Primary orb
    final orb1Paint = Paint()
      ..shader = RadialGradient(
        colors: [
          AppColors.primary.withOpacity(0.15),
          AppColors.primary.withOpacity(0),
        ],
      ).createShader(Rect.fromCircle(center: orb1Center, radius: size.width * 0.4));
    canvas.drawCircle(orb1Center, size.width * 0.4, orb1Paint);
    
    // Accent orb
    final orb2Paint = Paint()
      ..shader = RadialGradient(
        colors: [
          AppColors.accent.withOpacity(0.1),
          AppColors.accent.withOpacity(0),
        ],
      ).createShader(Rect.fromCircle(center: orb2Center, radius: size.width * 0.3));
    canvas.drawCircle(orb2Center, size.width * 0.3, orb2Paint);
  }

  double _sin(double value) => (value * 2 * 3.14159).sin();
  double _cos(double value) => (value * 2 * 3.14159).cos();

  @override
  bool shouldRepaint(covariant _BackgroundPainter oldDelegate) {
    return oldDelegate.animationValue != animationValue;
  }
}

// Grid overlay painter
class _GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppColors.textMuted
      ..strokeWidth = 0.5;

    const gridSize = 50.0;
    
    for (double x = 0; x < size.width; x += gridSize) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    
    for (double y = 0; y < size.height; y += gridSize) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

// Extension to add sin/cos to double
extension on double {
  double sin() => _sin(this);
  double cos() => _cos(this);
}

double _sin(double value) {
  return (value * 3.14159 * 2).clamp(-1.0, 1.0) > 0 
      ? (1.0 - ((value * 2 - 0.5).abs() * 2).clamp(0.0, 1.0))
      : -(1.0 - ((value * 2 - 0.5).abs() * 2).clamp(0.0, 1.0));
}

double _cos(double value) {
  return _sin(value + 0.25);
}
