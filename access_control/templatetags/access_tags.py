from django import template

register = template.Library()

_MASK = '••••'


@register.filter(name='price_mask')
def price_mask(value, can_view):
    """يُخفي القيمة السعرية عند غياب صلاحية مشاهدة الأسعار.
    Usage: {{ product.price|price_mask:can_view_prices }}"""
    if can_view:
        return value
    return _MASK


@register.simple_tag(takes_context=True)
def can_screen(context, screen_code, level='view'):
    """يتحقق من صلاحية شاشة داخل القالب مباشرةً.
    Usage: {% can_screen 'warehouses.stockmovement' 'add' as may_add %}"""
    request = context.get('request')
    if not request or not getattr(request, 'user', None):
        return False
    user = request.user
    if getattr(user, 'is_superuser', False):
        return True
    screen_perms = context.get('screen_perms') or {}
    return bool(screen_perms.get(screen_code, {}).get(level, False))
