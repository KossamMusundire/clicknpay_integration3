import frappe
def trigger_fiscalisation(payment_entry_name, invoice_name):
    frappe.log_error(title="ZIMRA Triggered by ClicknPay", message=f"PE:{payment_entry_name} INV:{invoice_name}")
    # Your marketplace app auto hooks on Payment Entry on_submit
    # If it doesn't, uncomment and put correct path:
    # frappe.get_doc("Payment Entry", payment_entry_name)
    # from your_zimra_app.api import fiscalise_invoice
    # fiscalise_invoice(invoice_name)