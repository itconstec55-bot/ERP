from django.contrib import admin
from .models import DocumentType, DocumentTemplate, Document, DocumentFlow, DocumentAttachment


class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'prefix', 'next_number', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')


class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'document_type', 'is_default', 'is_active')
    list_filter = ('document_type', 'is_active')
    search_fields = ('name',)


class DocumentFlowInline(admin.TabularInline):
    model = DocumentFlow
    extra = 0
    readonly_fields = ('action', 'from_status', 'to_status', 'performed_by', 'comment', 'created_at')
    can_delete = False


class DocumentAttachmentInline(admin.TabularInline):
    model = DocumentAttachment
    extra = 0
    readonly_fields = ('uploaded_by', 'uploaded_at')


class DocumentAdmin(admin.ModelAdmin):
    list_display = ('document_number', 'title', 'document_type', 'status', 'priority',
                    'department', 'date', 'due_date', 'created_by')
    list_filter = ('status', 'priority', 'document_type', 'department')
    search_fields = ('document_number', 'title')
    inlines = [DocumentFlowInline, DocumentAttachmentInline]
    readonly_fields = ('created_by',)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class DocumentFlowAdmin(admin.ModelAdmin):
    list_display = ('document', 'action', 'from_status', 'to_status', 'performed_by', 'created_at')
    list_filter = ('action',)
    search_fields = ('document__document_number',)


admin.site.register(DocumentType, DocumentTypeAdmin)
admin.site.register(DocumentTemplate, DocumentTemplateAdmin)
admin.site.register(Document, DocumentAdmin)
admin.site.register(DocumentFlow, DocumentFlowAdmin)
admin.site.register(DocumentAttachment)
