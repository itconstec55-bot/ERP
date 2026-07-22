from django import forms
from django.forms import inlineformset_factory

from .models import (
    ConcreteMixDesign,
    CustomerRequest,
    DeliverySchedule,
    MixComponent,
    ProductionBatch,
    ProductionCost,
    ProductionOrder,
    Silo,
    SiloTransaction,
    Truck,
)


class ConcreteMixDesignForm(forms.ModelForm):
    class Meta:
        model = ConcreteMixDesign
        fields = [
            'code',
            'name',
            'strength_class',
            'slump_cm',
            'max_aggregate_mm',
            'water_cement_ratio',
            'target_strength_mpa',
            'description',
            'is_active',
            'selling_price_per_m3',
        ]


MixComponentFormSet = inlineformset_factory(
    ConcreteMixDesign,
    MixComponent,
    fields=['component_type', 'name', 'quantity_kg', 'product', 'order'],
    extra=3,
    can_delete=True,
    widgets={
        'component_type': forms.Select(attrs={'class': 'form-select'}),
        'name': forms.TextInput(attrs={'class': 'form-control'}),
        'quantity_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
        'product': forms.Select(attrs={'class': 'form-select'}),
        'order': forms.NumberInput(attrs={'class': 'form-control'}),
    },
)


class CustomerRequestForm(forms.ModelForm):
    class Meta:
        model = CustomerRequest
        fields = ['customer', 'project_name', 'site_address', 'contact_person', 'contact_phone', 'notes']
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'project_name': forms.TextInput(attrs={'class': 'form-control'}),
            'site_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ProductionOrderForm(forms.ModelForm):
    class Meta:
        model = ProductionOrder
        fields = [
            'customer_request',
            'mix_design',
            'quantity_m3',
            'priority',
            'scheduled_date',
            'scheduled_time_from',
            'scheduled_time_to',
            'pump_required',
            'pump_cost',
            'unit_price',
            'special_requirements',
            'notes',
        ]
        widgets = {
            'customer_request': forms.Select(attrs={'class': 'form-select'}),
            'mix_design': forms.Select(attrs={'class': 'form-select'}),
            'quantity_m3': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'scheduled_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'scheduled_time_from': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'scheduled_time_to': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'pump_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'special_requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ProductionOrderFilterForm(forms.Form):
    status = forms.ChoiceField(
        choices=[('', 'الكل')] + ProductionOrder.STATUS_CHOICES,
        required=False,
        label='الحالة',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    priority = forms.ChoiceField(
        choices=[('', 'الكل')] + ProductionOrder.PRIORITY_CHOICES,
        required=False,
        label='الأولوية',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    date_from = forms.DateField(
        required=False, label='من تاريخ', widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    date_to = forms.DateField(
        required=False, label='إلى تاريخ', widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )


class ProductionBatchForm(forms.ModelForm):
    class Meta:
        model = ProductionBatch
        fields = ['production_order', 'truck', 'quantity_m3', 'notes']
        widgets = {
            'production_order': forms.Select(attrs={'class': 'form-select'}),
            'truck': forms.Select(attrs={'class': 'form-select'}),
            'quantity_m3': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class DeliveryScheduleForm(forms.ModelForm):
    class Meta:
        model = DeliverySchedule
        fields = [
            'production_order',
            'batch',
            'delivery_date',
            'time_slot_from',
            'time_slot_to',
            'truck',
            'sequence',
            'notes',
        ]
        widgets = {
            'production_order': forms.Select(attrs={'class': 'form-select'}),
            'batch': forms.Select(attrs={'class': 'form-select'}),
            'delivery_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'time_slot_from': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'time_slot_to': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'truck': forms.Select(attrs={'class': 'form-select'}),
            'sequence': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class TruckForm(forms.ModelForm):
    class Meta:
        model = Truck
        fields = ['plate_number', 'driver_name', 'driver_phone', 'capacity_m3', 'status', 'is_active']
        widgets = {
            'plate_number': forms.TextInput(attrs={'class': 'form-control'}),
            'driver_name': forms.TextInput(attrs={'class': 'form-control'}),
            'driver_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity_m3': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProductionCostForm(forms.ModelForm):
    class Meta:
        model = ProductionCost
        fields = ['production_order', 'cost_type', 'amount', 'description', 'date']
        widgets = {
            'production_order': forms.Select(attrs={'class': 'form-select'}),
            'cost_type': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class BatchStatusUpdateForm(forms.Form):
    """تحديث حالة الدفعة الإنتاجية"""

    STATUS_CHOICES = [
        ('mixing', 'جاري الخلط'),
        ('loading', 'جاري التحميل'),
        ('in_transit', 'في الطريق'),
        ('pouring', 'جاري الصب'),
        ('completed', 'مكتمل'),
        ('returned', 'مرتجع'),
        ('cancelled', 'ملغي'),
    ]
    status = forms.ChoiceField(choices=STATUS_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    actual_quantity_m3 = forms.DecimalField(
        required=False,
        label='الكمية الفعلية (م³)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
    )
    returned_quantity_m3 = forms.DecimalField(
        required=False,
        label='الكمية المرتجعة (م³)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
    )
    notes = forms.CharField(
        required=False, label='ملاحظات', widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2})
    )


class SiloForm(forms.ModelForm):
    class Meta:
        model = Silo
        fields = [
            'code',
            'name',
            'capacity_tons',
            'current_stock_tons',
            'minimum_order_tons',
            'critical_level_tons',
            'location',
            'cement_type',
            'supplier',
            'is_active',
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity_tons': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'current_stock_tons': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'minimum_order_tons': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'critical_level_tons': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'cement_type': forms.TextInput(attrs={'class': 'form-control'}),
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SiloTransactionForm(forms.ModelForm):
    class Meta:
        model = SiloTransaction
        fields = ['transaction_type', 'quantity_tons', 'reference_number', 'notes']
        widgets = {
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'quantity_tons': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
