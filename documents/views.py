from django.contrib.auth.decorators import login_required
from common.permissions import screen_permission_required

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Count
from .models import DocumentType, DocumentTemplate, Document, DocumentFlow, DocumentAttachment
from .forms import (DocumentTypeForm, DocumentTemplateForm, DocumentForm,
                     DocumentFlowForm, DocumentAttachmentForm)


@screen_permission_required('documents.document', 'view')
def document_type_list(request):
    types = DocumentType.objects.all()
    return render(request, 'documents/document_type_list.html', {'types': types})


@screen_permission_required('documents.document', 'add')
def document_type_create(request):
    if request.method == 'POST':
        form = DocumentTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إنشاء نوع المستند بنجاح')
            return redirect('documents:document_type_list')
    else:
        form = DocumentTypeForm()
    return render(request, 'documents/document_type_form.html', {'form': form})


@screen_permission_required('documents.document', 'edit')
def document_type_edit(request, pk):
    doc_type = get_object_or_404(DocumentType, pk=pk)
    if request.method == 'POST':
        form = DocumentTypeForm(request.POST, instance=doc_type)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل نوع المستند بنجاح')
            return redirect('documents:document_type_list')
    else:
        form = DocumentTypeForm(instance=doc_type)
    return render(request, 'documents/document_type_form.html', {'form': form, 'object': doc_type})


@screen_permission_required('documents.document', 'view')
def document_template_list(request):
    templates = DocumentTemplate.objects.select_related('document_type').all()
    return render(request, 'documents/document_template_list.html', {'templates': templates})


@screen_permission_required('documents.document', 'add')
def document_template_create(request):
    if request.method == 'POST':
        form = DocumentTemplateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إنشاء القالب بنجاح')
            return redirect('documents:document_template_list')
    else:
        form = DocumentTemplateForm()
    return render(request, 'documents/document_template_form.html', {'form': form})


@screen_permission_required('documents.document', 'edit')
def document_template_edit(request, pk):
    template_obj = get_object_or_404(DocumentTemplate, pk=pk)
    if request.method == 'POST':
        form = DocumentTemplateForm(request.POST, instance=template_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل القالب بنجاح')
            return redirect('documents:document_template_list')
    else:
        form = DocumentTemplateForm(instance=template_obj)
    return render(request, 'documents/document_template_form.html', {'form': form, 'object': template_obj})


@screen_permission_required('documents.document', 'view')
def document_list(request):
    docs = Document.objects.select_related('document_type', 'department', 'created_by', 'assigned_to').all()
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')
    search = request.GET.get('q', '')
    if status_filter:
        docs = docs.filter(status=status_filter)
    if type_filter:
        docs = docs.filter(document_type_id=type_filter)
    if search:
        docs = docs.filter(Q(title__icontains=search) | Q(document_number__icontains=search))
    doc_types = DocumentType.objects.filter(is_active=True)
    status_counts = Document.objects.values('status').annotate(count=Count('id'))
    return render(request, 'documents/document_list.html', {
        'documents': docs,
        'doc_types': doc_types,
        'status_counts': {s['status']: s['count'] for s in status_counts},
        'current_status': status_filter,
        'current_type': type_filter,
        'search': search,
    })


@screen_permission_required('documents.document', 'add')
def document_create(request):
    if request.method == 'POST':
        form = DocumentForm(request.POST)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.created_by = request.user
            if not doc.document_number:
                doc.document_number = doc.document_type.generate_number()
            doc.save()
            DocumentFlow.objects.create(
                document=doc,
                action='create',
                to_status=doc.status,
                performed_by=request.user,
                comment='إنشاء المستند',
            )
            messages.success(request, 'تم إنشاء المستند بنجاح')
            return redirect('documents:document_detail', pk=doc.pk)
    else:
        form = DocumentForm()
    return render(request, 'documents/document_form.html', {'form': form})


@screen_permission_required('documents.document', 'view')
def document_detail(request, pk):
    doc = get_object_or_404(Document.objects.select_related(
        'document_type', 'department', 'created_by', 'assigned_to'), pk=pk)
    flows = doc.flows.select_related('performed_by').all()
    attachments = doc.attachments.select_related('uploaded_by').all()
    flow_form = DocumentFlowForm()
    attachment_form = DocumentAttachmentForm()
    return render(request, 'documents/document_detail.html', {
        'document': doc,
        'flows': flows,
        'attachments': attachments,
        'flow_form': flow_form,
        'attachment_form': attachment_form,
    })


@screen_permission_required('documents.document', 'edit')
def document_edit(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if request.method == 'POST':
        form = DocumentForm(request.POST, instance=doc)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل المستند بنجاح')
            return redirect('documents:document_detail', pk=doc.pk)
    else:
        form = DocumentForm(instance=doc)
    return render(request, 'documents/document_form.html', {'form': form, 'object': doc})


@screen_permission_required('documents.document', 'edit')
def document_action(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if request.method != 'POST':
        return redirect('documents:document_detail', pk=pk)
    action = request.POST.get('action', '')
    comment = request.POST.get('comment', '')
    old_status = doc.status
    if action == 'approve':
        doc.approve()
        new_status = 'approved'
    elif action == 'reject':
        doc.reject()
        new_status = 'rejected'
    elif action == 'archive':
        doc.archive()
        new_status = 'archived'
    elif action == 'cancel':
        doc.cancel()
        new_status = 'cancelled'
    elif action == 'submit':
        doc.status = 'pending'
        doc.save(update_fields=['status', 'updated_at'])
        new_status = 'pending'
    else:
        messages.error(request, 'إجراء غير صحيح')
        return redirect('documents:document_detail', pk=doc.pk)
    DocumentFlow.objects.create(
        document=doc,
        action=action,
        from_status=old_status,
        to_status=new_status,
        performed_by=request.user,
        comment=comment,
    )
    messages.success(request, f'تم {doc.get_action_display() if hasattr(doc, "get_action_display") else action} المستند بنجاح')
    return redirect('documents:document_detail', pk=doc.pk)


@screen_permission_required('documents.document', 'add')
def document_add_attachment(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if request.method == 'POST':
        form = DocumentAttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            attachment = form.save(commit=False)
            attachment.document = doc
            attachment.uploaded_by = request.user
            attachment.save()
            messages.success(request, 'تم رفع المرفق بنجاح')
    return redirect('documents:document_detail', pk=doc.pk)
