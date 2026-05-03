import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';

/// Button variants
enum AppButtonVariant { primary, secondary, outlined, danger, ghost }

/// Button sizes
enum AppButtonSize { small, medium, large }

/// Custom styled button widget
class AppButton extends StatefulWidget {
  final String text;
  final VoidCallback? onPressed;
  final AppButtonVariant variant;
  final AppButtonSize size;
  final IconData? icon;
  final bool isLoading;
  final bool isFullWidth;
  final bool hasGlow;

  const AppButton({
    super.key,
    required this.text,
    this.onPressed,
    this.variant = AppButtonVariant.primary,
    this.size = AppButtonSize.medium,
    this.icon,
    this.isLoading = false,
    this.isFullWidth = false,
    this.hasGlow = false,
  });

  @override
  State<AppButton> createState() => _AppButtonState();
}

class _AppButtonState extends State<AppButton> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          boxShadow: widget.hasGlow && _isHovered
              ? _getGlowShadow()
              : null,
        ),
        child: SizedBox(
          width: widget.isFullWidth ? double.infinity : null,
          height: _getHeight(),
          child: _buildButton(),
        ),
      ),
    );
  }

  Widget _buildButton() {
    final buttonStyle = _getButtonStyle();
    final child = _buildChild();

    switch (widget.variant) {
      case AppButtonVariant.primary:
      case AppButtonVariant.danger:
        return ElevatedButton(
          onPressed: widget.isLoading ? null : widget.onPressed,
          style: buttonStyle,
          child: child,
        );
      case AppButtonVariant.secondary:
      case AppButtonVariant.outlined:
        return OutlinedButton(
          onPressed: widget.isLoading ? null : widget.onPressed,
          style: buttonStyle,
          child: child,
        );
      case AppButtonVariant.ghost:
        return TextButton(
          onPressed: widget.isLoading ? null : widget.onPressed,
          style: buttonStyle,
          child: child,
        );
    }
  }

  Widget _buildChild() {
    if (widget.isLoading) {
      return SizedBox(
        width: 20,
        height: 20,
        child: CircularProgressIndicator(
          strokeWidth: 2,
          valueColor: AlwaysStoppedAnimation<Color>(_getLoadingColor()),
        ),
      );
    }

    if (widget.icon != null) {
      return Row(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(widget.icon, size: _getIconSize()),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              widget.text,
              style: _getTextStyle(),
              overflow: TextOverflow.ellipsis,
              maxLines: 1,
            ),
          ),
        ],
      );
    }

    return Text(
      widget.text, 
      style: _getTextStyle(),
      overflow: TextOverflow.ellipsis,
      maxLines: 1,
    );
  }

  double _getHeight() {
    switch (widget.size) {
      case AppButtonSize.small:
        return 36;
      case AppButtonSize.medium:
        return 48;
      case AppButtonSize.large:
        return 56;
    }
  }

  double _getIconSize() {
    switch (widget.size) {
      case AppButtonSize.small:
        return 16;
      case AppButtonSize.medium:
        return 20;
      case AppButtonSize.large:
        return 24;
    }
  }

  TextStyle _getTextStyle() {
    switch (widget.size) {
      case AppButtonSize.small:
        return AppTypography.buttonSmall;
      case AppButtonSize.medium:
        return AppTypography.buttonMedium;
      case AppButtonSize.large:
        return AppTypography.buttonLarge;
    }
  }

  Color _getLoadingColor() {
    switch (widget.variant) {
      case AppButtonVariant.primary:
        return AppColors.background;
      case AppButtonVariant.danger:
        return AppColors.textPrimary;
      case AppButtonVariant.secondary:
      case AppButtonVariant.outlined:
      case AppButtonVariant.ghost:
        return AppColors.primary;
    }
  }

  List<BoxShadow>? _getGlowShadow() {
    switch (widget.variant) {
      case AppButtonVariant.primary:
        return AppColors.primaryGlow;
      case AppButtonVariant.danger:
        return AppColors.errorGlow;
      default:
        return null;
    }
  }

  ButtonStyle _getButtonStyle() {
    final padding = _getPadding();

    switch (widget.variant) {
      case AppButtonVariant.primary:
        return ElevatedButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: AppColors.background,
          padding: padding,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        );
      case AppButtonVariant.danger:
        return ElevatedButton.styleFrom(
          backgroundColor: AppColors.error,
          foregroundColor: AppColors.textPrimary,
          padding: padding,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        );
      case AppButtonVariant.secondary:
        return OutlinedButton.styleFrom(
          foregroundColor: AppColors.primary,
          side: const BorderSide(color: AppColors.primary, width: 2),
          padding: padding,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        );
      case AppButtonVariant.outlined:
        return OutlinedButton.styleFrom(
          foregroundColor: AppColors.textSecondary,
          side: const BorderSide(color: AppColors.border, width: 1),
          padding: padding,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        );
      case AppButtonVariant.ghost:
        return TextButton.styleFrom(
          foregroundColor: AppColors.primary,
          padding: padding,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        );
    }
  }

  EdgeInsetsGeometry _getPadding() {
    switch (widget.size) {
      case AppButtonSize.small:
        return const EdgeInsets.symmetric(horizontal: 16, vertical: 8);
      case AppButtonSize.medium:
        return const EdgeInsets.symmetric(horizontal: 24, vertical: 12);
      case AppButtonSize.large:
        return const EdgeInsets.symmetric(horizontal: 32, vertical: 16);
    }
  }
}

/// Icon button with hover effect
class AppIconButton extends StatefulWidget {
  final IconData icon;
  final VoidCallback? onPressed;
  final Color? color;
  final Color? hoverColor;
  final double size;
  final String? tooltip;
  final bool hasBadge;
  final int badgeCount;

  const AppIconButton({
    super.key,
    required this.icon,
    this.onPressed,
    this.color,
    this.hoverColor,
    this.size = 24,
    this.tooltip,
    this.hasBadge = false,
    this.badgeCount = 0,
  });

  @override
  State<AppIconButton> createState() => _AppIconButtonState();
}

class _AppIconButtonState extends State<AppIconButton> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    Widget button = MouseRegion(
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: IconButton(
        onPressed: widget.onPressed,
        icon: Icon(
          widget.icon,
          size: widget.size,
          color: _isHovered
              ? (widget.hoverColor ?? AppColors.primary)
              : (widget.color ?? AppColors.textSecondary),
        ),
      ),
    );

    if (widget.hasBadge && widget.badgeCount > 0) {
      button = Badge(
        label: Text(
          widget.badgeCount > 99 ? '99+' : widget.badgeCount.toString(),
          style: const TextStyle(fontSize: 10),
        ),
        backgroundColor: AppColors.error,
        child: button,
      );
    }

    if (widget.tooltip != null) {
      button = Tooltip(
        message: widget.tooltip!,
        child: button,
      );
    }

    return button;
  }
}
