from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count
from rest_framework.filters import SearchFilter, OrderingFilter
from django.contrib.auth.models import User
from accounts.models import AccountType, Account, JournalEntry
from purchases.models import Supplier, Product, ProductCategory, UnitOfMeasure, PurchaseInvoice
from sales.models import Customer, SalesInvoice
from treasury.models import Bank, Safe, BankTransaction, SafeTransaction
from hr.models import Department, Employee, Attendance, Salary
from assets.models import AssetCategory, Asset, DepreciationEntry
from warehouses.models import Warehouse, WarehouseProduct, StockMovement
from company.models import Company, CompanyBranch
from budget.models import CostCenter, Budget
from currency.models import Currency, ExchangeRateHistory
from documents.models import DocumentType, DocumentTemplate, Document
from audit.models import AuditLog
from cheques.models import Cheque
from credit_notes.models import CreditNote
from sales_returns.models import SalesReturn
from purchase_returns.models import PurchaseReturn
from payment_receipts.models import PaymentReceipt
from stock_adjustments.models import StockAdjustment
from tax_invoices.models import ETAConnection, TaxInvoice
from purchase_orders.models import PurchaseOrder
from sales_orders.models import SalesOrder
from goods_received.models import GoodsReceivedNote
from requisitions.models import Requisition
from rfq.models import RFQ, Quotation
from contractors.models import Contractor, Contract, InterimCertificate, ContractorPayment
from recurring.models import RecurringJournal
from notifications.models import NotificationCategory, NotificationTemplate, NotificationLog
from .serializers import *
from .pagination import StandardResultsPagination


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserBriefSerializer
    search_fields = ['username', 'first_name', 'last_name']
    pagination_class = None


class AccountTypeViewSet(viewsets.ModelViewSet):
    queryset = AccountType.objects.annotate(accounts_count=Count('accounts')).all()
    serializer_class = AccountTypeSerializer
    search_fields = ['name', 'code']
    ordering_fields = ['code', 'name']
    filterset_fields = ['account_type', 'is_active']


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.select_related('account_type', 'parent').annotate(children_count=Count('children')).all()
    serializer_class = AccountSerializer
    search_fields = ['name', 'code']
    ordering_fields = ['code', 'name', 'current_balance']
    filterset_fields = ['account_type', 'is_active', 'parent', 'is_bank', 'is_safe', 'tax_account']


class JournalEntryViewSet(viewsets.ModelViewSet):
    queryset = JournalEntry.objects.select_related('created_by').prefetch_related('lines__account').all()
    serializer_class = JournalEntrySerializer
    search_fields = ['entry_number', 'description', 'reference']
    ordering_fields = ['date', 'entry_number', 'total_debit']
    filterset_fields = ['entry_type', 'is_posted', 'is_reversed', 'date', 'created_by']

    @action(detail=True, methods=['post'])
    def post_entry(self, request, pk=None):
        entry = self.get_object()
        try:
            entry.post()
            return Response({'status': 'posted'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=True, methods=['post'])
    def reverse_entry(self, request, pk=None):
        entry = self.get_object()
        try:
            entry.reverse()
            return Response({'status': 'reversed'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.select_related('account').all()
    serializer_class = SupplierSerializer
    search_fields = ['name', 'code', 'tax_number', 'phone']
    ordering_fields = ['code', 'name', 'current_balance']
    filterset_fields = ['is_active', 'supplier_type']


class ProductCategoryViewSet(viewsets.ModelViewSet):
    queryset = ProductCategory.objects.annotate(children_count=Count('children')).all()
    serializer_class = ProductCategorySerializer
    search_fields = ['name', 'code']
    ordering_fields = ['code', 'name']
    filterset_fields = ['is_active', 'parent']


class UnitOfMeasureViewSet(viewsets.ModelViewSet):
    queryset = UnitOfMeasure.objects.all()
    serializer_class = UnitOfMeasureSerializer
    search_fields = ['name', 'code', 'symbol']
    filterset_fields = ['is_active']


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('category', 'unit_of_measure').all()
    serializer_class = ProductSerializer
    search_fields = ['name', 'code', 'barcode']
    ordering_fields = ['code', 'name', 'selling_price', 'current_stock']
    filterset_fields = ['is_active', 'category', 'unit_of_measure']


class PurchaseInvoiceViewSet(viewsets.ModelViewSet):
    queryset = PurchaseInvoice.objects.select_related('supplier', 'created_by', 'approved_by').prefetch_related('lines__product').all()
    serializer_class = PurchaseInvoiceSerializer
    search_fields = ['invoice_number', 'file_number', 'supplier__name']
    ordering_fields = ['date', 'invoice_number', 'total_amount']
    filterset_fields = ['supplier', 'is_posted', 'payment_method', 'date', 'is_tax_invoice']

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        invoice = self.get_object()
        invoice.approved_by = request.user
        invoice.approved_at = timezone.now()
        invoice.save()
        return Response({'status': 'approved'})

    @action(detail=False, methods=['post'], url_path='bulk-approve')
    def bulk_approve(self, request):
        ids = request.data.get('ids', [])
        approved = 0
        for pk in ids:
            try:
                inv = PurchaseInvoice.objects.get(pk=pk)
                inv.approve(request.user)
                approved += 1
            except Exception:
                pass
        return Response({'approved': approved, 'total': len(ids)})

    @action(detail=False, methods=['post'], url_path='bulk-post')
    def bulk_post(self, request):
        ids = request.data.get('ids', [])
        posted = 0
        errors = 0
        for pk in ids:
            try:
                inv = PurchaseInvoice.objects.get(pk=pk)
                inv.create_journal_entry()
                posted += 1
            except Exception:
                errors += 1
        return Response({'posted': posted, 'errors': errors, 'total': len(ids)})


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.select_related('account').all()
    serializer_class = CustomerSerializer
    search_fields = ['name', 'code', 'tax_number', 'phone']
    ordering_fields = ['code', 'name', 'current_balance']
    filterset_fields = ['is_active', 'customer_type']


class SalesInvoiceViewSet(viewsets.ModelViewSet):
    queryset = SalesInvoice.objects.select_related('customer', 'created_by', 'branch').prefetch_related('lines__product').all()
    serializer_class = SalesInvoiceSerializer
    search_fields = ['invoice_number', 'file_number', 'customer__name']
    ordering_fields = ['date', 'invoice_number', 'total_amount']
    filterset_fields = ['customer', 'is_posted', 'payment_method', 'date', 'branch']

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        invoice = self.get_object()
        invoice.approved_by = request.user
        invoice.approved_at = timezone.now()
        invoice.save()
        return Response({'status': 'approved'})

    @action(detail=False, methods=['post'], url_path='bulk-approve')
    def bulk_approve(self, request):
        ids = request.data.get('ids', [])
        approved = 0
        for pk in ids:
            try:
                inv = SalesInvoice.objects.get(pk=pk)
                inv.approve(request.user)
                approved += 1
            except Exception:
                pass
        return Response({'approved': approved, 'total': len(ids)})

    @action(detail=False, methods=['post'], url_path='bulk-post')
    def bulk_post(self, request):
        ids = request.data.get('ids', [])
        posted = 0
        errors = 0
        for pk in ids:
            try:
                inv = SalesInvoice.objects.get(pk=pk)
                inv.create_journal_entry()
                posted += 1
            except Exception:
                errors += 1
        return Response({'posted': posted, 'errors': errors, 'total': len(ids)})


class BankViewSet(viewsets.ModelViewSet):
    queryset = Bank.objects.select_related('account').all()
    serializer_class = BankSerializer
    search_fields = ['name', 'account_number']
    filterset_fields = ['is_active']


class SafeViewSet(viewsets.ModelViewSet):
    queryset = Safe.objects.select_related('account').all()
    serializer_class = SafeSerializer
    search_fields = ['name']
    filterset_fields = ['is_active']


class BankTransactionViewSet(viewsets.ModelViewSet):
    queryset = BankTransaction.objects.select_related('bank', 'created_by').all()
    serializer_class = BankTransactionSerializer
    search_fields = ['description', 'reference_number', 'check_number']
    ordering_fields = ['date', 'amount']
    filterset_fields = ['bank', 'transaction_type', 'date', 'is_posted']


class SafeTransactionViewSet(viewsets.ModelViewSet):
    queryset = SafeTransaction.objects.select_related('safe', 'created_by').all()
    serializer_class = SafeTransactionSerializer
    search_fields = ['description']
    ordering_fields = ['date', 'amount']
    filterset_fields = ['safe', 'transaction_type', 'date', 'is_posted']


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    search_fields = ['name']
    filterset_fields = ['is_active']


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related('department').all()
    serializer_class = EmployeeSerializer
    search_fields = ['first_name', 'last_name', 'employee_number', 'national_id']
    ordering_fields = ['employee_number', 'first_name']
    filterset_fields = ['department', 'status', 'gender']


class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.select_related('employee').all()
    serializer_class = AttendanceSerializer
    ordering_fields = ['date']
    filterset_fields = ['employee', 'status', 'date']


class SalaryViewSet(viewsets.ModelViewSet):
    queryset = Salary.objects.select_related('employee').all()
    serializer_class = SalarySerializer
    filterset_fields = ['employee', 'month', 'year', 'is_paid']
    ordering_fields = ['year', 'month']


class AssetCategoryViewSet(viewsets.ModelViewSet):
    queryset = AssetCategory.objects.select_related('account', 'depreciation_account').all()
    serializer_class = AssetCategorySerializer
    search_fields = ['name']


class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.select_related('category').all()
    serializer_class = AssetSerializer
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'purchase_date', 'purchase_price']
    filterset_fields = ['category', 'status', 'is_active', 'depreciation_method']


class DepreciationEntryViewSet(viewsets.ModelViewSet):
    queryset = DepreciationEntry.objects.select_related('asset').all()
    serializer_class = DepreciationEntrySerializer
    filterset_fields = ['asset', 'date']
    ordering_fields = ['date', 'amount']


class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    search_fields = ['code', 'name']
    filterset_fields = ['is_active']


class WarehouseProductViewSet(viewsets.ModelViewSet):
    queryset = WarehouseProduct.objects.select_related('warehouse', 'product').all()
    serializer_class = WarehouseProductSerializer
    search_fields = ['product__name', 'product__code']
    filterset_fields = ['warehouse', 'product']


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.select_related('warehouse', 'to_warehouse', 'product', 'performed_by').all()
    serializer_class = StockMovementSerializer
    search_fields = ['movement_number', 'product__name', 'reference_number']
    ordering_fields = ['date', 'quantity']
    filterset_fields = ['warehouse', 'product', 'movement_type', 'date']


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    search_fields = ['name', 'tax_number']

    @action(detail=False, methods=['get'])
    def current(self, request):
        company = Company.get_company()
        serializer = self.get_serializer(company)
        return Response(serializer.data)


class CompanyBranchViewSet(viewsets.ModelViewSet):
    queryset = CompanyBranch.objects.select_related('company').all()
    serializer_class = CompanyBranchSerializer
    search_fields = ['name']
    filterset_fields = ['company', 'is_active']


class CostCenterViewSet(viewsets.ModelViewSet):
    queryset = CostCenter.objects.annotate(children_count=Count('children')).all()
    serializer_class = CostCenterSerializer
    search_fields = ['code', 'name']
    filterset_fields = ['is_active', 'parent']


class BudgetViewSet(viewsets.ModelViewSet):
    queryset = Budget.objects.select_related('account', 'cost_center').all()
    serializer_class = BudgetSerializer
    search_fields = ['name']
    filterset_fields = ['account', 'cost_center', 'period', 'year', 'status']


class CurrencyViewSet(viewsets.ModelViewSet):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    search_fields = ['code', 'name']
    filterset_fields = ['is_active', 'is_base']


class ExchangeRateHistoryViewSet(viewsets.ModelViewSet):
    queryset = ExchangeRateHistory.objects.select_related('currency').all()
    serializer_class = ExchangeRateHistorySerializer
    filterset_fields = ['currency']
    ordering_fields = ['date']


class DocumentTypeViewSet(viewsets.ModelViewSet):
    queryset = DocumentType.objects.all()
    serializer_class = DocumentTypeSerializer
    search_fields = ['name', 'code']
    filterset_fields = ['is_active']


class DocumentTemplateViewSet(viewsets.ModelViewSet):
    queryset = DocumentTemplate.objects.select_related('document_type').all()
    serializer_class = DocumentTemplateSerializer
    search_fields = ['name']
    filterset_fields = ['document_type', 'is_active']


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.select_related('document_type', 'created_by', 'assigned_to').prefetch_related('flows', 'attachments').all()
    serializer_class = DocumentSerializer
    search_fields = ['document_number', 'title']
    ordering_fields = ['date', 'document_number']
    filterset_fields = ['document_type', 'status', 'priority', 'created_by']

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        doc = self.get_object()
        try:
            doc.approve()
            return Response({'status': 'approved'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        doc = self.get_object()
        try:
            doc.reject()
            return Response({'status': 'rejected'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related('user').all()
    serializer_class = AuditLogSerializer
    search_fields = ['model_name', 'object_repr']
    ordering_fields = ['timestamp']
    filterset_fields = ['user', 'action', 'model_name']


class ChequeViewSet(viewsets.ModelViewSet):
    queryset = Cheque.objects.select_related('customer', 'supplier').all()
    serializer_class = ChequeSerializer
    search_fields = ['cheque_number', 'bank_name', 'payee_name']
    ordering_fields = ['due_date', 'amount']
    filterset_fields = ['status', 'cheque_type', 'bank_name']


class CreditNoteViewSet(viewsets.ModelViewSet):
    queryset = CreditNote.objects.select_related('customer', 'supplier').all()
    serializer_class = CreditNoteSerializer
    search_fields = ['note_number']
    ordering_fields = ['date']
    filterset_fields = ['note_type', 'is_posted']


class SalesReturnViewSet(viewsets.ModelViewSet):
    queryset = SalesReturn.objects.select_related('customer').prefetch_related('lines__product').all()
    serializer_class = SalesReturnSerializer
    search_fields = ['return_number']
    ordering_fields = ['date']
    filterset_fields = ['customer', 'is_posted']


class PurchaseReturnViewSet(viewsets.ModelViewSet):
    queryset = PurchaseReturn.objects.select_related('supplier').prefetch_related('lines__product').all()
    serializer_class = PurchaseReturnSerializer
    search_fields = ['return_number']
    ordering_fields = ['date']
    filterset_fields = ['supplier', 'is_posted']


class PaymentReceiptViewSet(viewsets.ModelViewSet):
    queryset = PaymentReceipt.objects.select_related('customer', 'supplier', 'bank', 'safe').all()
    serializer_class = PaymentReceiptSerializer
    search_fields = ['receipt_number']
    ordering_fields = ['date', 'amount']
    filterset_fields = ['receipt_type', 'is_posted', 'payment_method', 'customer', 'supplier']


class StockAdjustmentViewSet(viewsets.ModelViewSet):
    queryset = StockAdjustment.objects.select_related('warehouse').prefetch_related('lines__product').all()
    serializer_class = StockAdjustmentSerializer
    search_fields = ['adjustment_number']
    ordering_fields = ['date']
    filterset_fields = ['warehouse', 'adjustment_type', 'status']


class ETAConnectionViewSet(viewsets.ModelViewSet):
    queryset = ETAConnection.objects.all()
    serializer_class = ETAConnectionSerializer
    filterset_fields = ['environment', 'is_active']


class TaxInvoiceViewSet(viewsets.ModelViewSet):
    queryset = TaxInvoice.objects.select_related('sales_invoice', 'connection').all()
    serializer_class = TaxInvoiceSerializer
    search_fields = ['tax_invoice_number', 'eta_uuid']
    ordering_fields = ['created_at']
    filterset_fields = ['status', 'document_type', 'connection']


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.select_related('supplier', 'cost_center').prefetch_related('lines__product').all()
    serializer_class = PurchaseOrderSerializer
    search_fields = ['order_number', 'supplier__name']
    ordering_fields = ['date']
    filterset_fields = ['supplier', 'status', 'cost_center']


class SalesOrderViewSet(viewsets.ModelViewSet):
    queryset = SalesOrder.objects.select_related('customer').prefetch_related('lines__product').all()
    serializer_class = SalesOrderSerializer
    search_fields = ['order_number', 'customer__name']
    ordering_fields = ['date']
    filterset_fields = ['customer', 'status']


class GoodsReceivedNoteViewSet(viewsets.ModelViewSet):
    queryset = GoodsReceivedNote.objects.prefetch_related('lines__product').all()
    serializer_class = GoodsReceivedNoteSerializer
    search_fields = ['grn_number']
    ordering_fields = ['date']
    filterset_fields = ['status', 'purchase_order']


class RequisitionViewSet(viewsets.ModelViewSet):
    queryset = Requisition.objects.prefetch_related('lines__product').all()
    serializer_class = RequisitionSerializer
    search_fields = ['requisition_number']
    ordering_fields = ['date']
    filterset_fields = ['status', 'priority', 'cost_center']


class RFQViewSet(viewsets.ModelViewSet):
    queryset = RFQ.objects.select_related('requested_by', 'cost_center').prefetch_related('lines__product').all()
    serializer_class = RFQSerializer
    search_fields = ['number', 'description']
    ordering_fields = ['date', 'number']
    filterset_fields = ['status', 'cost_center']


class QuotationViewSet(viewsets.ModelViewSet):
    queryset = Quotation.objects.select_related('rfq', 'supplier').prefetch_related('lines__product').all()
    serializer_class = QuotationSerializer
    search_fields = ['rfq__number']
    ordering_fields = ['date']
    filterset_fields = ['status', 'supplier', 'rfq']


class ContractorViewSet(viewsets.ModelViewSet):
    queryset = Contractor.objects.select_related('account').all()
    serializer_class = ContractorSerializer
    search_fields = ['name', 'code']
    filterset_fields = ['contractor_type', 'is_active']


class ContractViewSet(viewsets.ModelViewSet):
    queryset = Contract.objects.select_related('contractor').prefetch_related('items').all()
    serializer_class = ContractSerializer
    search_fields = ['title', 'contract_number']
    ordering_fields = ['start_date']
    filterset_fields = ['contractor', 'contract_type', 'status']


class InterimCertificateViewSet(viewsets.ModelViewSet):
    queryset = InterimCertificate.objects.select_related('contract').prefetch_related('items').all()
    serializer_class = InterimCertificateSerializer
    search_fields = ['certificate_number']
    ordering_fields = ['date']
    filterset_fields = ['status', 'contract']


class ContractorPaymentViewSet(viewsets.ModelViewSet):
    queryset = ContractorPayment.objects.select_related('contract', 'contract__contractor').all()
    serializer_class = ContractorPaymentSerializer
    search_fields = ['payment_number']
    ordering_fields = ['payment_date']
    filterset_fields = ['contract', 'payment_method', 'status']


class RecurringJournalViewSet(viewsets.ModelViewSet):
    queryset = RecurringJournal.objects.prefetch_related('lines').all()
    serializer_class = RecurringJournalSerializer
    search_fields = ['description']
    filterset_fields = ['frequency', 'status']
    ordering_fields = ['name', 'next_due_date', 'created_at']
    ordering = ['name']


class NotificationCategoryViewSet(viewsets.ModelViewSet):
    queryset = NotificationCategory.objects.all()
    serializer_class = NotificationCategorySerializer
    search_fields = ['name']


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    queryset = NotificationTemplate.objects.select_related('category').all()
    serializer_class = NotificationTemplateSerializer
    search_fields = ['name']
    filterset_fields = ['event', 'is_active']


class NotificationLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NotificationLog.objects.select_related('template').all()
    serializer_class = NotificationLogSerializer
    filterset_fields = ['success', 'template']
    ordering_fields = ['sent_at']


class AuthRateThrottle(SimpleRateThrottle):
    """تقييد معدل محاولات تسجيل الدخول عبر API — 20 محاولة في الساعة."""
    scope = 'auth'

    def get_cache_key(self, request: object, view: object) -> str:
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            ip = forwarded.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return f'auth_throttle_{ip}'


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def api_login(request: object) -> Response:
    """API login endpoint — returns auth token"""
    username = request.data.get('username', '')
    password = request.data.get('password', '')
    user = authenticate(username=username, password=password)
    if user is None:
        return Response({'error': 'اسم المستخدم أو كلمة المرور غير صحيحة'}, status=401)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'user_id': user.pk,
        'username': user.username,
        'is_superuser': user.is_superuser,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@cache_page(60)
def api_dashboard(request: object) -> Response:
    """Dashboard summary API endpoint"""
    from accounts.models import Account, JournalEntry
    from sales.models import SalesInvoice, Customer
    from purchases.models import PurchaseInvoice, Supplier
    from django.db import models
    from datetime import date
    
    today = date.today()
    month_start = today.replace(day=1)
    
    sales_this_month = SalesInvoice.objects.filter(
        date__gte=month_start, is_posted=True
    ).count()
    purchases_this_month = PurchaseInvoice.objects.filter(
        date__gte=month_start, is_posted=True
    ).count()
    total_receivable = Customer.objects.aggregate(
        total=models.Sum('current_balance')
    )['total'] or 0
    total_payable = Supplier.objects.aggregate(
        total=models.Sum('current_balance')
    )['total'] or 0
    recent_entries = JournalEntry.objects.order_by('-date')[:5].values(
        'entry_number', 'date', 'description', 'entry_type', 'total_debit', 'total_credit'
    )
    
    return Response({
        'sales_this_month': sales_this_month,
        'purchases_this_month': purchases_this_month,
        'total_receivable': float(total_receivable),
        'total_payable': float(total_payable),
        'recent_entries': list(recent_entries),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_stock_summary(request: object) -> Response:
    """Stock summary API endpoint"""
    from warehouses.models import WarehouseProduct
    from django.db.models import Sum
    
    products = WarehouseProduct.objects.select_related(
        'product', 'warehouse'
    ).values(
        'product__name', 'product__code', 'warehouse__name'
    ).annotate(
        total_qty=Sum('quantity')
    ).order_by('product__name')[:50]
    
    return Response(list(products))
