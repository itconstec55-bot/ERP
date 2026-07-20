from django.db import migrations


def create_standard_accounts(apps, schema_editor):
    Account = apps.get_model('accounts', 'Account')
    AccountType = apps.get_model('accounts', 'AccountType')

    asset_type, _ = AccountType.objects.get_or_create(
        code='asset', defaults={'name': 'أصول'})
    revenue_type, _ = AccountType.objects.get_or_create(
        code='revenue', defaults={'name': 'إيرادات'})

    standard = [
        ('1140', 'ضريبة الخصم والتحصيل تحت التحصيل', asset_type),
        ('4101', 'خصم على المبيعات', revenue_type),
    ]
    for code, name, atype in standard:
        Account.objects.get_or_create(
            code=code,
            defaults={
                'name': name,
                'account_type': atype,
                'opening_balance': 0,
                'current_balance': 0,
                'is_active': True,
            },
        )


def remove_standard_accounts(apps, schema_editor):
    Account = apps.get_model('accounts', 'Account')
    Account.objects.filter(code__in=['1140', '4101']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0004_salesinvoice_approved_at_salesinvoice_approved_by'),
        ('accounts', '0001_initial_squashed_0007_alter_journalentryline_options_and_more'),
    ]

    operations = [
        migrations.RunPython(create_standard_accounts, remove_standard_accounts),
    ]
