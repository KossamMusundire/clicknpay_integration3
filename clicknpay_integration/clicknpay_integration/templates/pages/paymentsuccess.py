import frappe

def get_context(context):
    # FIX: Handle BOTH - ?doctype=Sales Invoice&docname=INV and ?invoice=INV
    doctype = frappe.form_dict.get("doctype")
    docname = frappe.form_dict.get("docname") or frappe.form_dict.get("invoice") or frappe.form_dict.get("clientReference")
    status = (frappe.form_dict.get("status") or frappe.form_dict.get("gateway_status") or "SUCCESS").upper()
    
    # Default to Sales Invoice if not provided
    if not doctype and docname:
        doctype = "Sales Invoice"
    
    context.status = status
    context.docname = docname
    context.doctype = doctype
    context.invoice = docname
    
    # Try get doc safely - NO CRASH
    context.doc = None
    context.paid = False
    context.customer_name = ""
    context.grand_total = 0
    
    try:
        if doctype and docname and frappe.db.exists(doctype, docname):
            doc = frappe.get_doc(doctype, docname)
            context.doc = doc
            if hasattr(doc, 'outstanding_amount'):
                context.paid = doc.outstanding_amount == 0
            if hasattr(doc, 'customer'):
                context.customer_name = doc.customer
            if hasattr(doc, 'grand_total'):
                context.grand_total = doc.grand_total
        # If status is SUCCESS, mark as paid even if doc fetch fails
        if status in ("SUCCESS","PAID","COMPLETED","APPROVED","TOP-PAID"):
            context.paid = True
    except Exception as e:
        frappe.log_error(f"payment_success get_context error {e}", "Payment Success")
        # Don't crash - show welcome anyway if gateway said SUCCESS
        if status in ("SUCCESS","PAID","COMPLETED"):
            context.paid = True
    
    return context