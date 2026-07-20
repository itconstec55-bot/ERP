from django.urls import path
from . import views

app_name = 'ai_analysis'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('analyze/', views.analyze_error, name='analyze_error'),
    path('detect/', views.auto_detect, name='auto_detect'),
    path('history/', views.error_history, name='error_history'),
    path('error/<uuid:pk>/', views.error_detail, name='error_detail'),
    path('solution/<uuid:pk>/apply/', views.apply_solution, name='apply_solution'),
    path('api/detect/', views.api_detect_errors, name='api_detect_errors'),
    path('api/analyze/', views.api_analyze_error, name='api_analyze_error'),
    path('api/stats/', views.api_error_stats, name='api_error_stats'),
]
