from django import forms

from .models import MachineInfo, SyncSettings


class MachineInfoForm(forms.ModelForm):
    class Meta:
        model = MachineInfo
        fields = ['name', 'machine_type']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'machine_type': forms.Select(attrs={'class': 'form-select'}),
        }


class SyncSettingsForm(forms.ModelForm):
    class Meta:
        model = SyncSettings
        fields = [
            'auto_sync_enabled',
            'sync_interval_minutes',
            'sync_on_startup',
            'host_address',
            'host_port',
            'sync_key',
        ]
        widgets = {
            'host_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '192.168.1.100'}),
            'host_port': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 65535}),
            'sync_key': forms.PasswordInput(
                attrs={'class': 'form-control', 'placeholder': 'مفتاح الربط'}, render_value=True
            ),
            'sync_interval_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }
