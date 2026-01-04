import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../providers/auth_provider.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with TickerProviderStateMixin {
  late AnimationController _logoController;
  late AnimationController _textController;
  late Animation<double> _logoScaleAnimation;
  late Animation<double> _logoFadeAnimation;
  late Animation<double> _textFadeAnimation;
  late Animation<Offset> _textSlideAnimation;

  @override
  void initState() {
    super.initState();
    
    _logoController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    );
    
    _textController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    );
    
    _logoScaleAnimation = Tween<double>(begin: 0.5, end: 1.0).animate(
      CurvedAnimation(parent: _logoController, curve: Curves.elasticOut),
    );
    
    _logoFadeAnimation = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(parent: _logoController, curve: Curves.easeOut),
    );
    
    _textFadeAnimation = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(parent: _textController, curve: Curves.easeOut),
    );
    
    _textSlideAnimation = Tween<Offset>(
      begin: const Offset(0, 0.3),
      end: Offset.zero,
    ).animate(
      CurvedAnimation(parent: _textController, curve: Curves.easeOutCubic),
    );
    
    _startAnimation();
  }

  Future<void> _startAnimation() async {
    await Future.delayed(const Duration(milliseconds: 200));
    _logoController.forward();
    
    await Future.delayed(const Duration(milliseconds: 500));
    _textController.forward();
    
    await Future.delayed(const Duration(milliseconds: 1500));
    _initializeApp();
  }

  Future<void> _initializeApp() async {
    final authProvider = context.read<AuthProvider>();
    await authProvider.initialize();
    
    if (!mounted) return;
    
    // Navigate based on auth state
    if (authProvider.isAuthenticated) {
      final userType = authProvider.userType;
      if (userType == 'admin') {
        Navigator.of(context).pushReplacementNamed('/admin/dashboard');
      } else {
        Navigator.of(context).pushReplacementNamed('/driver/home');
      }
    } else {
      // Check if running on web or mobile to decide which login to show
      Navigator.of(context).pushReplacementNamed('/platform-router');
    }
  }

  @override
  void dispose() {
    _logoController.dispose();
    _textController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: RadialGradient(
            center: Alignment.center,
            radius: 1.5,
            colors: [
              Color(0xFF1A1A2E),
              AppColors.background,
            ],
          ),
        ),
        child: Stack(
          children: [
            // Animated background particles
            _buildParticles(),
            
            // Main content
            Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Logo
                  FadeTransition(
                    opacity: _logoFadeAnimation,
                    child: ScaleTransition(
                      scale: _logoScaleAnimation,
                      child: _buildLogo(),
                    ),
                  ),
                  
                  const SizedBox(height: 40),
                  
                  // Text
                  FadeTransition(
                    opacity: _textFadeAnimation,
                    child: SlideTransition(
                      position: _textSlideAnimation,
                      child: _buildText(),
                    ),
                  ),
                  
                  const SizedBox(height: 60),
                  
                  // Loading indicator
                  FadeTransition(
                    opacity: _textFadeAnimation,
                    child: _buildLoadingIndicator(),
                  ),
                ],
              ),
            ),
            
            // Version info
            Positioned(
              bottom: 32,
              left: 0,
              right: 0,
              child: FadeTransition(
                opacity: _textFadeAnimation,
                child: Text(
                  'Version 1.0.0',
                  textAlign: TextAlign.center,
                  style: AppTypography.caption.copyWith(
                    color: AppColors.textMuted,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildParticles() {
    return CustomPaint(
      painter: _ParticlePainter(),
      size: Size.infinite,
    );
  }

  Widget _buildLogo() {
    return Container(
      width: 120,
      height: 240,
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.border, width: 3),
        boxShadow: [
          BoxShadow(
            color: AppColors.primary.withOpacity(0.3),
            blurRadius: 40,
            spreadRadius: 10,
          ),
        ],
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _buildLight(AppColors.trafficRed, 0),
          _buildLight(AppColors.trafficYellow, 1),
          _buildLight(AppColors.trafficGreen, 2),
        ],
      ),
    );
  }

  Widget _buildLight(Color color, int index) {
    return AnimatedBuilder(
      animation: _logoController,
      builder: (context, child) {
        final delay = index * 0.2;
        final progress = ((_logoController.value - delay) / (1 - delay)).clamp(0.0, 1.0);
        
        return Container(
          width: 60,
          height: 60,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: Color.lerp(color.withOpacity(0.2), color, progress),
            boxShadow: progress > 0.5
                ? [
                    BoxShadow(
                      color: color.withOpacity(0.6 * progress),
                      blurRadius: 20 * progress,
                      spreadRadius: 5 * progress,
                    ),
                  ]
                : null,
          ),
        );
      },
    );
  }

  Widget _buildText() {
    return Column(
      children: [
        ShaderMask(
          shaderCallback: (bounds) => const LinearGradient(
            colors: [AppColors.primary, AppColors.accent],
          ).createShader(bounds),
          child: Text(
            'TRAFFIC CONTROL',
            style: AppTypography.h1.copyWith(
              fontSize: 32,
              fontWeight: FontWeight.w900,
              color: Colors.white,
              letterSpacing: 4,
            ),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'INTELLIGENT MANAGEMENT SYSTEM',
          style: AppTypography.bodyMedium.copyWith(
            color: AppColors.textSecondary,
            letterSpacing: 3,
          ),
        ),
      ],
    );
  }

  Widget _buildLoadingIndicator() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: List.generate(3, (index) {
        return AnimatedBuilder(
          animation: _logoController,
          builder: (context, _) {
            final delay = index * 0.15;
            final wave = ((_logoController.value * 3 + delay) % 1.0);
            final scale = 0.5 + 0.5 * (1 - (2 * wave - 1).abs());
            
            return Container(
              width: 8,
              height: 8,
              margin: const EdgeInsets.symmetric(horizontal: 4),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: AppColors.primary.withOpacity(scale),
              ),
            );
          },
        );
      }),
    );
  }
}

class _ParticlePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppColors.primary.withOpacity(0.05)
      ..style = PaintingStyle.fill;

    // Draw some subtle dots
    for (var i = 0; i < 50; i++) {
      final x = (i * 37) % size.width;
      final y = (i * 59) % size.height;
      canvas.drawCircle(Offset(x, y), 2, paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
