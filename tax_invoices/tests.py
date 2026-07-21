import uuid
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from sales.models import Customer, SalesInvoice


class TestTaxInvoice:
    @pytest.mark.django_db
    def test_tax_invoice_list_requires_login(self, client):
        url = reverse('tax_invoices:tax_invoice_list')
        response = client.get(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_tax_invoice_detail_requires_login(self, client):
        url = reverse('tax_invoices:tax_invoice_detail', kwargs={'pk': uuid.uuid4()})
        response = client.get(url)
        assert response.status_code == 302


class TestTaxInvoiceGeneration:
    @pytest.mark.django_db
    def test_create_from_sales_invoice_requires_login(self, client):
        url = reverse('tax_invoices:tax_invoice_create_from_sales', kwargs={'sales_pk': uuid.uuid4()})
        response = client.post(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_create_from_sales_invoice_with_auth(self, client):
        user = User.objects.create_superuser(username='admin', password='admin123', email='admin@test.com')
        client.login(username='admin', password='admin123')
        customer = Customer.objects.create(code='C001', name='عميل تجريبي', customer_type='company')
        invoice = SalesInvoice.objects.create(
            customer=customer,
            invoice_number='INV-001',
            date=date.today(),
            payment_method='cash',
            is_tax_invoice=False,
            withholding_tax_type=0,
            subtotal=1000.00,
            vat_amount=140.00,
            discount_amount=0,
            withholding_tax_amount=0,
            total_amount=1000.00,
            paid_amount=0,
            remaining_amount=1000.00,
            cost_of_goods=0,
            gross_profit=1000.00,
            currency_amount=1000.00,
            exchange_rate=1.0,
            is_posted=False,
        )
        url = reverse('tax_invoices:tax_invoice_create_from_sales', kwargs={'sales_pk': invoice.pk})
        response = client.post(url)
        assert response.status_code in (200, 302)
