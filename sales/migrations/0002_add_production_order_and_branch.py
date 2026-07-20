import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0001_initial_squashed_0010_alter_customer_credit_limit_and_more'),
        ('company', '0002_company_cogs_account_company_customer_account_and_more'),
        ('concrete_production', '0004_concretemixdesign_product_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='salesinvoice',
            name='production_order',
            field=models.ForeignKey(blank=True, help_text='يرتبط تلقائياً عند إنشاء فاتورة من تسليم خرسانة', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sales_invoices', to='concrete_production.productionorder', verbose_name='أمر إنتاج الخرسانة'),
        ),
        migrations.AddField(
            model_name='salesinvoice',
            name='branch',
            field=models.ForeignKey(blank=True, help_text='يُستخدم للصلاحيات على مستوى الكائن', null=True, on_delete=django.db.models.deletion.SET_NULL, to='company.companybranch', verbose_name='الفرع'),
        ),
    ]
