import frappe
from frappe.model.document import Document

class ClicknPaySettings(Document):
    def validate_transaction_currency(self, currency):
        pass
    
    def validate_transaction_amount(self, currency, amount=None):
        # ERPNext sometimes passes amount as 2nd arg, sometimes as 1st
        if amount is None and currency is not None:
            try:
                # if currency is actually amount
                float(currency)
                amount = currency
            except:
                pass
        if not amount:
            return
        if float(amount) <= 0:
            frappe.throw("Amount must be > 0")

    def get_payment_url(self, **kwargs):
        """
        Handles both:
        - CyteERP: Payment Request ACC-PRQ-2026-00008 -> ACC-SINV-2026-00026
        - Direct Invoice pay: ACC-SINV-2026-00026
        """
        from clicknpay_integration.api import initiate_payment
        
        # ERPNext can send many keys - handle all
        pr_name = kwargs.get("payment_request") or kwargs.get("name") or kwargs.get("payment_request_name")
        reference = kwargs.get("reference") or kwargs.get("reference_docname") or kwargs.get("reference_name") or kwargs.get("invoice_name")
        
        # If reference is actually a PRQ, resolve it
        if reference and frappe.db.exists("Payment Request", reference):
            pr_name = reference
            try:
                pr = frappe.get_doc("Payment Request", reference)
                reference = pr.reference_name
            except Exception:
                pass

        # If reference still empty, fetch from PR doc
        if not reference and pr_name and frappe.db.exists("Payment Request", pr_name):
            try:
                pr = frappe.get_doc("Payment Request", pr_name)
                reference = pr.reference_name
            except Exception as e:
                frappe.log_error(f"get_payment_url fetch PR failed: {e}", "ClicknPay")

        if not reference:
            frappe.throw(f"Cannot resolve Sales Invoice for Payment Request {pr_name}")

        # THIS IS THE FIX - pass both and let api.py handle it
        result = initiate_payment(
            reference=reference, 
            payment_request=pr_name,
            **kwargs
        )
        
        if result.get("status") == "success":
            url = result.get("redirect_url") or result.get("payment_url")
            # save url back to PRQ so your print format shows it
            if pr_name and url:
                try:
                    frappe.db.set_value("Payment Request", pr_name, "payment_url", url)
                except Exception:
                    pass
            return url
        
        frappe.throw(f"ClicknPay failed: {result.get('raw') or result.get('message')}")
