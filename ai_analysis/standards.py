EGYPTIAN_ACCOUNTING_STANDARDS = {
    'name': 'المعايير المحاسبية المصرية',
    'code': 'EGAS',
    'key_principles': [
        {
            'name': 'مبدأ الاستمرارية',
            'description': 'يفترض أن المشروع sẽ يستمر في نشاطه لفترة غير محددة',
            'reference': 'المعيار المحاسبي المصري رقم 1',
        },
        {
            'name': 'مبدأ الحيطة المحاسبية',
            'description': 'عدم الاعتراف بأرباح محتملة لكن يُعترف بخسائر محتملة',
            'reference': 'المعيار المحاسبي المصري رقم 2',
        },
        {
            'name': 'مبدأ المطابقة',
            'description': 'مطابقة الإيرادات مع المصروفات في نفس الفترة المحاسبية',
            'reference': 'المعيار المحاسبي المصري رقم 3',
        },
        {
            'name': 'مبدأ الكشف الكامل',
            'description': 'الكشف عن جميع المعلومات المالية ذات الأثر المحاسبي',
            'reference': 'المعيار المحاسبي المصري رقم 4',
        },
        {
            'name': 'مبدأ ثبات السياسات',
            'description': 'استمرار نفس السياسات المحاسبية من فترة لأخرى',
            'reference': 'المعيار المحاسبي المصري رقم 5',
        },
        {
            'name': 'مبدأ التكلفة التاريخية',
            'description': 'تسجيل الأصول بالتكلفة التاريخية',
            'reference': 'المعيار المحاسبي المصري رقم 6',
        },
    ],
    'vat_rules': {
        'rate': 14,
        'law': 'القانون رقم 67 لسنة 2016',
        'key_points': [
            'ضريبة القيمة المضافة على جميع السلع والخدمات',
            'نسبة الضريبة 14%',
            'يُسجل كالتزام ضريبي عند الفوترة',
            'يُخصم كدخل ضريبي عند الدفع',
        ]
    },
    'withholding_tax_rules': {
        'rates': {
            '1': 'شركات',
            '3': 'جهات حكومية',
            '5': 'مقاولين',
        },
        'law': 'القانون رقم 91 لسنة 2005 وتعديلاته',
    }
}

IFRS_STANDARDS = {
    'name': 'معايير الإبلاغ المالي الدولية',
    'code': 'IFRS',
    'key_standards': [
        {
            'code': 'IAS 1',
            'name': 'عرض البيانات المالية',
            'key_requirements': [
                'عرض البيانات المالية بوضوح',
                'الإفصاح عن جميع السياسات المحاسبية',
                'تقديم مقارنة مع الفترة السابقة',
            ]
        },
        {
            'code': 'IAS 8',
            'name': 'السياسات المحاسبية والتغييرات في المقدراث المحاسبية',
            'key_requirements': [
                'استمرار السياسات المحاسبية',
                'التغيير فقط إذا كان يحسن المعلومات المالية',
                'الإفصاح عن أي تغيير',
            ]
        },
        {
            'code': 'IAS 10',
            'name': 'الأحداث بعد تاريخ الميزانية العمومية',
            'key_requirements': [
                'تعديل البيانات المالية للأحداث المعدلة',
                'الإفصاح عن الأحداث غير المعدلة',
            ]
        },
        {
            'code': 'IFRS 15',
            'name': 'إيرادات العقود مع العملاء',
            'key_requirements': [
                'تحديد العقود',
                'تحديد الالتزامات',
                'تحديد سعر المعاملة',
                'توزيع سعر المعاملة',
                'الاعتراف بالإيراد',
            ]
        },
        {
            'code': 'IAS 36',
            'name': 'الإهلاك',
            'key_requirements': [
                'تحقق من انخفاض القيمة القابلة للاسترداد',
                'تسجيل خسائر انخفاض القيمة',
                'عدم عكس الخسائر في_periodات لاحقة',
            ]
        },
    ]
}


def validate_solution_against_standards(proposed_solution, error_type):
    """التحقق من حل مقترح ضد المعايير المحاسبية"""
    violations = []
    warnings = []

    # التحقق من مبدأ الحيطة المحاسبية
    if 'ربح' in proposed_solution.lower() and 'محتشم' not in proposed_solution.lower():
        violations.append({
            'standard': 'مبدأ الحيطة المحاسبية',
            'description': 'يجب أن يكون التقدير محتشماً عند الاعتراف بالأرباح',
        })

    # التحقق من مبدأ المطابقة
    if error_type in ['REVENUE_RECOGNITION', 'EXPENSE_MATCHING']:
        if 'فترة' not in proposed_solution.lower():
            warnings.append({
                'standard': 'مبدأ المطابقة',
                'description': 'تأكد من مطابقة الإيرادات والمصروفات لنفس الفترة المحاسبية',
            })

    # التحقق من الكشف الكامل
    if 'إفصاح' not in proposed_solution.lower() and 'كشف' not in proposed_solution.lower():
        warnings.append({
            'standard': 'مبدأ الكشف الكامل',
            'description': 'تأكد من الإفصاح الكامل عن التعديل في البيانات المالية',
        })

    # التحقق من قواعد VAT
    if error_type in ['VAT_ERROR', 'TAX_ERROR']:
        if '14%' not in proposed_solution:
            warnings.append({
                'standard': 'ضريبة القيمة المضافة',
                'description': 'تأكد من تطبيق نسبة 14% الصحيحة',
            })

    return {
        'is_compliant': len(violations) == 0,
        'violations': violations,
        'warnings': warnings,
    }


def get_applicable_standards(error_type):
    """تحديد المعايير المطبقة لنوع الخطأ"""
    standards = []

    if error_type in ['UNBALANCED_ENTRY', 'POSTING_ERROR']:
        standards.append(EGYPTIAN_ACCOUNTING_STANDARDS['key_principles'][2])  # Matching
        standards.append(IFRS_STANDARDS['key_standards'][0])  # IAS 1

    if error_type in ['REVENUE_RECOGNITION']:
        standards.append(IFRS_STANDARDS['key_standards'][3])  # IFRS 15

    if error_type in ['ASSET_IMPAIRMENT']:
        standards.append(IFRS_STANDARDS['key_standards'][4])  # IAS 36

    if error_type in ['POLICY_CHANGE']:
        standards.append(IFRS_STANDARDS['key_standards'][1])  # IAS 8

    if error_type in ['YEAR_END_EVENT']:
        standards.append(IFRS_STANDARDS['key_standards'][2])  # IAS 10

    return standards
