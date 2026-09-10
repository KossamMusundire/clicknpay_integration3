import frappe
from frappe.model.document import Document

class ClicknPaySettings(Document):
    def validate_transaction_currency(self, currency):
        pass
    
    def validate_transaction_amount(self, currency, amount=None):
        if amount is None: amount = currency
        if not amount or float(amount) <= 0:
            frappe.throw("Amount must be > 0")
    
    def get_payment_url(self, **kwargs):
        """
        Called by:
        1. CyteERP: Payment Request -> Submit
        2. GW Keys: Payment Request for Subscription invoice
        """
        from clicknpay_integration.api import initiate_payment, get_payment_url as api_get_url
        
        # CyteERP: kwargs has Payment Request name
        pr_name = kwargs.get("name")
        ref = kwargs.get("reference_docname") or kwargs.get("reference_name")
        
        if not ref and pr_name:
            try:
                pr = frappe.get_doc("Payment Request", pr_name)
                ref = pr.reference_name
            except:
                pass
        
        if not ref:
            ref = kwargs.get("clientReference") or "ACC-SINV-2026-00023"

        # This will create real ClicknPay order via your api.py
        result = initiate_payment(reference=ref)
        
        if result.get("status") == "success":
            url = result.get("redirect_url")
            # Save url to PR so portal shows it
            if pr_name:
                frappe.db.set_value("Payment Request", pr_name, "payment_url", url)
            return url
        
        # If fails, don't 500 - fallback to guest pay link
        frappe.log_error(f"ClicknPay failed for {ref}: {result}", "ClicknPay")
        return f"/api/method/clicknpay_integration.api.pay_invoice?invoice_name={ref}"
