from django import forms

from .models import BackupSettings


class BackupSettingsForm(forms.ModelForm):
    class Meta:
        model = BackupSettings
        fields = [
            'auto_backup_enabled',
            'backup_interval_hours',
            'max_backups',
            'backup_database',
            'backup_media',
            'backup_source',
        ]
        widgets = {
            'backup_interval_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'max_backups': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }
