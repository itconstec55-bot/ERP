"""
PostgreSQL Stress Test for Accounting System
=============================================
Tests concurrent accounting operations under load to measure:
- Throughput (transactions/sec)
- Response times (p50, p95, p99)
- Error rates
- Lock contention

Usage:
  python deploy/stress_test_postgresql.py [--users 10] [--duration 30] [--db-url postgres://...]

Requires: psycopg2-binary, threading (stdlib)
"""

import argparse
import os
import statistics
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from decimal import Decimal
from threading import Lock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'accounting_system.settings')

import django

django.setup()

from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection, transaction
from django.utils import timezone

from accounts.models import Account, AccountType, JournalEntry, JournalEntryLine
from purchases.models import Product, PurchaseInvoice, PurchaseInvoiceLine, Supplier
from sales.models import Customer, SalesInvoice, SalesInvoiceLine

REPORT_LOCK = Lock()
results = []


def setup_test_data():
    """Ensure test data exists for stress testing."""
    user, _ = User.objects.get_or_create(
        username='stress_tester', defaults={'is_staff': True, 'email': 'stress@test.local'}
    )
    user.set_password('stress123')
    user.save()

    acc_type, _ = AccountType.objects.get_or_create(
        code='stress_asset', defaults={'name': 'Stress Asset', 'account_type': 'asset'}
    )
    revenue_type, _ = AccountType.objects.get_or_create(
        code='stress_revenue', defaults={'name': 'Stress Revenue', 'account_type': 'revenue'}
    )

    cash_account, _ = Account.objects.get_or_create(
        code='STRESS-CASH', defaults={'name': 'Stress Cash', 'account_type': acc_type, 'balance': Decimal('1000000.00')}
    )
    sales_account, _ = Account.objects.get_or_create(
        code='STRESS-SALES',
        defaults={'name': 'Stress Sales Revenue', 'account_type': revenue_type, 'balance': Decimal('0.00')},
    )

    customer, _ = Customer.objects.get_or_create(
        code='STRESS-C001', defaults={'name': 'Stress Customer', 'customer_type': 'company'}
    )
    supplier, _ = Supplier.objects.get_or_create(
        code='STRESS-S001', defaults={'name': 'Stress Supplier', 'supplier_type': 'company'}
    )
    product, _ = Product.objects.get_or_create(
        code='STRESS-P001', defaults={'name': 'Stress Product', 'purchase_price': 50.00, 'selling_price': 75.00}
    )
    return {
        'user': user,
        'accounts': {'cash': cash_account, 'sales': sales_account},
        'customer': customer,
        'supplier': supplier,
        'product': product,
    }


def run_stress_cycle(data, cycle_id):
    """Execute one accounting transaction cycle."""
    start = time.monotonic()
    errors = 0
    try:
        with transaction.atomic():
            inv = SalesInvoice.objects.create(
                customer=data['customer'],
                invoice_number=f'STRESS-{cycle_id}-{int(start * 1000000) % 100000}',
                date=date.today(),
                payment_method='cash',
                is_tax_invoice=False,
                withholding_tax_type=0,
                subtotal=Decimal('100.00'),
                vat_amount=Decimal('14.00'),
                discount_amount=Decimal('0.00'),
                withholding_tax_amount=Decimal('0.00'),
                total_amount=Decimal('114.00'),
                paid_amount=Decimal('0.00'),
                remaining_amount=Decimal('114.00'),
                cost_of_goods=Decimal('0.00'),
                gross_profit=Decimal('0.00'),
                currency_amount=Decimal('114.00'),
                exchange_rate=Decimal('1.00'),
                is_posted=False,
            )
            SalesInvoiceLine.objects.create(
                sales_invoice=inv,
                product=data['product'],
                quantity=2,
                unit_price=Decimal('50.00'),
                total=Decimal('100.00'),
            )
            je = JournalEntry.objects.create(
                entry_number=f'JE-STRESS-{cycle_id}',
                date=date.today(),
                description=f'Stress test entry {cycle_id}',
                created_by=data['user'],
            )
            JournalEntryLine.objects.create(
                journal_entry=je,
                account=data['accounts']['cash'],
                debit=Decimal('114.00'),
                credit=Decimal('0.00'),
                description='Debit cash',
            )
            JournalEntryLine.objects.create(
                journal_entry=je,
                account=data['accounts']['sales'],
                debit=Decimal('0.00'),
                credit=Decimal('114.00'),
                description='Credit sales',
            )
        elapsed = time.monotonic() - start
    except Exception as e:
        elapsed = time.monotonic() - start
        errors = 1
        traceback.print_exc()

    with REPORT_LOCK:
        results.append({'cycle': cycle_id, 'elapsed': elapsed, 'errors': errors})
    return elapsed, errors


def print_results(duration, num_users, total_cycles):
    """Print formatted stress test report."""
    if not results:
        print('No results collected.')
        return

    times = [r['elapsed'] for r in results]
    total_errors = sum(r['errors'] for r in results)

    print()
    print('=' * 60)
    print('  PostgreSQL Stress Test Results')
    print('=' * 60)
    print(f'  Duration:          {duration}s')
    print(f'  Concurrent users:  {num_users}')
    print(f'  Total cycles:      {total_cycles}')
    print(f'  Successful:        {total_cycles - total_errors}')
    print(f'  Errors:            {total_errors}')
    print(
        f'  Error rate:        {total_errors / total_cycles * 100:.1f}%'
        if total_cycles > 0
        else '  Error rate:        N/A'
    )
    print(f'  Throughput:        {total_cycles / duration:.1f} txns/sec')
    print(f'  Database:          {settings.DATABASES["default"]["ENGINE"].split(".")[-1]}')
    print(f'  DB Host:           {settings.DATABASES["default"].get("HOST", "localhost")}')
    print('-' * 60)
    print('  Latency (seconds):')
    print(f'    Min:    {min(times):.4f}')
    print(f'    Max:    {max(times):.4f}')
    print(f'    Mean:   {statistics.mean(times):.4f}')
    print(f'    Median: {statistics.median(times):.4f}')
    if len(times) > 1:
        sorted_times = sorted(times)
        print(f'    p95:    {sorted_times[int(len(sorted_times) * 0.95)]:.4f}')
        print(f'    p99:    {sorted_times[int(len(sorted_times) * 0.99)]:.4f}')
    print('=' * 60)


def main():
    parser = argparse.ArgumentParser(description='PostgreSQL Stress Test for Accounting System')
    parser.add_argument('--users', type=int, default=10, help='Number of concurrent simulated users (default: 10)')
    parser.add_argument('--duration', type=int, default=30, help='Test duration in seconds (default: 30)')
    parser.add_argument(
        '--cycles', type=int, default=0, help='Fixed number of cycles per user (default: auto from duration)'
    )
    args = parser.parse_args()

    print('Setting up test data...')
    data = setup_test_data()
    print(f'  Using database: {settings.DATABASES["default"]["ENGINE"]}')
    print(f'  DB: {settings.DATABASES["default"].get("NAME", "unknown")}')
    print(f'  Host: {settings.DATABASES["default"].get("HOST", "localhost")}')

    print(f'\nStarting stress test: {args.users} concurrent users')
    if args.cycles:
        print(f'  Running {args.cycles} cycles per user...')
    else:
        print(f'  Running for {args.duration} seconds...')

    start_time = time.monotonic()
    cycle_counter = 0

    with ThreadPoolExecutor(max_workers=args.users) as executor:
        futures = []
        while True:
            elapsed = time.monotonic() - start_time
            if not args.cycles and elapsed >= args.duration:
                break
            if args.cycles and cycle_counter >= args.users * args.cycles:
                break

            cycle_counter += 1
            future = executor.submit(run_stress_cycle, data, cycle_counter)
            futures.append(future)

            if not args.cycles:
                time.sleep(max(0, args.duration / (args.users * 2) - 0.01))

        for f in as_completed(futures):
            pass

    actual_duration = time.monotonic() - start_time
    print_results(actual_duration, args.users, cycle_counter)

    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM sales_salesinvoice WHERE invoice_number LIKE 'STRESS-%'")
        cleanup_count = cursor.fetchone()[0]
        print(f'\nCleanup: {cleanup_count} stress invoices remain (DELETE if needed).')

    return 0 if cycle_counter > 0 else 1


if __name__ == '__main__':
    sys.exit(main())
