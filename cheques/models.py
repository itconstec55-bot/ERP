from decimal import Decimal
from django.db import models
import uuid


class Cheque(models.Model):
    CHEQUE_TYPE_CHOICES = [
        ('received', 'شيك وارد'),
        ('issued', 'شيك صادر'),
    ]
    STATUS_CHOICES = [
        ('pending', 'قيد الانتظار'),
        ('deposited', 'ودع في البنك'),
        ('cleared', 'محصل'),
        ('bounced', 'مرتجع'),
        ('cancelled', 'ملغي'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cheque_number = models.CharField(max_length=50, verbose_name='رقم الشيك')
    cheque_type = models.CharField(max_length=10, choices=CHEQUE_TYPE_CHOICES, verbose_name='نوع الشيك')
    bank_name = models.CharField(max_length=100, verbose_name='البنك')
    branch = models.CharField(max_length=100, blank=True, null=True, verbose_name='الفرع')
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='المبلغ')
    currency = models.CharField(max_length=3, default='EGP', verbose_name='العملة')
    issue_date = models.DateField(verbose_name='تاريخ الإصدار')
    due_date = models.DateField(verbose_name='تاريخ الاستحقاق')
    payee_name = models.CharField(max_length=200, blank=True, null=True, verbose_name='المستفيد/الدافع')
    customer = models.ForeignKey('sales.Customer', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='العميل')
    supplier = models.ForeignKey('purchases.Supplier', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='المورد')
    invoice = models.ForeignKey('sales.SalesInvoice', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='فاتورة مبيعات')
    purchase_invoice = models.ForeignKey('purchases.PurchaseInvoice', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='فاتورة مشتريات')
    bank_account = models.ForeignKey('accounts.Account', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='cheques', verbose_name='الحساب البنكي')
    gl_account = models.ForeignKey('accounts.Account', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='cheque_gl_entries', verbose_name='حساب الشيكات المحاسبي')
    journal_entry = models.ForeignKey('accounts.JournalEntry', on_delete=models.SET_NULL, null=True, blank=True,
                                      verbose_name='القيد المحاسبي')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending', db_index=True, verbose_name='الحالة')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'شيك'
        verbose_name_plural = 'الشيكات'
        ordering = ['-due_date']

    def __str__(self):
        return f'{self.cheque_number} - {self.bank_name} - {self.amount}'

    def _get_gl_account(self):
        if self.gl_account_id:
            return self.gl_account
        from common.accounting_service import JournalEntryService
        try:
            return JournalEntryService.get_account('2140')
        except Exception:
            return None

    def post_issuance(self, user=None):
        """ترحيل إصدار شيك صادر للاستاذ العام: مدين حساب الشيكات الصادرة، دائن حساب البنك."""
        from common.accounting_service import JournalEntryService
        from common.models import SequenceNumber
        from common.exceptions import AccountingError
        if self.journal_entry_id:
            return None
        gl = self._get_gl_account()
        bank = self.bank_account
        if not gl or not bank:
            raise AccountingError(
                'يجب ربط حساب بنكي وحساب شيكات صادرة بالشيك لترحيله للاستاذ العام.'
            )
        entry = JournalEntryService.create_entry(
            entry_type='payment',
            date=self.issue_date,
            description=f'إصدار شيك صادر رقم {self.cheque_number} - {self.payee_name or ""}',
            reference=self.cheque_number,
            lines=[
                {
                    'account': gl,
                    'debit': self.amount,
                    'credit': Decimal('0'),
                    'description': 'التزام شيك صادر (دفع)',
                },
                {
                    'account': bank,
                    'debit': Decimal('0'),
                    'credit': self.amount,
                    'description': 'خصم حساب البنك',
                },
            ],
            created_by=user,
            entry_number=SequenceNumber.get_next_number('journal_entry'),
        )
        self.journal_entry = entry
        self.save(update_fields=['journal_entry'])
        return entry

    def post_clearing(self, user=None):
        """عند التحصيل/الإيداع: عكس قيد الإصدار إن وُجد، وإلا إنشاء قيد تحصيل لشيك وارد."""
        from common.accounting_service import JournalEntryService
        from common.models import SequenceNumber
        if self.journal_entry_id and not self.journal_entry.is_reversed:
            self.journal_entry.reverse()
            return self.journal_entry
        if not self.journal_entry_id:
            gl = self._get_gl_account()
            bank = self.bank_account
            if gl and bank:
                entry = JournalEntryService.create_entry(
                    entry_type='receipt',
                    date=self.due_date,
                    description=f'تحصيل شيك وارد رقم {self.cheque_number}',
                    reference=self.cheque_number,
                    lines=[
                        {
                            'account': bank,
                            'debit': self.amount,
                            'credit': Decimal('0'),
                            'description': 'إيداع شيك وارد بالبنك',
                        },
                        {
                            'account': gl,
                            'debit': Decimal('0'),
                            'credit': self.amount,
                            'description': 'حساب الشيكات الواردة',
                        },
                    ],
                    created_by=user,
                    entry_number=SequenceNumber.get_next_number('journal_entry'),
                )
                self.journal_entry = entry
                self.save(update_fields=['journal_entry'])
                return entry
        return None

    def reverse_gl(self, user=None):
        """عكس القيد المحاسبي المرتبط بالشيك (ارتداد/إلغاء)."""
        if self.journal_entry_id and not self.journal_entry.is_reversed:
            self.journal_entry.reverse()
            return True
        return False
