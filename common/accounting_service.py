import logging
from decimal import Decimal
from django.db import transaction
from accounts.models import Account, JournalEntry, JournalEntryLine
from common.exceptions import (AccountingError, UnbalancedEntryError, 
                                AccountNotFoundError, InsufficientStockError)

logger = logging.getLogger('accounting')


class JournalEntryService:

    @staticmethod
    @transaction.atomic
    def create_entry(
        entry_type,
        date,
        description,
        reference='',
        lines=None,
        created_by=None,
        entry_number=None,
        file_number=None,
    ):
        if lines is None:
            lines = []
        
        if not lines:
            raise UnbalancedEntryError('القيد يجب أن يحتوي على بنود')
        
        # التحقق من توازن القيد
        total_debit = sum(Decimal(str(line.get('debit', 0))) for line in lines)
        total_credit = sum(Decimal(str(line.get('credit', 0))) for line in lines)
        
        if total_debit != total_credit:
            raise UnbalancedEntryError(
                f'القيد غير متوازن: مدين={total_debit}, دائن={total_credit}'
            )
        
        if total_debit == 0 and total_credit == 0:
            raise UnbalancedEntryError('القيود لا يمكن أن تكون صفر مدين وصفر دائن')
        
        # التحقق من وجود الحسابات وقفلها
        for i, line in enumerate(lines):
            if not line.get('account'):
                raise AccountNotFoundError(f'حساب غير محدد في البند رقم {i + 1}')
        
        account_codes = [line['account'].code if hasattr(line['account'], 'code') else line['account'] for line in lines]
        account_codes = [c for c in account_codes if c]
        
        if not account_codes:
            raise AccountNotFoundError('لا توجد حسابات صالحة في القيود')
        
        accounts = Account.objects.filter(code__in=account_codes).select_for_update()
        accounts_dict = {acc.code: acc for acc in accounts}
        
        missing = set(account_codes) - set(accounts_dict.keys())
        if missing:
            raise AccountNotFoundError(f'حسابات غير موجودة: {missing}')

        entry = JournalEntry.objects.create(
            entry_number=entry_number or reference,
            date=date,
            entry_type=entry_type,
            description=description,
            reference=reference,
            file_number=file_number,
            total_debit=total_debit,
            total_credit=total_credit,
            created_by=created_by,
        )
        
        for line_data in lines:
            account_obj = line_data['account']
            if isinstance(account_obj, str):
                account_obj = accounts_dict[account_obj]
            
            debit = Decimal(str(line_data.get('debit', 0)))
            credit = Decimal(str(line_data.get('credit', 0)))
            
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=account_obj,
                debit=debit,
                credit=credit,
                description=line_data.get('description', ''),
            )
            
            account_obj.current_balance += debit - credit
            account_obj.save(update_fields=['current_balance'])
        
        entry.is_posted = True
        entry.save(update_fields=['is_posted'])
        
        logger.info(
            'Journal entry created: type=%s ref=%s total=%.2f',
            entry_type, reference, total_debit,
        )
        return entry

    @staticmethod
    def get_account(code, default_code=None):
        account = Account.objects.filter(code=code).first()
        if not account and default_code:
            account = Account.objects.filter(code=default_code).first()
        if not account:
            logger.error('Account code %s not found (fallback: %s)', code, default_code)
            raise AccountNotFoundError(f'الحساب المحاسبي برمز {code} غير موجود')
        return account
