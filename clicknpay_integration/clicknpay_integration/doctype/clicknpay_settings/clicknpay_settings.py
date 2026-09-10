import frappe
from frappe.model.document import Document

class ClicknPaySettings(Document):
    def validate_transaction_currency(self, currency):
        pass
    
    def validate_transaction_amount(self, currency, amount=None):
        if amount is None:
            amount = currency
        if not amount or float(amount) <= 0:
            frappe.throw("Amount must be > 0")

    def get_payment_url(self, **kwargs):
        """
        Handles both:
        - CyteERP: Payment Request -> kwargs has reference_name = ACC-SINV-...
        - GW Keys: Payment Request for Subscription invoice
        """
        from clicknpay_integration.api import initiate_payment
        
        pr_name = kwargs.get("name")  # This is ACC-PRQ-2026-00002
        reference = kwargs.get("reference_docname") or kwargs.get("reference_name")
        
        # If reference not in kwargs, fetch from PR doc
        if not reference and pr_name:
            try:
                if frappe.db.exists("Payment Request", pr_name):
                    pr = frappe.get_doc("Payment Request", pr_name)
                    reference = pr.reference_name  # Should be ACC-SINV-2026-00024
            except Exception as e:
                frappe.log_error(f"get_payment_url fetch PR failed: {e}", "ClicknPay")

        if not reference:
            frappe.throw(f"Cannot resolve Sales Invoice for Payment Request {pr_name}")

        # reference is now ACC-SINV-2026-00024, not ACC-PRQ-2026-00002
        result = initiate_payment(reference=reference, payment_request=pr_name)
        
        if result.get("status") == "success":
            return result.get("redirect_url")
        
        frappe.throw(f"ClicknPay failed: {result.get('message')}")
