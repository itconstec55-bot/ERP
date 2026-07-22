import pytest


@pytest.mark.django_db
class TestSalesForms:
    def test_sales_invoice_form(self):
        from sales.forms import SalesInvoiceForm
        form = SalesInvoiceForm(data={})
        assert not form.is_valid()

    def test_customer_form(self):
        from sales.forms import CustomerForm
        form = CustomerForm(data={})
        assert not form.is_valid()


@pytest.mark.django_db
class TestPurchasesForms:
    def test_purchase_invoice_form(self):
        from purchases.forms import PurchaseInvoiceForm
        form = PurchaseInvoiceForm(data={})
        assert not form.is_valid()

    def test_supplier_form(self):
        from purchases.forms import SupplierForm
        form = SupplierForm(data={})
        assert not form.is_valid()


class TestNotificationsForms:
    def test_notification_template_form(self):
        from notifications.forms import NotificationTemplateForm
        form = NotificationTemplateForm(data={})
        assert not form.is_valid()


class TestBudgetForms:
    def test_budget_form(self):
        from budget.forms import BudgetForm
        form = BudgetForm(data={})
        assert not form.is_valid()

    def test_cost_center_form(self):
        from budget.forms import CostCenterForm
        form = CostCenterForm(data={})
        assert not form.is_valid()


class TestChequesForms:
    def test_cheque_form(self):
        from cheques.forms import ChequeForm
        form = ChequeForm(data={})
        assert not form.is_valid()


class TestTreasuryForms:
    def test_bank_form(self):
        from treasury.forms import BankForm
        form = BankForm(data={})
        assert not form.is_valid()

    def test_safe_form(self):
        from treasury.forms import SafeForm
        form = SafeForm(data={})
        assert not form.is_valid()


class TestWarehouseForms:
    def test_warehouse_form(self):
        from warehouses.forms import WarehouseForm
        form = WarehouseForm(data={})
        assert not form.is_valid()


class TestHRForms:
    def test_employee_form(self):
        from hr.forms import EmployeeForm
        form = EmployeeForm(data={})
        assert not form.is_valid()


class TestDocumentForms:
    def test_document_form(self):
        from documents.forms import DocumentForm
        form = DocumentForm(data={})
        assert not form.is_valid()


class TestContractorForms:
    def test_contractor_form(self):
        from contractors.forms import ContractorForm
        form = ContractorForm(data={})
        assert not form.is_valid()


class TestCurrencyForms:
    def test_currency_form(self):
        from currency.forms import CurrencyForm
        form = CurrencyForm(data={})
        assert not form.is_valid()


class TestSalesOrdersForms:
    def test_sales_order_form(self):
        from sales_orders.forms import SalesOrderForm
        form = SalesOrderForm(data={})
        assert not form.is_valid()


class TestPurchaseOrdersForms:
    def test_purchase_order_form(self):
        from purchase_orders.forms import PurchaseOrderForm
        form = PurchaseOrderForm(data={})
        assert not form.is_valid()


class TestGoodsReceivedForms:
    def test_goods_received_form(self):
        from goods_received.forms import GoodsReceivedNoteForm
        form = GoodsReceivedNoteForm(data={})
        assert not form.is_valid()


class TestPaymentReceiptForms:
    def test_payment_receipt_form(self):
        from payment_receipts.forms import PaymentReceiptForm
        form = PaymentReceiptForm(data={})
        assert not form.is_valid()



