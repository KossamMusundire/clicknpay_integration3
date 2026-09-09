import frappe
from frappe.model.document import Document

class ClicknPaySettings(Document):
    
    def validate_transaction_currency(self, currency):
        if currency not in ["USD", "ZWG", "ZiG", "ZAR","ZMW"]:
            frappe.throw(f"Currency {currency} not supported")
    
    def validate_transaction_amount(self, currency, amount=None):
        # ERPNext v16 calls with (currency, amount) or (amount)
        if amount is None:
            amount = currency
        if amount <= 0:
            frappe.throw("Amount must be > 0")
    
    def get_payment_url(self, **kwargs):
        from clicknpay_integration.clicknpay_integration.api import get_payment_url
        return get_payment_url(**kwargs)
