import json
from datetime import datetime
from decimal import Decimal

from django.db.models import Sum

from accounts.models import Account, JournalEntry
from purchases.models import PurchaseInvoice
from sales.models import SalesInvoice

from .detector import AccountingErrorDetector
from .models import ErrorLog, Solution
from .prompts import ACCOUNTING_ERROR_PROMPT
from .standards import get_applicable_standards, validate_solution_against_standards


class AIAccountingAnalyzer:
    """خدمة تحليل الأخطاء المحاسبية بالذكاء الاصطناعي"""

    def __init__(self):
        self.detector = AccountingErrorDetector()

    def auto_detect_and_analyze(self):
        """كشف الأخطاء تلقائياً وتحليلها"""
        raw_errors = self.detector.scan_all()

        # إضافة فحوصات خاصة
        raw_errors.extend(self.detector.detect_specific_unbalanced_sales())
        raw_errors.extend(self.detector.detect_specific_unbalanced_purchases())
        raw_errors.extend(self.detector.detect_specific_unbalanced_salaries())

        analyzed_errors = []
        for error_data in raw_errors:
            # حفظ في قاعدة البيانات
            error_log = self._save_error_log(error_data)

            # بناء السياق المحاسبي
            context = self._build_accounting_context(error_data)

            # إنشاء البرومبت
            prompt = self._build_analysis_prompt(error_data, context)

            # تحليل المعايير
            standards_check = self._check_standards(error_data)

            # بناء الحلول المقترحة
            solutions = self._generate_solutions(error_data, context, standards_check)

            analyzed_errors.append(
                {
                    'error': error_log,
                    'context': context,
                    'prompt': prompt,
                    'standards_check': standards_check,
                    'solutions': solutions,
                }
            )

        return analyzed_errors

    def analyze_single_error(self, error_data):
        """تحليل خطأ واحد"""
        # التحقق من اكتمال البيانات
        missing = self._validate_data_completeness(error_data)
        if missing:
            return {
                'status': 'missing_data',
                'missing_fields': missing,
                'message': self._generate_missing_data_message(missing),
            }

        # حفظ الخطأ
        error_log = self._save_error_log(error_data)

        # بناء السياق
        context = self._build_accounting_context(error_data)

        # إنشاء البرومبت
        prompt = self._build_analysis_prompt(error_data, context)

        # تحليل المعايير
        standards_check = self._check_standards(error_data)

        # بناء الحلول
        solutions = self._generate_solutions(error_data, context, standards_check)

        # تحديث الحالة
        error_log.status = 'analyzed'
        error_log.save()

        return {
            'status': 'success',
            'error': error_log,
            'context': context,
            'prompt': prompt,
            'standards_check': standards_check,
            'solutions': solutions,
        }

    def _validate_data_completeness(self, error_data):
        """التحقق من اكتمال البيانات"""
        required_fields = {'error_type': 'نوع الخطأ', 'description': 'الوصف'}
        missing = []
        for field, label in required_fields.items():
            if not error_data.get(field):
                missing.append({'field': field, 'label': label})
        return missing

    def _generate_missing_data_message(self, missing_fields):
        """إنشاء رسالة البيانات المفقودة"""
        fields_text = '\n'.join([f'- {f["label"]}' for f in missing_fields])
        return f"""
## بيانات مطلوبة إضافياً

يرجى توفير المعلومات التالية لتمكين التحليل الدقيق:

{fields_text}

### لماذا هذه البيانات مهمة؟
- **نوع الخطأ:** لتحديد الطريقة المناسبة للعلاج
- **الوصف:** لفهم السياق والسبب الجذری

### كيفية الحصول على البيانات
- راجع القيود المحاسبية في دليل الحسابات
- تحقق من الفواتير المرتبطة بالقيد
- راجع السجلات البنكية إذا كان الخطأ يتعلق بالتسوية

بمجرد توفير هذه البيانات، سنتمكن من تقديم تحليل دقيق وحلول مناسبة.
"""

    def _save_error_log(self, error_data):
        """حفظ سجل الخطأ"""
        error_log = ErrorLog.objects.create(
            error_type=error_data.get('error_type', 'UNKNOWN'),
            severity=error_data.get('severity', 'medium'),
            title=error_data.get('title', 'خطأ غير محدد'),
            description=error_data.get('description', ''),
            reference_number=error_data.get('reference_number', ''),
            affected_account_code=error_data.get('affected_account_code', ''),
            affected_account_name=error_data.get('affected_account_name', ''),
            amount=Decimal(str(error_data.get('amount', 0))),
            entry_date=error_data.get('entry_date'),
            journal_entry_id=error_data.get('journal_entry_id'),
            raw_data=error_data.get('raw_data', {}),
            detected_by='auto_detector',
        )
        return error_log

    def _build_accounting_context(self, error_data):
        """بناء السياق المحاسبي"""
        context = {'account_balances': {}, 'recent_entries': [], 'fiscal_year_info': {}, 'vat_status': {}}

        # أرصدة الحسابات الرئيسية
        main_accounts = ['1100', '1200', '1300', '1350', '2300', '3100', '3200', '3300', '4100', '5100']
        for code in main_accounts:
            try:
                account = Account.objects.get(code=code)
                context['account_balances'][code] = {
                    'name': account.name,
                    'balance': str(account.current_balance),
                    'type': account.account_type.account_type,
                }
            except Account.DoesNotExist:
                pass

        # آخر 10 قيود
        recent = JournalEntry.objects.filter(is_posted=True).order_by('-date')[:10]
        for entry in recent:
            context['recent_entries'].append(
                {
                    'number': entry.entry_number,
                    'date': str(entry.date),
                    'type': entry.entry_type,
                    'debit': str(entry.total_debit),
                    'credit': str(entry.total_credit),
                }
            )

        # معلومات السنة المالية
        today = datetime.now().date()
        context['fiscal_year_info'] = {'current_date': str(today), 'year': today.year, 'month': today.month}

        # حالة VAT
        vat_output = SalesInvoice.objects.filter(is_posted=True, is_tax_invoice=True).aggregate(
            total=Sum('vat_amount')
        )['total'] or Decimal('0')
        vat_input = PurchaseInvoice.objects.filter(is_posted=True, is_tax_invoice=True).aggregate(
            total=Sum('vat_amount')
        )['total'] or Decimal('0')

        context['vat_status'] = {'output': str(vat_output), 'input': str(vat_input), 'net': str(vat_output - vat_input)}

        return context

    def _build_analysis_prompt(self, error_data, context):
        """إنشاء البرومبت للتحليل"""
        prompt = ACCOUNTING_ERROR_PROMPT.format(
            error_type=error_data.get('error_type', 'غير محدد'),
            severity=error_data.get('severity', 'غير محدد'),
            title=error_data.get('title', 'غير محدد'),
            description=error_data.get('description', 'غير محدد'),
            reference_number=error_data.get('reference_number', 'غير محدد'),
            affected_account=error_data.get('affected_account_code', 'غير محدد'),
            amount=error_data.get('amount', 0),
            entry_date=error_data.get('entry_date', 'غير محدد'),
            raw_data=json.dumps(error_data.get('raw_data', {}), ensure_ascii=False, default=str),
            accounting_context=json.dumps(context, ensure_ascii=False, default=str),
        )
        return prompt

    def _check_standards(self, error_data):
        """التحقق من المعايير المحاسبية"""
        error_type = error_data.get('error_type', '')
        applicable = get_applicable_standards(error_type)
        solution_text = json.dumps(error_data, ensure_ascii=False, default=str)
        result = validate_solution_against_standards(solution_text, error_type)
        return {
            'applicable_standards': applicable,
            'is_compliant': result['is_compliant'],
            'violations': result['violations'],
            'warnings': result.get('warnings', []),
        }

    def _generate_solutions(self, error_data, context, standards_check):
        """توليد الحلول المقترحة وحفظها في قاعدة البيانات"""
        error_type = error_data.get('error_type', '')
        solutions = []

        if error_type == 'UNBALANCED_ENTRY':
            raw_solutions = self._solutions_unbalanced_entry(error_data, context)
        elif error_type == 'DUPLICATE_ENTRY':
            raw_solutions = self._solutions_duplicate_entry(error_data, context)
        elif error_type == 'MISSING_ACCOUNT':
            raw_solutions = self._solutions_missing_account(error_data, context)
        elif error_type == 'NEGATIVE_BALANCE':
            raw_solutions = self._solutions_negative_balance(error_data, context)
        elif error_type == 'RECONCILIATION_DIFF':
            raw_solutions = self._solutions_reconciliation(error_data, context)
        elif error_type == 'SALES_DISCOUNT_UNBALANCED':
            raw_solutions = self._solutions_sales_discount(error_data, context)
        elif error_type == 'PURCHASE_DISCOUNT_UNBALANCED':
            raw_solutions = self._solutions_purchase_discount(error_data, context)
        elif error_type == 'SALARY_DEDUCTIONS_UNBALANCED':
            raw_solutions = self._solutions_salary_deductions(error_data, context)
        else:
            raw_solutions = self._solutions_generic(error_data, context)

        error_log = ErrorLog.objects.filter(error_type=error_type, status='pending').order_by('-created_at').first()

        if not error_log:
            error_log = ErrorLog.objects.filter(error_type=error_type).order_by('-created_at').first()

        for sol_data in raw_solutions:
            sol = Solution.objects.create(
                error_log=error_log,
                title=sol_data['title'],
                description=sol_data['description'],
                steps=sol_data.get('steps', []),
                financial_impact=sol_data.get('financial_impact', ''),
                risk_level=sol_data.get('risk_level', 'medium'),
                priority=sol_data.get('priority', 1),
            )
            solutions.append(sol)

        return solutions

    def _solutions_unbalanced_entry(self, error_data, context):
        """حلول القيود غير المتوازنة"""
        return [
            {
                'priority': 1,
                'title': 'إضافة سطر قيد تعويضي',
                'description': 'إضافة سطر قيد جديد لتعديل الفرق بين المدين والدائن',
                'steps': [
                    'تحديد الحساب الذي ينقص فيه المبلغ',
                    'إنشاء سطر قيد جديد بالفرق المطلوب',
                    'مراجعة القيد للتأكد من التوازن',
                    'ترحيل القيد المعدل',
                ],
                'financial_impact': 'سيؤثر على أرصدة الحسابات المتأثرة',
                'risk_level': 'low',
            },
            {
                'priority': 2,
                'title': 'عكس القيد وإعادة إنشائه',
                'description': 'عكس القيد الحالي وإنشائه بشكل صحيح',
                'steps': [
                    'عكس القيد الحالي',
                    'إنشاء قيد جديد بالبيانات الصحيحة',
                    'تأكد من توازن القيد الجديد',
                    'ترحيل القيد الجديد',
                ],
                'financial_impact': 'سيؤثر على أرصدة الحسابات المتأثرة',
                'risk_level': 'medium',
            },
            {
                'priority': 3,
                'title': 'تسوية عبر حساب التسوية',
                'description': 'تسجيل الفرق في حساب تسوية خاص',
                'steps': ['إنشاء حساب تسوية جديد', 'تسجيل الفرق في حساب التسوية', 'مراجعة الحساب في نهاية الفترة'],
                'financial_impact': 'يؤثر بشكل مؤقت على الميزانية',
                'risk_level': 'high',
            },
        ]

    def _solutions_duplicate_entry(self, error_data, context):
        """حلول القيود المكررة"""
        return [
            {
                'priority': 1,
                'title': 'عكس القيد المكرر',
                'description': 'عكس أحد القيدين المكررين وتسجيل ملاحظة',
                'steps': ['تحديد القيد المكرر', 'عكس القيد المكرر', 'إضافة ملاحظة توضيحية', 'مراجعة الأرصدة'],
                'financial_impact': 'سيتم إزالة التأثير المكرر على الأرصدة',
                'risk_level': 'low',
            },
            {
                'priority': 2,
                'title': 'حذف القيد المكرر',
                'description': 'حذف القيد المكرر نهائياً',
                'steps': ['التأكد من أن القيد مكرر فعلاً', 'حذف القيد المكرر', 'مراجعة الأرصدة'],
                'financial_impact': 'سيتم إزالة التأثير المكرر على الأرصدة',
                'risk_level': 'medium',
            },
        ]

    def _solutions_missing_account(self, error_data, context):
        """حلول الحسابات المفقودة"""
        account_code = error_data.get('affected_account_code', '')
        return [
            {
                'priority': 1,
                'title': f'إنشاء الحساب المفقود: {account_code}',
                'description': f'إنشاء حساب جديد بالكود {account_code} في دليل الحسابات',
                'steps': [
                    'الذهاب إلى دليل الحسابات',
                    f'إنشاء حساب جديد بالكود {account_code}',
                    'تحديد نوع الحساب المناسب',
                    'تحديد الحساب الأب',
                    'تفعيل الحساب',
                ],
                'financial_impact': 'لا يؤثر مباشرة على القوائم المالية',
                'risk_level': 'low',
            }
        ]

    def _solutions_negative_balance(self, error_data, context):
        """حلول الأرصدة السالبة"""
        return [
            {
                'priority': 1,
                'title': 'مراجعة القيود المؤثرة',
                'description': 'مراجعة جميع القيود التي أثرت على هذا الحساب',
                'steps': [
                    'عرض جميع القيود على الحساب',
                    'تحديد القيود الخاطئة',
                    'عكس أو تعديل القيود الخاطئة',
                    'التأكد من توازن الأرصدة',
                ],
                'financial_impact': 'سيؤثر على أرصدة الحسابات المتأثرة',
                'risk_level': 'medium',
            },
            {
                'priority': 2,
                'title': 'تسجيل تسوية تعويضية',
                'description': 'تسجيل قيد تعويضي لتصحيح الرصيد',
                'steps': ['تحديد الحساب المعوض', 'إنشاء قيد تعويضي', 'مراجعة الأرصدة'],
                'financial_impact': 'سيؤثر على أرصدة الحسابات المتأثرة',
                'risk_level': 'low',
            },
        ]

    def _solutions_reconciliation(self, error_data, context):
        """حلول فروقات التسوية البنكية"""
        return [
            {
                'priority': 1,
                'title': 'مراجعة المعاملات البنكية',
                'description': 'مراجعة جميع المعاملات_bankية ومقارنتها بالسجلات',
                'steps': [
                    'طباعة كشف حساب البنك',
                    'مراجعة كل معاملة مع القيد المحاسبي',
                    'تحديد المعاملات غير المسجلة',
                    'تسجيل المعاملات المفقودة',
                    'تحديث رصيد التسوية',
                ],
                'financial_impact': 'سيتم تعديل أرصدة البنوك والخزائن',
                'risk_level': 'low',
            },
            {
                'priority': 2,
                'title': 'تسجيل قيود التسوية',
                'description': 'تسجيل قيود تسوية للفروقات',
                'steps': ['تحديد طبيعة الفروق', 'إنشاء قيود تسوية مناسبة', 'مراجعة الأرصدة'],
                'financial_impact': 'سيتم تعديل أرصدة البنوك والخزائن',
                'risk_level': 'medium',
            },
        ]

    def _solutions_sales_discount(self, error_data, context):
        """حلول عدم توازن قيود المبيعات مع الخصم"""
        return [
            {
                'priority': 1,
                'title': 'تصحيح القيد بإضافة سطر الخصم',
                'description': 'إضافة سطر قيد لتسجيل الخصم في حساب مناسب',
                'steps': [
                    'تحديد حساب الخصم المناسب',
                    'إنشاء سطر قيد بالخصم (مدين)',
                    'تعديل سطر العميل (الدائن)',
                    'التأكد من توازن القيد',
                    'ترحيل القيد المعدل',
                ],
                'financial_impact': 'سيؤثر على قائمة الدخل (تخفيض الإيرادات)',
                'risk_level': 'low',
            },
            {
                'priority': 2,
                'title': 'عكس القيد وإعادة إنشائه',
                'description': 'عكس القيد الحالي وإنشائه بشكل صحيح مع الخصم',
                'steps': [
                    'عكس القيد الحالي',
                    'إنشاء قيد جديد بالبيانات الصحيحة',
                    'إضافة سطر الخصم',
                    'التأكد من التوازن',
                    'ترحيل القيد الجديد',
                ],
                'financial_impact': 'سيؤثر على قائمة الدخل (تخفيض الإيرادات)',
                'risk_level': 'medium',
            },
        ]

    def _solutions_purchase_discount(self, error_data, context):
        """حلول عدم توازن قيود المشتريات مع الخصم والتحصيل"""
        return [
            {
                'priority': 1,
                'title': 'تصحيح القيد بتسجيل الخصم والتحصيل',
                'description': 'تعديل القيد لتسجيل الخصم والتحصيل بشكل صحيح',
                'steps': [
                    'تحديد حساب الخصم والتحصيل',
                    'إنشاء سطر قيد مناسب',
                    'تعديل أطراف القيد الأخرى',
                    'التأكد من التوازن',
                    'ترحيل القيد المعدل',
                ],
                'financial_impact': 'سيؤثر على الميزانية العمومية',
                'risk_level': 'low',
            }
        ]

    def _solutions_salary_deductions(self, error_data, context):
        """حلول عدم توازن قيود الرواتب"""
        return [
            {
                'priority': 1,
                'title': 'تسجيل الخصومات في حساب مناسب',
                'description': 'إضافة سطر قيد لتسجيل الخصومات في حساب مخصص',
                'steps': [
                    'تحديد حساب الخصومات المناسب',
                    'إنشاء سطر قيد بالخصومات (دائن)',
                    'تعديل سطر رواتب مستحقة (المدين)',
                    'التأكد من التوازن',
                    'ترحيل القيد المعدل',
                ],
                'financial_impact': 'سيؤثر على قائمة الدخل والميزانية العمومية',
                'risk_level': 'low',
            }
        ]

    def _solutions_generic(self, error_data, context):
        """حلول عامة"""
        return [
            {
                'priority': 1,
                'title': 'مراجعة القيود المحاسبية',
                'description': 'مراجعة شاملة للقيود المرتبطة بالخطأ',
                'steps': [
                    'عرض جميع القيود المرتبطة',
                    'تحديد القيود الخاطئة',
                    'عكس أو تعديل القيود الخاطئة',
                    'التأكد من توازن الأرصدة',
                ],
                'financial_impact': 'يعتمد على طبيعة الخطأ',
                'risk_level': 'medium',
            }
        ]

    def apply_solution(self, solution_id, user):
        """تطبيق حل مقترح"""
        try:
            solution = Solution.objects.get(pk=solution_id)
            solution.applied = True
            solution.applied_by = user
            from django.utils import timezone

            solution.applied_at = timezone.now()
            solution.save()

            # تحديث حالة الخطأ
            error_log = solution.error_log
            error_log.status = 'resolved'
            error_log.resolved_by = user
            error_log.resolved_at = timezone.now()
            error_log.save()

            return {'status': 'success', 'message': 'تم تطبيق الحل بنجاح'}
        except Solution.DoesNotExist:
            return {'status': 'error', 'message': 'الحل غير موجود'}
