from django.apps import AppConfig


class ConcreteProductionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'concrete_production'
    verbose_name = 'إنتاج الخرسانة الجاهزة'
