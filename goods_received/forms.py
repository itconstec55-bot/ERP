from django import forms
from purchases.models import Supplier, Product
from purchase_orders.models import PurchaseOrder, PurchaseOrderLine
from warehouses.models import Warehouse
from .models import GoodsReceivedNote, GoodsReceivedLine


class GoodsReceivedNoteForm(forms.ModelForm):
    class Meta:
        model = GoodsReceivedNote
        fields = ['grn_number', 'purchase_order', 'warehouse', 'supplier', 'date', 'status', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'grn_number': forms.TextInput(attrs={'placeholder': 'يُولَّد تلقائياً عند الحفظ'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].queryset = Supplier.objects.filter(is_active=True)
        self.fields['purchase_order'].queryset = PurchaseOrder.objects.exclude(status='cancelled')
        self.fields['warehouse'].queryset = Warehouse.objects.filter(is_active=True)
        self.fields['grn_number'].required = False

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('warehouse'):
            raise forms.ValidationError('يجب تحديد المستودع')
        return cleaned_data


class GoodsReceivedLineForm(forms.ModelForm):
    class Meta:
        model = GoodsReceivedLine
        fields = ['purchase_order_line', 'product', 'quantity_received', 'unit_price', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
        self.fields['purchase_order_line'].queryset = PurchaseOrderLine.objects.select_related('order', 'product').all()
        self.fields['purchase_order_line'].required = False
        self.fields['purchase_order_line'].label = 'بند أمر الشراء (اختياري)'

    def clean_quantity_received(self):
        qty = self.cleaned_data.get('quantity_received', 0)
        if qty is None or qty <= 0:
            raise forms.ValidationError('الكمية المستلمة يجب أن تكون أكبر من صفر')
        return qty

    def clean_unit_price(self):
        price = self.cleaned_data.get('unit_price', 0)
        if price is None or price < 0:
            raise forms.ValidationError('السعر لا يمكن أن يكون سالباً')
        return price


GoodsReceivedLineFormSet = forms.inlineformset_factory(
    GoodsReceivedNote, GoodsReceivedLine,
    form=GoodsReceivedLineForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
