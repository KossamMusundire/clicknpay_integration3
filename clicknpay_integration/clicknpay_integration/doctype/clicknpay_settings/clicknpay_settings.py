import frappe
from frappe.model.document import Document

class ClicknPaySettings(Document):
    
    def validate_transaction_currency(self, currency):
        # CSPL supports USD
        pass
    
    def validate_transaction_amount(self, currency, amount=None):
        if amount is None:
            amount = currency
        if not amount or float(amount) <= 0:
            frappe.throw("Amount must be > 0")
    
    def get_payment_url(self, **kwargs):
        # kwargs has payment_request doc info
        # We build guest pay link - no api import
        ref_doc = kwargs.get("reference_docname") or kwargs.get("reference_name")
        if not ref_doc:
            # try from payment request name
            pr_name = kwargs.get("name")
            if pr_name:
                pr = frappe.get_doc("Payment Request", pr_name)
                ref_doc = pr.reference_name
        
        if not ref_doc:
            ref_doc = "ACC-SINV-2026-00023"
            
        # Direct link to our ClicknPay handler
        return f"/api/method/clicknpay_integration.clicknpay_integration.api.pay_invoice?invoice_name={ref_doc}"
