# خريطة كود شاشة نظام الأدوار الجديد ← (app_label, اسم النموذج القديم في Django)
# تُستخدم لترجمة صلاحيات الشاشات إلى أكواد Django القديمة التي تفحصها القائمة الجانبية،
# حتى يظهر للمستخدم المُدار بالنظام الجديد كل الأقسام المصرَّح له بها لا الداشبورد فقط.
SCREEN_TO_MODEL = {
    'accounts.account': ('accounts', 'account'),
    'accounts.journalentry': ('accounts', 'journalentry'),
    'sales.customer': ('sales', 'customer'),
    'sales.invoice': ('sales', 'salesinvoice'),
    'purchases.supplier': ('purchases', 'supplier'),
    'purchases.invoice': ('purchases', 'purchaseinvoice'),
    'purchases.product': ('purchases', 'product'),
    'warehouses.warehouse': ('warehouses', 'warehouse'),
    'warehouses.stockmovement': ('warehouses', 'stockmovement'),
    'treasury.safe': ('treasury', 'safe'),
    'treasury.bank': ('treasury', 'bank'),
    'hr.employee': ('hr', 'employee'),
    'reports.report': ('reports', 'reporttemplate'),
    'budget.budget': ('budget', 'budget'),
    'requisitions.requisition': ('requisitions', 'requisition'),
    'purchase_orders.purchaseorder': ('purchase_orders', 'purchaseorder'),
    'rfq.rfq': ('rfq', 'rfq'),
    'goods_received.grn': ('goods_received', 'goodsreceivednote'),
    'purchase_returns.purchasereturn': ('purchase_returns', 'purchasereturn'),
    'sales_orders.salesorder': ('sales_orders', 'salesorder'),
    'sales_returns.salesreturn': ('sales_returns', 'salesreturn'),
    'tax_invoices.taxinvoice': ('tax_invoices', 'taxinvoice'),
    'credit_notes.creditnote': ('credit_notes', 'creditnote'),
    'payment_receipts.paymentreceipt': ('payment_receipts', 'paymentreceipt'),
    'cheques.cheque': ('cheques', 'cheque'),
    'stock_adjustments.adjustment': ('stock_adjustments', 'stockadjustment'),
    'assets.asset': ('assets', 'asset'),
    'contractors.contractor': ('contractors', 'contractor'),
    'concrete_production.production': ('concrete_production', 'concretemixdesign'),
    'currency.currency': ('currency', 'currency'),
    'documents.document': ('documents', 'document'),
    'bank_reconciliation.statement': ('bank_reconciliation', 'bankstatementitem'),
    'system.users': ('auth', 'user'),
    'ai_analysis.errorlog': ('ai_analysis', 'errorlog'),
}

# مستوى الشاشة ← فعل صلاحية Django
_LEVEL_TO_ACTION = {'view': 'view', 'add': 'add', 'edit': 'change', 'delete': 'delete'}


def _legacy_perms_from_screens(screen_perms):
    """يترجم {screen_code: {level: bool}} إلى مجموعة أكواد Django مثل sales.view_salesinvoice."""
    out = set()
    for code, levels in (screen_perms or {}).items():
        mapped = SCREEN_TO_MODEL.get(code)
        if not mapped:
            continue
        app_label, model = mapped
        for level, action in _LEVEL_TO_ACTION.items():
            if levels.get(level):
                out.add(f'{app_label}.{action}_{model}')
    return out


def user_permissions_context(request):
    """Context processor that adds user permissions for template conditional display."""
    if not request.user.is_authenticated:
        return {'user_perms': set(), 'is_superuser': False}
    
    cached = getattr(request, '_cached_perms', None)
    if cached is not None:
        return cached
    
    if request.user.is_superuser:
        perms = {'all'}
    else:
        perms = set()

    screen_perms = {}
    can_view_prices = True
    try:
        from access_control.resolver import resolve
        resolved = resolve(request.user)
        screen_perms = resolved.screens
        can_view_prices = resolved.can_view_prices
        # المصدر الوحيد للصلاحيات هو نظام الأدوار الجديد (access_control).
        # نشتق أكواد القائمة من الشاشات فقط، بلا أي اعتماد على صلاحيات Django القديمة
        # (لم نعد نقرأ get_all_permissions) حتى لا يعود نظامان متعارضان يسبّبان اختفاء القوائم.
        if not request.user.is_superuser:
            perms = _legacy_perms_from_screens(screen_perms)
    except Exception:
        pass

    result = {
        'user_perms': perms,
        'is_superuser': request.user.is_superuser,
        'screen_perms': screen_perms,
        'can_view_prices': can_view_prices,
    }
    request._cached_perms = result
    return result
