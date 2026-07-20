import uuid

from django.contrib.auth.models import User
from django.db import models, transaction

from accounts.models import JournalEntry


class PaymentReceipt(models.Model):
    TYPE_CHOICES = [('receipt', 'سند قبض'), ('payment', 'سند دفع')]
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'نقداً'),
        ('bank_transfer', 'تحويل بنكي'),
        ('cheque', 'شيك'),
        ('visa', 'فيزا/ماستر كارد'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt_number = models.CharField(max_length=50, unique=True, verbose_name='رقم السند')
    receipt_type = models.CharField(max_length=10, choices=TYPE_CHOICES, verbose_name='نوع السند')
    date = models.DateField(verbose_name='التاريخ')
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='المبلغ')
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash', verbose_name='طريقة الدفع'
    )
    customer = models.ForeignKey(
        'sales.Customer', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='العميل'
    )
    supplier = models.ForeignKey(
        'purchases.Supplier', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='المورد'
    )
    invoice = models.ForeignKey(
        'sales.SalesInvoice', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='فاتورة مبيعات'
    )
    purchase_invoice = models.ForeignKey(
        'purchases.PurchaseInvoice', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='فاتورة مشتريات'
    )
    bank = models.ForeignKey('treasury.Bank', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='البنك')
    safe = models.ForeignKey('treasury.Safe', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='الخزينة')
    cheque_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='رقم الشيك')
    description = models.TextField(blank=True, null=True, verbose_name='البيان')
    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='القيد المحاسبي'
    )
    is_posted = models.BooleanField(default=False, verbose_name='مرحل')
    currency = models.ForeignKey(
        'currency.Currency', on_delete=models.PROTECT, null=True, blank=True, verbose_name='العملة'
    )
    currency_amount = models.DecimalField(max_digits=30, decimal_places=2, default=0, verbose_name='المبلغ بالعملة')
    exchange_rate = models.DecimalField(max_digits=15, decimal_places=6, default=1, verbose_name='سعر الصرف')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='أنشئ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'سند قبض/دفع'
        verbose_name_plural = 'سندات القبض والدفع'
        ordering = ['-date']

    def __str__(self):
        return f'{self.receipt_number} - {self.get_receipt_type_display()} - {self.amount}'

    def create_journal_entry(self):
        if self.is_posted:
            return self.journal_entry
        from common.accounting_service import JournalEntryService
        from common.models import SequenceNumber
        from purchases.models import PurchaseInvoice, Supplier
        from sales.models import Customer, SalesInvoice

        if self.receipt_type == 'receipt':
            desc = f'سند قبض - {self.customer.name if self.customer else ""} - {self.receipt_number}'
            debit_account = (
                self.safe.account
                if self.safe
                else (self.bank.account if self.bank else JournalEntryService.get_account('1500'))
            )
            credit_account = (
                self.customer.account
                if self.customer and self.customer.account
                else JournalEntryService.get_account('1100')
            )
        else:
            desc = f'سند دفع - {self.supplier.name if self.supplier else ""} - {self.receipt_number}'
            debit_account = (
                self.supplier.account
                if self.supplier and self.supplier.account
                else JournalEntryService.get_account('3100')
            )
            credit_account = (
                self.safe.account
                if self.safe
                else (self.bank.account if self.bank else JournalEntryService.get_account('1500'))
            )

        with transaction.atomic():
            entry = JournalEntryService.create_entry(
                entry_type='general',
                date=self.date,
                description=desc,
                entry_number=SequenceNumber.get_next_number('journal_entry'),
                lines=[
                    {'account': debit_account, 'debit': self.amount, 'credit': 0, 'description': desc},
                    {'account': credit_account, 'debit': 0, 'credit': self.amount, 'description': desc},
                ],
                created_by=self.created_by,
            )
            self.journal_entry = entry
            self.is_posted = True
            self.save(update_fields=['journal_entry', 'is_posted'])

            if self.invoice_id:
                invoice = SalesInvoice.objects.select_for_update().get(pk=self.invoice_id)
                invoice.paid_amount += self.amount
                invoice.calculate_totals()
                invoice.save(update_fields=['paid_amount'])
                if invoice.customer_id:
                    customer = Customer.objects.select_for_update().get(pk=invoice.customer_id)
                    customer.current_balance -= self.amount
                    customer.save(update_fields=['current_balance'])
            elif self.purchase_invoice_id:
                purchase_invoice = PurchaseInvoice.objects.select_for_update().get(pk=self.purchase_invoice_id)
                purchase_invoice.paid_amount += self.amount
                purchase_invoice.calculate_totals()
                purchase_invoice.save(update_fields=['paid_amount'])
                if purchase_invoice.supplier_id:
                    supplier = Supplier.objects.select_for_update().get(pk=purchase_invoice.supplier_id)
                    supplier.current_balance -= self.amount
                    supplier.save(update_fields=['current_balance'])
        return entry
