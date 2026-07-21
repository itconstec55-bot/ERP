| التطبيق (App) | الشاشة/الدالة (View) | مستوى الوصول / الصلاحية المطلوبة |
|---|---|---|
| `accounts` | `account_list` | صلاحية: 'accounts.view_account' |
| `accounts` | `account_create` | دخول فقط (مصادقة) |
| `accounts` | `account_detail` | دخول فقط (مصادقة) |
| `accounts` | `account_edit` | دخول فقط (مصادقة) |
| `accounts` | `account_statement` | دخول فقط (مصادقة) |
| `accounts` | `journal_list` | صلاحية: 'accounts.view_journalentry' |
| `accounts` | `journal_create` | صلاحية: 'accounts.add_journalentry' |
| `accounts` | `journal_detail` | دخول فقط (مصادقة) |
| `accounts` | `journal_post` | دخول فقط (مصادقة) |
| `accounts` | `trial_balance` | دخول فقط (مصادقة) |
| `accounts` | `chart_of_accounts` | دخول فقط (مصادقة) |
| `accounts` | `export_accounts` | دخول فقط (مصادقة) |
| `accounts` | `import_accounts` | دخول فقط (مصادقة) |
| `accounts` | `export_journal` | دخول فقط (مصادقة) |
| `accounts` | `fiscal_year_close` | دخول فقط (مصادقة) |
| `ai_analysis` | `dashboard` | دخول فقط (مصادقة) |
| `ai_analysis` | `analyze_error` | دخول فقط (مصادقة) |
| `ai_analysis` | `auto_detect` | دخول فقط (مصادقة) |
| `ai_analysis` | `error_history` | دخول فقط (مصادقة) |
| `ai_analysis` | `error_detail` | دخول فقط (مصادقة) |
| `ai_analysis` | `apply_solution` | قيد طريقة HTTP: require_POST |
| `ai_analysis` | `api_detect_errors` | قيد طريقة HTTP: require_POST |
| `ai_analysis` | `api_analyze_error` | قيد طريقة HTTP: require_POST |
| `ai_analysis` | `api_error_stats` | دخول فقط (مصادقة) |
| `assets` | `asset_list` | دخول فقط (مصادقة) |
| `assets` | `asset_create` | دخول فقط (مصادقة) |
| `assets` | `asset_detail` | دخول فقط (مصادقة) |
| `assets` | `asset_edit` | دخول فقط (مصادقة) |
| `assets` | `depreciation_create` | دخول فقط (مصادقة) |
| `assets` | `asset_category_list` | دخول فقط (مصادقة) |
| `assets` | `asset_category_create` | دخول فقط (مصادقة) |
| `assets` | `export_assets` | دخول فقط (مصادقة) |
| `assets` | `import_assets` | دخول فقط (مصادقة) |
| `audit` | `audit_log_list` | دخول فقط (مصادقة) |
| `backups` | `_ensure_backup_dir` | — (عام/بلا قيد) |
| `backups` | `_format_size` | — (عام/بلا قيد) |
| `backups` | `_safe_extract_zip` | — (عام/بلا قيد) |
| `backups` | `backup_dashboard` | دخول فقط (مصادقة) |
| `backups` | `create_backup` | قيد طريقة HTTP: require_POST |
| `backups` | `download_backup` | دخول فقط (مصادقة) |
| `backups` | `delete_backup` | قيد طريقة HTTP: require_POST |
| `backups` | `restore_backup` | دخول فقط (مصادقة) |
| `backups` | `export_json` | دخول فقط (مصادقة) |
| `backups` | `import_json` | دخول فقط (مصادقة) |
| `backups` | `backup_settings_view` | دخول فقط (مصادقة) |
| `bank_reconciliation` | `reconciliation_dashboard` | دخول فقط (مصادقة) |
| `bank_reconciliation` | `session_create` | دخول فقط (مصادقة) |
| `bank_reconciliation` | `session_detail` | دخول فقط (مصادقة) |
| `bank_reconciliation` | `item_list` | دخول فقط (مصادقة) |
| `bank_reconciliation` | `item_create` | دخول فقط (مصادقة) |
| `bank_reconciliation` | `item_match` | دخول فقط (مصادقة) |
| `bank_reconciliation` | `import_csv` | دخول فقط (مصادقة) |
| `bank_reconciliation` | `auto_match` | دخول فقط (مصادقة) |
| `bank_reconciliation` | `item_delete` | قيد طريقة HTTP: require_POST |
| `budget` | `cost_center_list` | دخول فقط (مصادقة) |
| `budget` | `cost_center_create` | دخول فقط (مصادقة) |
| `budget` | `budget_list` | دخول فقط (مصادقة) |
| `budget` | `budget_create` | دخول فقط (مصادقة) |
| `cheques` | `cheque_list` | دخول فقط (مصادقة) |
| `cheques` | `cheque_create` | دخول فقط (مصادقة) |
| `cheques` | `cheque_detail` | دخول فقط (مصادقة) |
| `cheques` | `cheque_update_status` | قيد طريقة HTTP: require_POST |
| `cheques` | `cheque_delete` | قيد طريقة HTTP: require_POST |
| `cheques` | `cheque_dashboard` | دخول فقط (مصادقة) |
| `common` | `whatsapp_webhook` | قيد طريقة HTTP: require_http_methods |
| `company` | `company_settings` | دخول فقط (مصادقة) |
| `company` | `branch_create` | دخول فقط (مصادقة) |
| `company` | `branch_edit` | دخول فقط (مصادقة) |
| `company` | `branch_delete` | قيد طريقة HTTP: require_POST |
| `company` | `admin_settings_dashboard` | صلاحية: 'accounts.change_accounttype', raise_exception=True |
| `company` | `account_type_create` | قيد طريقة HTTP: require_http_methods |
| `company` | `account_type_update` | قيد طريقة HTTP: require_http_methods |
| `company` | `account_type_delete` | قيد طريقة HTTP: require_http_methods |
| `company` | `product_create` | قيد طريقة HTTP: require_http_methods |
| `company` | `product_update` | قيد طريقة HTTP: require_http_methods |
| `company` | `product_delete` | قيد طريقة HTTP: require_http_methods |
| `company` | `category_create` | قيد طريقة HTTP: require_http_methods |
| `company` | `category_update` | قيد طريقة HTTP: require_http_methods |
| `company` | `category_delete` | قيد طريقة HTTP: require_http_methods |
| `company` | `unit_create` | قيد طريقة HTTP: require_http_methods |
| `company` | `unit_update` | قيد طريقة HTTP: require_http_methods |
| `company` | `unit_delete` | قيد طريقة HTTP: require_http_methods |
| `credit_notes` | `credit_note_list` | دخول فقط (مصادقة) |
| `credit_notes` | `credit_note_create` | دخول فقط (مصادقة) |
| `credit_notes` | `credit_note_detail` | دخول فقط (مصادقة) |
| `credit_notes` | `credit_note_post` | قيد طريقة HTTP: require_POST |
| `credit_notes` | `credit_note_delete` | قيد طريقة HTTP: require_POST |
| `currency` | `currency_list` | دخول فقط (مصادقة) |
| `currency` | `currency_create` | دخول فقط (مصادقة) |
| `currency` | `currency_edit` | دخول فقط (مصادقة) |
| `currency` | `exchange_rate_history` | دخول فقط (مصادقة) |
| `documents` | `document_type_list` | دخول فقط (مصادقة) |
| `documents` | `document_type_create` | دخول فقط (مصادقة) |
| `documents` | `document_type_edit` | دخول فقط (مصادقة) |
| `documents` | `document_template_list` | دخول فقط (مصادقة) |
| `documents` | `document_template_create` | دخول فقط (مصادقة) |
| `documents` | `document_template_edit` | دخول فقط (مصادقة) |
| `documents` | `document_list` | دخول فقط (مصادقة) |
| `documents` | `document_create` | دخول فقط (مصادقة) |
| `documents` | `document_detail` | دخول فقط (مصادقة) |
| `documents` | `document_edit` | دخول فقط (مصادقة) |
| `documents` | `document_action` | دخول فقط (مصادقة) |
| `documents` | `document_add_attachment` | دخول فقط (مصادقة) |
| `hr` | `employee_list` | صلاحية: 'hr.view_employee' |
| `hr` | `employee_create` | صلاحية: 'hr.add_employee' |
| `hr` | `employee_detail` | صلاحية: 'hr.view_employee' |
| `hr` | `employee_edit` | صلاحية: 'hr.change_employee' |
| `hr` | `attendance_list` | صلاحية: 'hr.view_attendance' |
| `hr` | `attendance_create` | صلاحية: 'hr.add_attendance' |
| `hr` | `salary_list` | صلاحية: 'hr.view_salary' |
| `hr` | `salary_create` | صلاحية: 'hr.add_salary' |
| `hr` | `salary_post` | قيد طريقة HTTP: require_POST |
| `hr` | `department_list` | صلاحية: 'hr.view_department' |
| `hr` | `department_create` | صلاحية: 'hr.add_department' |
| `hr` | `export_employees` | صلاحية: 'hr.view_employee' |
| `hr` | `export_salaries` | صلاحية: 'hr.export_salary' |
| `hr` | `import_employees` | صلاحية: 'hr.add_employee' |
| `notifications` | `notification_dashboard` | دخول فقط (مصادقة) |
| `notifications` | `template_list` | دخول فقط (مصادقة) |
| `notifications` | `template_create` | دخول فقط (مصادقة) |
| `notifications` | `send_test_notification` | دخول فقط (مصادقة) |
| `payment_receipts` | `receipt_list` | صلاحية: 'treasury.view_bank' |
| `payment_receipts` | `receipt_create` | دخول فقط (مصادقة) |
| `payment_receipts` | `receipt_detail` | دخول فقط (مصادقة) |
| `payment_receipts` | `receipt_post` | قيد طريقة HTTP: require_POST |
| `payment_receipts` | `receipt_delete` | قيد طريقة HTTP: require_POST |
| `payment_receipts` | `receipt_print` | دخول فقط (مصادقة) |
| `payment_receipts` | `get_customer_invoices` | دخول فقط (مصادقة) |
| `payment_receipts` | `get_supplier_invoices` | دخول فقط (مصادقة) |
| `purchases` | `supplier_list` | صلاحية: 'purchases.view_supplier' |
| `purchases` | `supplier_create` | صلاحية: 'purchases.add_supplier' |
| `purchases` | `supplier_detail` | صلاحية: 'purchases.view_supplier' |
| `purchases` | `supplier_edit` | صلاحية: 'purchases.change_supplier' |
| `purchases` | `product_list` | دخول فقط (مصادقة) |
| `purchases` | `product_create` | دخول فقط (مصادقة) |
| `purchases` | `product_edit` | دخول فقط (مصادقة) |
| `purchases` | `catalog_settings` | دخول فقط (مصادقة) |
| `purchases` | `purchase_invoice_list` | دخول فقط (مصادقة) |
| `purchases` | `purchase_invoice_create` | دخول فقط (مصادقة) |
| `purchases` | `purchase_invoice_detail` | دخول فقط (مصادقة) |
| `purchases` | `purchase_invoice_post` | قيد طريقة HTTP: require_POST |
| `purchases` | `purchase_invoice_print` | دخول فقط (مصادقة) |
| `purchases` | `purchase_invoice_whatsapp` | قيد طريقة HTTP: require_POST |
| `purchases` | `supplier_statement_whatsapp` | قيد طريقة HTTP: require_POST |
| `purchases` | `export_suppliers` | دخول فقط (مصادقة) |
| `purchases` | `import_suppliers` | دخول فقط (مصادقة) |
| `purchases` | `export_products` | دخول فقط (مصادقة) |
| `purchases` | `import_products` | دخول فقط (مصادقة) |
| `purchases` | `product_barcode_print` | دخول فقط (مصادقة) |
| `purchases` | `product_barcode_batch` | دخول فقط (مصادقة) |
| `purchases` | `product_price_list` | دخول فقط (مصادقة) |
| `purchase_returns` | `purchase_return_list` | صلاحية: 'purchases.view_purchaseinvoice' |
| `purchase_returns` | `purchase_return_create` | دخول فقط (مصادقة) |
| `purchase_returns` | `purchase_return_detail` | دخول فقط (مصادقة) |
| `purchase_returns` | `purchase_return_post` | قيد طريقة HTTP: require_POST |
| `purchase_returns` | `purchase_return_delete` | قيد طريقة HTTP: require_POST |
| `recurring` | `recurring_list` | دخول فقط (مصادقة) |
| `recurring` | `recurring_create` | دخول فقط (مصادقة) |
| `recurring` | `recurring_edit` | دخول فقط (مصادقة) |
| `recurring` | `recurring_execute` | دخول فقط (مصادقة) |
| `recurring` | `recurring_toggle` | دخول فقط (مصادقة) |
| `recurring` | `recurring_delete` | دخول فقط (مصادقة) |
| `recurring` | `_save_lines` | — (عام/بلا قيد) |
| `reports` | `_safe_parse_date` | — (عام/بلا قيد) |
| `reports` | `_validate_date_range` | — (عام/بلا قيد) |
| `reports` | `_get_date_range` | — (عام/بلا قيد) |
| `reports` | `dashboard_view` | دخول فقط (مصادقة) |
| `reports` | `financial_dashboard` | صلاحية: 'reports.view_reporttemplate' |
| `reports` | `_age_bucket` | — (عام/بلا قيد) |
| `reports` | `workflow_tracker` | صلاحية: 'reports.view_reporttemplate' |
| `reports` | `report_list` | دخول فقط (مصادقة) |
| `reports` | `income_statement` | دخول فقط (مصادقة) |
| `reports` | `balance_sheet` | دخول فقط (مصادقة) |
| `reports` | `trial_balance_report` | دخول فقط (مصادقة) |
| `reports` | `vat_return` | دخول فقط (مصادقة) |
| `reports` | `withholding_tax_report` | دخول فقط (مصادقة) |
| `reports` | `supplier_report` | دخول فقط (مصادقة) |
| `reports` | `supplier_detail_report` | دخول فقط (مصادقة) |
| `reports` | `customer_report` | دخول فقط (مصادقة) |
| `reports` | `customer_detail_report` | دخول فقط (مصادقة) |
| `reports` | `profit_margin_report` | دخول فقط (مصادقة) |
| `reports` | `asset_schedule` | دخول فقط (مصادقة) |
| `reports` | `payroll_report` | دخول فقط (مصادقة) |
| `reports` | `export_report` | دخول فقط (مصادقة) |
| `reports` | `_export_simple_xlsx` | — (عام/بلا قيد) |
| `reports` | `__init__` | — (عام/بلا قيد) |
| `reports` | `__getattr__` | — (عام/بلا قيد) |
| `reports` | `_export_daily_sales` | — (عام/بلا قيد) |
| `reports` | `_export_daily_purchases` | — (عام/بلا قيد) |
| `reports` | `_export_ar_aging` | — (عام/بلا قيد) |
| `reports` | `_export_ap_aging` | — (عام/بلا قيد) |
| `reports` | `_export_income_statement` | — (عام/بلا قيد) |
| `reports` | `_export_balance_sheet` | — (عام/بلا قيد) |
| `reports` | `_export_vat_return` | — (عام/بلا قيد) |
| `reports` | `_export_payroll` | — (عام/بلا قيد) |
| `reports` | `_export_inventory` | — (عام/بلا قيد) |
| `reports` | `_export_profit_margin` | — (عام/بلا قيد) |
| `reports` | `_export_withholding_tax` | — (عام/بلا قيد) |
| `reports` | `_export_supplier_report` | — (عام/بلا قيد) |
| `reports` | `_export_customer_report` | — (عام/بلا قيد) |
| `reports` | `_export_customer_statement` | — (عام/بلا قيد) |
| `reports` | `_export_supplier_statement` | — (عام/بلا قيد) |
| `reports` | `_export_trial_balance` | — (عام/بلا قيد) |
| `reports` | `_export_asset_schedule` | — (عام/بلا قيد) |
| `reports` | `_export_cash_flow` | — (عام/بلا قيد) |
| `reports` | `ar_aging_report` | دخول فقط (مصادقة) |
| `reports` | `ap_aging_report` | دخول فقط (مصادقة) |
| `reports` | `inventory_report` | دخول فقط (مصادقة) |
| `reports` | `customer_statement` | دخول فقط (مصادقة) |
| `reports` | `supplier_statement` | دخول فقط (مصادقة) |
| `reports` | `daily_sales_report` | دخول فقط (مصادقة) |
| `reports` | `daily_purchases_report` | دخول فقط (مصادقة) |
| `reports` | `cash_flow_report` | دخول فقط (مصادقة) |
| `sales` | `customer_list` | صلاحية: 'sales.view_customer' |
| `sales` | `customer_create` | صلاحية: 'sales.add_customer' |
| `sales` | `customer_detail` | صلاحية: 'sales.view_customer' |
| `sales` | `customer_edit` | صلاحية: 'sales.change_customer' |
| `sales` | `sales_invoice_list` | صلاحية: 'sales.view_salesinvoice' |
| `sales` | `sales_invoice_create` | صلاحية: 'sales.add_salesinvoice' |
| `sales` | `sales_invoice_detail` | دخول فقط (مصادقة) |
| `sales` | `sales_invoice_post` | قيد طريقة HTTP: require_POST |
| `sales` | `sales_invoice_print` | دخول فقط (مصادقة) |
| `sales` | `sales_invoice_whatsapp` | قيد طريقة HTTP: require_POST |
| `sales` | `customer_statement_whatsapp` | قيد طريقة HTTP: require_POST |
| `sales` | `export_customers` | دخول فقط (مصادقة) |
| `sales` | `import_customers` | دخول فقط (مصادقة) |
| `sales_returns` | `sales_return_list` | صلاحية: 'sales.view_salesinvoice' |
| `sales_returns` | `sales_return_create` | دخول فقط (مصادقة) |
| `sales_returns` | `sales_return_detail` | دخول فقط (مصادقة) |
| `sales_returns` | `sales_return_post` | قيد طريقة HTTP: require_POST |
| `sales_returns` | `sales_return_delete` | قيد طريقة HTTP: require_POST |
| `stock_adjustments` | `adjustment_list` | دخول فقط (مصادقة) |
| `stock_adjustments` | `adjustment_create` | دخول فقط (مصادقة) |
| `stock_adjustments` | `adjustment_detail` | دخول فقط (مصادقة) |
| `stock_adjustments` | `adjustment_approve` | قيد طريقة HTTP: require_POST |
| `stock_adjustments` | `adjustment_delete` | قيد طريقة HTTP: require_POST |
| `sync` | `_get_or_create_machine` | — (عام/بلا قيد) |
| `sync` | `_verify_api_key` | — (عام/بلا قيد) |
| `sync` | `sync_dashboard` | دخول فقط (مصادقة) |
| `sync` | `sync_settings_view` | دخول فقط (مصادقة) |
| `sync` | `test_connection` | دخول فقط (مصادقة) |
| `sync` | `manual_sync` | دخول فقط (مصادقة) |
| `sync` | `sync_log_detail` | دخول فقط (مصادقة) |
| `sync` | `api_push` | قيد طريقة HTTP: require_http_methods |
| `sync` | `api_pull` | قيد طريقة HTTP: require_http_methods |
| `sync` | `api_status` | قيد طريقة HTTP: require_http_methods |
| `sync` | `api_recalculate` | قيد طريقة HTTP: require_http_methods |
| `treasury` | `bank_list` | صلاحية: 'treasury.view_bank' |
| `treasury` | `bank_create` | صلاحية: 'treasury.add_bank' |
| `treasury` | `bank_detail` | صلاحية: 'treasury.view_bank' |
| `treasury` | `bank_transaction_create` | صلاحية: 'treasury.add_banktransaction' |
| `treasury` | `safe_list` | صلاحية: 'treasury.view_safe' |
| `treasury` | `safe_create` | صلاحية: 'treasury.add_safe' |
| `treasury` | `safe_detail` | صلاحية: 'treasury.view_safe' |
| `treasury` | `safe_transaction_create` | صلاحية: 'treasury.add_safetransaction' |
| `treasury` | `export_banks` | صلاحية: 'treasury.view_bank' |
| `treasury` | `export_safes` | صلاحية: 'treasury.view_safe' |
| `treasury` | `import_banks` | صلاحية: 'treasury.add_bank' |
| `treasury` | `import_safes` | صلاحية: 'treasury.add_safe' |
| `users` | `clean_password2` | — (عام/بلا قيد) |
| `users` | `save` | — (عام/بلا قيد) |
| `users` | `user_list` | دخول فقط (مصادقة) |
| `users` | `user_create` | دخول فقط (مصادقة) |
| `users` | `user_edit` | دخول فقط (مصادقة) |
| `users` | `user_delete` | قيد طريقة HTTP: require_POST |
| `users` | `group_list` | دخول فقط (مصادقة) |
| `users` | `group_create` | دخول فقط (مصادقة) |
| `users` | `group_edit` | دخول فقط (مصادقة) |
| `users` | `group_delete` | قيد طريقة HTTP: require_POST |
| `users` | `change_password` | دخول فقط (مصادقة) |
| `warehouses` | `warehouse_list` | صلاحية: 'warehouses.view_warehouse' |
| `warehouses` | `warehouse_create` | صلاحية: 'warehouses.add_warehouse' |
| `warehouses` | `warehouse_edit` | صلاحية: 'warehouses.change_warehouse' |
| `warehouses` | `warehouse_detail` | صلاحية: 'warehouses.view_warehouse' |
| `warehouses` | `warehouse_product_add` | صلاحية: 'warehouses.add_warehouseproduct' |
| `warehouses` | `movement_list` | صلاحية: 'warehouses.view_stockmovement' |
| `warehouses` | `movement_create` | صلاحية: 'warehouses.add_stockmovement' |
| `warehouses` | `movement_detail` | صلاحية: 'warehouses.view_stockmovement' |
| `concrete_production` | `dashboard` | صلاحية: 'concrete_production.view_concretemixdesign' |
| `concrete_production` | `mix_design_list` | صلاحية: 'concrete_production.view_concretemixdesign' |
| `concrete_production` | `mix_design_create` | صلاحية: 'concrete_production.add_concretemixdesign' |
| `concrete_production` | `mix_design_detail` | صلاحية: 'concrete_production.view_concretemixdesign' |
| `concrete_production` | `mix_design_edit` | صلاحية: 'concrete_production.change_concretemixdesign' |
| `concrete_production` | `customer_request_list` | صلاحية: 'concrete_production.view_customerrequest' |
| `concrete_production` | `customer_request_create` | صلاحية: 'concrete_production.add_customerrequest' |
| `concrete_production` | `customer_request_detail` | صلاحية: 'concrete_production.view_customerrequest' |
| `concrete_production` | `customer_request_confirm` | صلاحية: 'concrete_production.change_customerrequest' |
| `concrete_production` | `production_cost_per_m3` | صلاحية: 'concrete_production.view_productionorder' |
| `concrete_production` | `production_order_list` | صلاحية: 'concrete_production.view_productionorder' |
| `concrete_production` | `production_order_create` | صلاحية: 'concrete_production.add_productionorder' |
| `concrete_production` | `production_order_detail` | صلاحية: 'concrete_production.view_productionorder' |
| `concrete_production` | `production_order_schedule` | صلاحية: 'concrete_production.change_productionorder' |
| `concrete_production` | `batch_list` | صلاحية: 'concrete_production.view_productionbatch' |
| `concrete_production` | `production_daily` | صلاحية: 'concrete_production.view_productionorder' |
| `concrete_production` | `batch_create` | صلاحية: 'concrete_production.add_productionbatch' |
| `concrete_production` | `batch_detail` | صلاحية: 'concrete_production.view_productionbatch' |
| `concrete_production` | `batch_update_status` | صلاحية: 'concrete_production.change_productionbatch' |
| `concrete_production` | `truck_list` | صلاحية: 'concrete_production.view_truck' |
| `concrete_production` | `truck_create` | صلاحية: 'concrete_production.add_truck' |
| `concrete_production` | `truck_edit` | صلاحية: 'concrete_production.change_truck' |
| `concrete_production` | `delivery_list` | صلاحية: 'concrete_production.view_deliveryschedule' |
| `concrete_production` | `delivery_create` | صلاحية: 'concrete_production.add_deliveryschedule' |
| `concrete_production` | `cost_list` | صلاحية: 'concrete_production.view_productioncost' |
| `concrete_production` | `cost_create` | صلاحية: 'concrete_production.add_productioncost' |
| `concrete_production` | `api_mix_components` | صلاحية: 'concrete_production.view_concretemixdesign' |
| `concrete_production` | `api_available_trucks` | صلاحية: 'concrete_production.view_truck' |
| `concrete_production` | `api_production_stats` | صلاحية: 'concrete_production.view_productionorder' |
| `concrete_production` | `silo_dashboard` | صلاحية: 'concrete_production.view_silo' |
| `concrete_production` | `cement_daily_inventory` | صلاحية: 'concrete_production.view_silotransaction' |
| `concrete_production` | `silo_list` | صلاحية: 'concrete_production.view_silo' |
| `concrete_production` | `silo_detail` | صلاحية: 'concrete_production.view_silo' |
| `concrete_production` | `silo_create` | صلاحية: 'concrete_production.add_silo' |
| `concrete_production` | `silo_edit` | صلاحية: 'concrete_production.change_silo' |
| `concrete_production` | `silo_transaction_create` | صلاحية: 'concrete_production.add_silotransaction' |
| `concrete_production` | `api_silo_stock` | صلاحية: 'concrete_production.view_silo' |
| `contractors` | `dashboard` | صلاحية: 'contractors.view_contractor' |
| `contractors` | `contractor_list` | صلاحية: 'contractors.view_contractor' |
| `contractors` | `contractor_create` | صلاحية: 'contractors.add_contractor' |
| `contractors` | `contractor_detail` | صلاحية: 'contractors.view_contractor' |
| `contractors` | `contractor_edit` | صلاحية: 'contractors.change_contractor' |
| `contractors` | `contract_list` | صلاحية: 'contractors.view_contract' |
| `contractors` | `contract_create` | صلاحية: 'contractors.add_contract' |
| `contractors` | `contract_detail` | صلاحية: 'contractors.view_contract' |
| `contractors` | `contract_edit` | صلاحية: 'contractors.change_contract' |
| `contractors` | `contract_approve` | صلاحية: 'contractors.change_contract' |
| `contractors` | `contract_close` | صلاحية: 'contractors.change_contract' |
| `contractors` | `certificate_list` | صلاحية: 'contractors.view_interimcertificate' |
| `contractors` | `certificate_create` | صلاحية: 'contractors.add_interimcertificate' |
| `contractors` | `certificate_detail` | صلاحية: 'contractors.view_interimcertificate' |
| `contractors` | `certificate_approve` | صلاحية: 'contractors.change_interimcertificate' |
| `contractors` | `certificate_post` | صلاحية: 'contractors.change_interimcertificate' |
| `contractors` | `payment_list` | صلاحية: 'contractors.view_contractorpayment' |
| `contractors` | `payment_create` | صلاحية: 'contractors.add_contractorpayment' |
| `contractors` | `payment_detail` | صلاحية: 'contractors.view_contractorpayment' |
| `contractors` | `payment_post` | صلاحية: 'contractors.change_contractorpayment' |
| `contractors` | `api_contract_items` | صلاحية: 'contractors.view_contract' |
| `contractors` | `api_contractor_stats` | صلاحية: 'contractors.view_contractor' |