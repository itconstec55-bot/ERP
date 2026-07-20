from django.core.management.base import BaseCommand
from accounts.models import AccountType, Account


class Command(BaseCommand):
    help = 'إعداد دليل الحسابات الأساسي وفقاً للمعايير المصرية'

    def handle(self, *args, **kwargs):
        self.stdout.write('جاري إعداد دليل الحسابات...')

        account_types = [
            ('AT01', 'أصول متداولة', 'asset'),
            ('AT02', 'أصول غير متداولة', 'asset'),
            ('AT03', 'خصوم متداولة', 'liability'),
            ('AT04', 'خصوم غير متداولة', 'liability'),
            ('AT05', 'حقوق الملكية', 'equity'),
            ('AT06', 'إيرادات', 'revenue'),
            ('AT07', 'تكلفة البضاعة المباعة', 'expense'),
            ('AT08', 'مصروفات تشغيلية', 'expense'),
            ('AT09', 'مصروفات أخرى', 'expense'),
            ('AT10', 'إيرادات أخرى', 'revenue'),
        ]

        types = {}
        for code, name, acc_type in account_types:
            obj, created = AccountType.objects.get_or_create(
                code=code,
                defaults={'name': name, 'account_type': acc_type}
            )
            types[code] = obj
            if created:
                self.stdout.write(f'  تم إنشاء نوع الحساب: {name}')

        accounts_data = [
            # الأصول المتداولة
            ('1100', 'العملاء / حسابات المدينة', 'AT01', None),
            ('1110', 'أرصدة مدينة - عملاء', 'AT01', '1100'),
            ('1150', 'أوراق تحصيل', 'AT01', None),
            ('1200', 'المخزون', 'AT01', None),
            ('1210', 'مخزون البضاعة', 'AT01', '1200'),
            ('1250', 'منتجات تحت التصنيع', 'AT01', '1200'),
            ('1300', 'المشتريات', 'AT01', None),
            ('1350', 'ضريبة القيمة المضافة المحصلة (Input VAT)', 'AT01', None, True),
            ('1400', 'مجمع الإهلاك', 'AT01', None),
            ('1500', 'نقد بالصندوق', 'AT01', None, False, True),
            ('1600', 'حسابات بنكية', 'AT01', None, True),
            ('1610', 'البنك الأهلي المصري', 'AT01', '1600', True),
            ('1620', 'بنك CIB', 'AT01', '1600', True),
            ('1700', 'أوداع وضمانات', 'AT01', None),
            ('1800', 'أرباح معلقة', 'AT01', None),

            # الأصول غير المتداولة
            ('2100', 'أصول ثابتة', 'AT02', None),
            ('2110', 'أراضي', 'AT02', '2100'),
            ('2120', 'مباني', 'AT02', '2100'),
            ('2130', 'آلات ومعدات', 'AT02', '2100'),
            ('2140', 'أدوات مكتبية', 'AT02', '2100'),
            ('2150', 'سيارات', 'AT02', '2100'),
                        ('2200', 'أصول غير مادية', 'AT02', None),
            ('2300', 'مواقع إلكترونية', 'AT02', None),

            # الخصوم المتداولة
            ('3100', 'الموردين / حسابات دائنة', 'AT03', None),
            ('3110', 'أرصدة دائنة - موردين', 'AT03', '3100'),
            ('3200', 'ضريبة القيمة المضافة المستحقة (Output VAT)', 'AT03', None, True),
            ('3300', 'ضريبة الخصم والتحصيل المستحقة', 'AT03', None),
            ('3400', 'مصروفات مستحقة', 'AT03', None),
            ('3500', 'أقساط معلقة', 'AT03', None),
            ('3600', 'رواتب مستحقة', 'AT03', None),
            ('3610', 'تأمين اجتماعي مستحق', 'AT03', None),
            ('3620', 'ضريبة دخل مستحقة', 'AT03', None),
            ('3700', 'أرباح مستحقة', 'AT03', None),

            # الخصوم غير المتداولة
            ('4100', 'قروض طويلة الأجل', 'AT04', None),
            ('4200', 'أخرى', 'AT04', None),

            # حقوق الملكية
            ('5100', 'رأس المال', 'AT05', None),
            ('5200', 'احتياطيات', 'AT05', None),
            ('5300', 'أرباح محتجزة', 'AT05', None),
            ('5400', 'صافي أرباح/خسائر السنة', 'AT05', None),

            # الإيرادات
            ('6100', 'إيرادات المبيعات', 'AT06', None),
            ('6200', 'إيرادات خدمات', 'AT06', None),
            ('6300', 'خصم مكتسب', 'AT06', None),
            ('6400', 'مرتجعات مبيعات', 'AT06', None),

            # تكلفة البضاعة المباعة
            ('7100', 'تكلفة البضاعة المباعة', 'AT07', None),
            ('7200', 'مرتجعات مشتريات', 'AT07', None),

            # المصروفات التشغيلية
            ('8100', 'إيجارات', 'AT08', None),
            ('8200', 'رواتب وأجور', 'AT08', None),
            ('8300', 'تأمين اجتماعي', 'AT08', None),
            ('8400', 'مصاريف عمالية', 'AT08', None),
            ('8500', 'فواتير كهرباء ومياه', 'AT08', None),
            ('8600', 'اتصالات وإنترنت', 'AT08', None),
            ('8700', 'صيانة', 'AT08', None),
            ('8800', 'توصيل وشحن', 'AT08', None),
            ('8810', 'مصروفات إهلاك', 'AT08', None),
            ('8820', 'مصروفات تأمين', 'AT08', None),
            ('8830', 'مصاريف تسويق وإعلان', 'AT08', None),
            ('8840', 'مصاريف مكتبية', 'AT08', None),
            ('8850', 'رسوم وتصاريح', 'AT08', None),
            ('8860', 'استشارات قانونية ومحاسبية', 'AT08', None),

            # مصروفات أخرى
            ('9100', 'فوائد بنكية', 'AT09', None),
            ('9200', 'خسائر غير عادية', 'AT09', None),
            ('9300', 'غرامات', 'AT09', None),

            # إيرادات أخرى
            ('10100', 'فوائد مركبة', 'AT10', None),
            ('10200', 'أرباح استثمارات', 'AT10', None),
        ]

        for data in accounts_data:
            code = data[0]
            name = data[1]
            type_code = data[2]
            parent_code = data[3] if len(data) > 3 else None
            is_bank = data[4] if len(data) > 4 else False
            is_safe = data[5] if len(data) > 5 else False
            is_tax = data[6] if len(data) > 6 else False

            parent = None
            if parent_code:
                try:
                    parent = Account.objects.get(code=parent_code)
                except Account.DoesNotExist:
                    pass

            obj, created = Account.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'account_type': types[type_code],
                    'parent': parent,
                    'is_bank': is_bank,
                    'is_safe': is_safe,
                    'tax_account': is_tax,
                }
            )
            if created:
                self.stdout.write(f'  تم إنشاء الحساب: {code} - {name}')

        self.stdout.write(self.style.SUCCESS('تم إعداد دليل الحسابات بنجاح!'))
