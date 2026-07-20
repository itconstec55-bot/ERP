from rest_framework import serializers
from django.contrib.auth.models import User
from accounts.models import AccountType, Account, JournalEntry, JournalEntryLine
from purchases.models import Supplier, Product, ProductCategory, UnitOfMeasure, PurchaseInvoice, PurchaseInvoiceLine, CatalogSettings
from sales.models import Customer, SalesInvoice, SalesInvoiceLine
from treasury.models import Bank, Safe, BankTransaction, SafeTransaction
from hr.models import Department, Employee, Attendance, Salary
from assets.models import AssetCategory, Asset, DepreciationEntry
from warehouses.models import Warehouse, WarehouseProduct, StockMovement
from company.models import Company, CompanyBranch
from budget.models import CostCenter, Budget
from currency.models import Currency, ExchangeRateHistory
from documents.models import DocumentType, DocumentTemplate, Document, DocumentFlow, DocumentAttachment
from audit.models import AuditLog
from cheques.models import Cheque
from credit_notes.models import CreditNote
from sales_returns.models import SalesReturn, SalesReturnLine
from purchase_returns.models import PurchaseReturn, PurchaseReturnLine
from payment_receipts.models import PaymentReceipt
from stock_adjustments.models import StockAdjustment, StockAdjustmentLine
from tax_invoices.models import ETAConnection, TaxInvoice
from purchase_orders.models import PurchaseOrder, PurchaseOrderLine
from sales_orders.models import SalesOrder, SalesOrderLine
from goods_received.models import GoodsReceivedNote, GoodsReceivedLine
from requisitions.models import Requisition, RequisitionLine
from rfq.models import RFQ, RFQLine, Quotation, QuotationLine
from contractors.models import Contractor, Contract, ContractItem, InterimCertificate, CertificateItem, ContractorPayment
from recurring.models import RecurringJournal, RecurringJournalLine
from notifications.models import NotificationCategory, NotificationTemplate, NotificationLog

class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']


class AccountTypeSerializer(serializers.ModelSerializer):
    accounts_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = AccountType
        fields = '__all__'


class AccountSerializer(serializers.ModelSerializer):
    account_type_name = serializers.CharField(source='account_type.name', read_only=True)
    children_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Account
        fields = '__all__'


class JournalEntryLineSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)
    account_code = serializers.CharField(source='account.code', read_only=True)

    class Meta:
        model = JournalEntryLine
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalEntryLineSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default='')

    class Meta:
        model = JournalEntry
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'total_debit', 'total_credit', 'created_by']


class SupplierSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True, default='')

    class Meta:
        model = Supplier
        fields = '__all__'
        read_only_fields = ['id', 'current_balance', 'created_at', 'updated_at']


class ProductCategorySerializer(serializers.ModelSerializer):
    children_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProductCategory
        fields = '__all__'


class UnitOfMeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitOfMeasure
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, default='')
    unit_name = serializers.CharField(source='unit_of_measure.name', read_only=True, default='')

    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class PurchaseInvoiceLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)

    class Meta:
        model = PurchaseInvoiceLine
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'total_price']


class PurchaseInvoiceSerializer(serializers.ModelSerializer):
    lines = PurchaseInvoiceLineSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default='')
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True, default='')

    class Meta:
        model = PurchaseInvoice
        fields = '__all__'
        read_only_fields = ['id', 'subtotal', 'vat_amount', 'withholding_tax_amount', 'total_amount', 'remaining_amount', 'journal_entry', 'created_at', 'updated_at', 'created_by']


class CustomerSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True, default='')

    class Meta:
        model = Customer
        fields = '__all__'
        read_only_fields = ['id', 'current_balance', 'created_at', 'updated_at']


class SalesInvoiceLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)

    class Meta:
        model = SalesInvoiceLine
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'total_price', 'cost_total', 'profit', 'profit_margin']


class SalesInvoiceSerializer(serializers.ModelSerializer):
    lines = SalesInvoiceLineSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default='')

    class Meta:
        model = SalesInvoice
        fields = '__all__'
        read_only_fields = ['id', 'subtotal', 'vat_amount', 'withholding_tax_amount', 'total_amount', 'remaining_amount', 'cost_of_goods', 'gross_profit', 'journal_entry', 'created_at', 'updated_at', 'created_by']


class BankSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True, default='')

    class Meta:
        model = Bank
        fields = '__all__'
        read_only_fields = ['id', 'current_balance', 'created_at', 'updated_at']


class SafeSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True, default='')

    class Meta:
        model = Safe
        fields = '__all__'
        read_only_fields = ['id', 'current_balance', 'created_at', 'updated_at']


class BankTransactionSerializer(serializers.ModelSerializer):
    bank_name = serializers.CharField(source='bank.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default='')

    class Meta:
        model = BankTransaction
        fields = '__all__'
        read_only_fields = ['id', 'balance_after', 'journal_entry', 'created_at', 'updated_at', 'created_by']


class SafeTransactionSerializer(serializers.ModelSerializer):
    safe_name = serializers.CharField(source='safe.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default='')

    class Meta:
        model = SafeTransaction
        fields = '__all__'
        read_only_fields = ['id', 'balance_after', 'journal_entry', 'created_at', 'updated_at', 'created_by']


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class EmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True, default='')

    class Meta:
        model = Employee
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

    def get_employee_name(self, obj):
        return obj.employee.full_name if obj.employee else ''


class SalarySerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = Salary
        fields = '__all__'
        read_only_fields = ['id', 'net_salary', 'journal_entry', 'created_at', 'updated_at']

    def get_employee_name(self, obj):
        return obj.employee.full_name if obj.employee else ''


class AssetCategorySerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True, default='')
    depreciation_account_name = serializers.CharField(source='depreciation_account.name', read_only=True, default='')

    class Meta:
        model = AssetCategory
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class AssetSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    annual_depreciation = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    monthly_depreciation = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = Asset
        fields = '__all__'
        read_only_fields = ['id', 'accumulated_depreciation', 'net_book_value', 'journal_entry', 'created_at', 'updated_at']


class DepreciationEntrySerializer(serializers.ModelSerializer):
    asset_name = serializers.CharField(source='asset.name', read_only=True)
    asset_code = serializers.CharField(source='asset.code', read_only=True)

    class Meta:
        model = DepreciationEntry
        fields = '__all__'
        read_only_fields = ['id', 'journal_entry', 'created_at']


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class WarehouseProductSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)
    is_low = serializers.BooleanField(read_only=True)

    class Meta:
        model = WarehouseProduct
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class StockMovementSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    to_warehouse_name = serializers.CharField(source='to_warehouse.name', read_only=True, default='')
    product_name = serializers.CharField(source='product.name', read_only=True)
    performed_by_name = serializers.CharField(source='performed_by.username', read_only=True, default='')

    class Meta:
        model = StockMovement
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class CompanyBranchSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = CompanyBranch
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class CostCenterSerializer(serializers.ModelSerializer):
    children_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CostCenter
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class BudgetSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True, default='')
    cost_center_name = serializers.CharField(source='cost_center.name', read_only=True, default='')
    variance = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    variance_percent = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)

    class Meta:
        model = Budget
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = '__all__'
        read_only_fields = ['id', 'updated_at']


class ExchangeRateHistorySerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source='currency.code', read_only=True)

    class Meta:
        model = ExchangeRateHistory
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class DocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class DocumentTemplateSerializer(serializers.ModelSerializer):
    document_type_name = serializers.CharField(source='document_type.name', read_only=True)

    class Meta:
        model = DocumentTemplate
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class DocumentFlowSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source='performed_by.username', read_only=True, default='')

    class Meta:
        model = DocumentFlow
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class DocumentAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True, default='')

    class Meta:
        model = DocumentAttachment
        fields = '__all__'
        read_only_fields = ['id', 'uploaded_at']


class DocumentSerializer(serializers.ModelSerializer):
    flows = DocumentFlowSerializer(many=True, read_only=True)
    attachments = DocumentAttachmentSerializer(many=True, read_only=True)
    document_type_name = serializers.CharField(source='document_type.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default='')
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True, default='')

    class Meta:
        model = Document
        fields = '__all__'
        read_only_fields = ['id', 'document_number', 'created_at', 'updated_at']


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True, default='')

    class Meta:
        model = AuditLog
        fields = '__all__'
        read_only_fields = ['id', 'timestamp']


class ChequeSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True, default='')
    supplier_name = serializers.CharField(source='supplier.name', read_only=True, default='')

    class Meta:
        model = Cheque
        fields = '__all__'
        read_only_fields = ['id', 'journal_entry', 'created_at', 'updated_at', 'created_by']


class CreditNoteSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True, default='')
    supplier_name = serializers.CharField(source='supplier.name', read_only=True, default='')

    class Meta:
        model = CreditNote
        fields = '__all__'
        read_only_fields = ['id', 'journal_entry', 'created_at']


class SalesReturnLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = SalesReturnLine
        fields = '__all__'
        read_only_fields = ['id']


class SalesReturnSerializer(serializers.ModelSerializer):
    lines = SalesReturnLineSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, default='')

    class Meta:
        model = SalesReturn
        fields = '__all__'
        read_only_fields = ['id', 'journal_entry', 'created_at', 'created_by']


class PurchaseReturnLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = PurchaseReturnLine
        fields = '__all__'
        read_only_fields = ['id']


class PurchaseReturnSerializer(serializers.ModelSerializer):
    lines = PurchaseReturnLineSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True, default='')

    class Meta:
        model = PurchaseReturn
        fields = '__all__'
        read_only_fields = ['id', 'journal_entry', 'created_at', 'created_by']


class PaymentReceiptSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True, default='')
    supplier_name = serializers.CharField(source='supplier.name', read_only=True, default='')
    bank_name = serializers.CharField(source='bank.name', read_only=True, default='')
    safe_name = serializers.CharField(source='safe.name', read_only=True, default='')

    class Meta:
        model = PaymentReceipt
        fields = '__all__'
        read_only_fields = ['id', 'journal_entry', 'created_at', 'created_by']


class StockAdjustmentLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = StockAdjustmentLine
        fields = '__all__'
        read_only_fields = ['id']


class StockAdjustmentSerializer(serializers.ModelSerializer):
    lines = StockAdjustmentLineSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = StockAdjustment
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'created_by']


class ETAConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ETAConnection
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class TaxInvoiceSerializer(serializers.ModelSerializer):
    sales_invoice_number = serializers.CharField(source='sales_invoice.invoice_number', read_only=True, default='')

    class Meta:
        model = TaxInvoice
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']


class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = PurchaseOrderLine
        fields = '__all__'
        read_only_fields = ['id']


class PurchaseOrderSerializer(serializers.ModelSerializer):
    lines = PurchaseOrderLineSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']


class SalesOrderLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = SalesOrderLine
        fields = '__all__'
        read_only_fields = ['id']


class SalesOrderSerializer(serializers.ModelSerializer):
    lines = SalesOrderLineSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)

    class Meta:
        model = SalesOrder
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']


class GoodsReceivedLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True, default='')

    class Meta:
        model = GoodsReceivedLine
        fields = '__all__'
        read_only_fields = ['id']


class GoodsReceivedNoteSerializer(serializers.ModelSerializer):
    lines = GoodsReceivedLineSerializer(many=True, read_only=True)

    class Meta:
        model = GoodsReceivedNote
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']


class RequisitionLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True, default='')

    class Meta:
        model = RequisitionLine
        fields = '__all__'
        read_only_fields = ['id']


class RequisitionSerializer(serializers.ModelSerializer):
    lines = RequisitionLineSerializer(many=True, read_only=True)

    class Meta:
        model = Requisition
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']


class RFQLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True, default='')

    class Meta:
        model = RFQLine
        fields = '__all__'
        read_only_fields = ['id']


class RFQSerializer(serializers.ModelSerializer):
    lines = RFQLineSerializer(many=True, read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.username', read_only=True, default='')

    class Meta:
        model = RFQ
        fields = '__all__'
        read_only_fields = ['id', 'number', 'created_at', 'updated_at', 'created_by']


class QuotationLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True, default='')

    class Meta:
        model = QuotationLine
        fields = '__all__'
        read_only_fields = ['id']


class QuotationSerializer(serializers.ModelSerializer):
    lines = QuotationLineSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True, default='')

    class Meta:
        model = Quotation
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class ContractorSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True, default='')

    class Meta:
        model = Contractor
        fields = '__all__'
        read_only_fields = ['id', 'current_balance', 'created_at', 'updated_at']


class ContractItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractItem
        fields = '__all__'
        read_only_fields = ['id']


class ContractSerializer(serializers.ModelSerializer):
    items = ContractItemSerializer(many=True, read_only=True)
    contractor_name = serializers.CharField(source='contractor.name', read_only=True)

    class Meta:
        model = Contract
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']


class CertificateItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateItem
        fields = '__all__'
        read_only_fields = ['id']


class InterimCertificateSerializer(serializers.ModelSerializer):
    items = CertificateItemSerializer(many=True, read_only=True)
    contract_title = serializers.CharField(source='contract.title', read_only=True, default='')

    class Meta:
        model = InterimCertificate
        fields = '__all__'
        read_only_fields = ['id', 'journal_entry', 'created_at', 'updated_at', 'created_by']


class ContractorPaymentSerializer(serializers.ModelSerializer):
    contractor_name = serializers.CharField(source='contractor.name', read_only=True, default='')

    class Meta:
        model = ContractorPayment
        fields = '__all__'
        read_only_fields = ['id', 'journal_entry', 'created_at', 'updated_at', 'created_by']


class RecurringJournalLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurringJournalLine
        fields = '__all__'
        read_only_fields = ['id']


class RecurringJournalSerializer(serializers.ModelSerializer):
    lines = RecurringJournalLineSerializer(many=True, read_only=True)

    class Meta:
        model = RecurringJournal
        fields = '__all__'
        read_only_fields = ['id', 'last_executed', 'created_at', 'updated_at', 'created_by']


class NotificationCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationCategory
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class NotificationTemplateSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, default='')

    class Meta:
        model = NotificationTemplate
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class NotificationLogSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True, default='')

    class Meta:
        model = NotificationLog
        fields = '__all__'
        read_only_fields = ['id', 'sent_at']


class CatalogSettingsSerializer(serializers.ModelSerializer):
    default_unit_name = serializers.CharField(source='default_unit.name', read_only=True, default='')
    default_category_name = serializers.CharField(source='default_category.name', read_only=True, default='')

    class Meta:
        model = CatalogSettings
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
