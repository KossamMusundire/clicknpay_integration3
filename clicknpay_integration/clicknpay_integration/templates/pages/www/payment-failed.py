import frappe
def get_context(context):
    context.docname = frappe.form_dict.get("docname") or frappe.form_dict.get("invoice") or frappe.form_dict.get("clientReference")
    context.status = (frappe.form_dict.get("status") or "FAILED").upper()
    context.reason = frappe.form_dict.get("reason") or frappe.form_dict.get("message") or ""
    return context