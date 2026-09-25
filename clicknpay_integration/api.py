import frappe
import requests
from frappe.utils import today, get_url, cint

CREATE_URL = "https://backendservices.clicknpay.africa:2081/payme/orders"
STATUS_URL = "https://backendservices.clicknpay.africa:2081/payme/orders/top-paid"

def get_settings():
    public_id = None
    try:
        mode = frappe.db.get_single_value("ClicknPay Settings", "mode") or "Test"
        if mode == "Live":
            public_id = frappe.db.get_single_value("ClicknPay Settings", "live_public_id")
        else:
            public_id = frappe.db.get_single_value("ClicknPay Settings", "test_public_id")
    except Exception:
        pass
    if not public_id:
        public_id = frappe.conf.get("clicknpay_public_id") or "HQGVaTYJihldpvzsw"
    return {
        "public_id": public_id,
        "create_url": frappe.conf.get("clicknpay_create_url") or CREATE_URL,
        "status_url": frappe.conf.get("clicknpay_status_url") or STATUS_URL,
    }

@frappe.whitelist(allow_guest=True)
def initiate_payment(reference=None, subscription=None, email=None, phone=None, plan_name=None, qty=1, description=None, return_url=None, currency=None, payment_request=None, invoice_name=None, **kwargs):
    """
    Works for both:
    - reference = ACC-SINV-2026-00026 (Invoice)
    - reference = ACC-PRQ-2026-00008 (Payment Request)
    - payment_request = ACC-PRQ-2026-00008 (from ClicknPay Settings.get_payment_url)
    """
    # Accept all possible names ERPNext might send
    reference = (reference or invoice_name or kwargs.get("reference_name") or kwargs.get("invoice_name") or "").strip()
    payment_request = (payment_request or kwargs.get("payment_request_name") or kwargs.get("pr_name") or "").strip()
    email = (email or kwargs.get("contact_email") or "").strip()
    phone = (phone or kwargs.get("contact_phone") or "").strip()
    qty = cint(qty or 1) or 1

    site_url = get_url()
    settings = get_settings()
    pr_doc = None
    inv_name = None

    # If reference is a Payment Request, resolve to invoice
    if reference and frappe.db.exists("Payment Request", reference):
        pr_doc = frappe.get_doc("Payment Request", reference)
        inv_name = pr_doc.reference_name
        payment_request = pr_doc.name
    elif payment_request and frappe.db.exists("Payment Request", payment_request):
        pr_doc = frappe.get_doc("Payment Request", payment_request)
        inv_name = pr_doc.reference_name or reference
        reference = inv_name

    # If still not invoice, check subscription
    if not inv_name and kwargs.get("subscription") and frappe.db.exists("Subscription", kwargs.get("subscription")):
        outs = frappe.get_all("Sales Invoice", filters={"subscription": kwargs.get("subscription"), "docstatus": 1, "outstanding_amount": [">", 0]}, limit=1, order_by="creation desc")
        if outs:
            inv_name = outs[0].name

    # Direct invoice
    if not inv_name and reference and frappe.db.exists("Sales Invoice", reference):
        inv_name = reference

    # Email search fallback
    search_email = email or (reference if "@" in reference else "")
    if not inv_name and search_email:
        inv = frappe.get_all("Sales Invoice", filters={"contact_email": search_email, "docstatus": ["!=", 2]}, limit=1, order_by="creation desc")
        if inv:
            inv_name = inv[0].name

    if not inv_name:
        frappe.throw(f"Invoice not found Ref: {reference} / PRQ: {payment_request}")

    inv_doc = frappe.get_doc("Sales Invoice", inv_name)
    curr = currency or inv_doc.currency or "USD"
    grand = float(inv_doc.grand_total or 0)

    if not return_url:
        return_url = f"{site_url}/api/method/clicknpay_integration.api.clicknpay_callback?clientReference={inv_name}"

    # --- BUILD PRODUCTS WITH TAX INCLUDED (FIX FOR YOUR 100 vs 115.50 BUG) ---
    products = []
    # Simplest & 100% accurate: send single product = grand_total
    # This guarantees gateway = invoice total incl. VAT
    # If you want itemized + tax lines, uncomment the block below
    products = [{
        "description": (description or f"Payment for {inv_name} - {inv_doc.customer}")[:100],
        "id": 1,
        "price": grand,
        "productName": inv_name[:50],
        "quantity": 1
    }]

    """
    # ALTERNATIVE - itemized with tax lines (use if ClicknPay needs breakdown):
    total = 0
    for idx, i in enumerate(inv_doc.items):
        products.append({
            "description": (i.description or i.item_name or "")[:100],
            "id": idx+1,
            "price": float(i.rate or 0),
            "productName": (i.item_code or "ITEM")[:50],
            "quantity": int(i.qty or 1)
        })
        total += float(i.rate or 0) * int(i.qty or 1)
    for t_idx, t in enumerate(inv_doc.taxes):
        if float(t.tax_amount or 0)!= 0:
            products.append({
                "description": (t.description or "Tax")[:100],
                "id": len(products)+1,
                "price": float(t.tax_amount),
                "productName": f"TAX-{t_idx+1}",
                "quantity": 1
            })
            total += float(t.tax_amount)
    if abs(total - grand) > 0.01:
        products = [{"description": f"Payment for {inv_name}", "id": 1, "price": grand, "productName": inv_name, "quantity": 1}]
    """

    payload = {
        "channel": "AUTOMATED",
        "clientReference": inv_name,
        "currency": curr,
        "customerCharged": True,
        "customerPhoneNumber": (phone.replace(" ", "") or "263771234567")[:15],
        "description": (description or f"Payment x1 - {inv_name}")[:200],
        "multiplePayments": False,
        "orderYpe": "DYNAMIC",
        "productsList": products,
        "publicUniqueId": settings["public_id"],
        "returnUrl": return_url
    }

    resp = requests.post(settings["create_url"], json=payload, timeout=30)
    try:
        j = resp.json()
    except Exception:
        j = {"raw_text": resp.text, "status_code": resp.status_code}

    pay_url = j.get("paymeURL") or j.get("paymeUrl") or j.get("paymentUrl") or j.get("payUrl")

    if pay_url and pr_doc:
        frappe.db.set_value("Payment Request", pr_doc.name, "payment_url", pay_url)

    if pay_url:
        return {"status": "success", "redirect_url": pay_url, "payment_url": pay_url, "invoice": inv_name, "raw": j, "amount": grand}

    frappe.log_error(title=f"ClicknPay Fail {inv_name}", message=str(j) + "\n" + str(payload))
    return {"status": "error", "raw": j, "payload": payload}

@frappe.whitelist(allow_guest=True)
def check_status(reference):
    settings = get_settings()
    try:
        r = requests.get(f"{settings['status_url']}/{reference}", timeout=15)
        data = r.json()
        if isinstance(data, list) and data:
            return data[0]
        return data
    except Exception as e:
        return {"status": "UNKNOWN", "error": str(e)}

@frappe.whitelist(allow_guest=True)
def clicknpay_callback():
    ref = (frappe.form_dict.get("clientReference") or frappe.form_dict.get("reference") or "UNKNOWN").strip()
    status_val = "SUCCESS"
    try:
        s = check_status(ref) if ref!= "UNKNOWN" else {}
        if isinstance(s, list) and s: s = s[0]
        if isinstance(s, dict):
            status_val = (s.get("status") or s.get("paymentStatus") or "SUCCESS").upper()
    except Exception:
        status_val = "SUCCESS"

    try:
        if ref!= "UNKNOWN" and frappe.db.exists("Sales Invoice", ref):
            inv = frappe.get_doc("Sales Invoice", ref)
            if inv.docstatus == 1 and inv.outstanding_amount > 0:
                orig = frappe.session.user
                frappe.set_user("Administrator")
                frappe.flags.ignore_permissions = True
                if not frappe.db.exists("Payment Entry", {"reference_no": ref, "docstatus": ["<", 2]}):
                    mode_of_payment = "ClicknPay"
                    paid_to = frappe.db.get_value("Mode of Payment Account", {"parent": mode_of_payment, "company": inv.company}, "default_account")
                    if not paid_to:
                        paid_to = frappe.db.get_value("Company", inv.company, "default_bank_account") or frappe.db.get_value("Company", inv.company, "default_cash_account")
                    if not paid_to:
                        paid_to = "Bank Account - CSPL"
                    pe = frappe.get_doc({
                        "doctype": "Payment Entry", "company": inv.company, "payment_type": "Receive",
                        "party_type": "Customer", "party": inv.customer, "paid_from": inv.debit_to, "paid_to": paid_to,
                        "posting_date": today(), "paid_amount": inv.outstanding_amount, "received_amount": inv.outstanding_amount,
                        "reference_no": ref, "reference_date": today(), "mode_of_payment": mode_of_payment,
                        "references": [{"reference_doctype": "Sales Invoice", "reference_name": ref, "allocated_amount": inv.outstanding_amount}]
                    })
                    pe.insert(ignore_permissions=True)
                    pe.submit()
                    frappe.db.commit()
                frappe.set_user(orig)
    except Exception:
        frappe.log_error(title=f"ClicknPay PE {ref}", message=frappe.get_traceback())

    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = f"{get_url()}/payment-success?doctype=Sales Invoice&docname={ref}&invoice={ref}&status={status_val}&gateway=clicknpay"

@frappe.whitelist(allow_guest=True)
def pay_invoice(invoice_name=None):
    invoice_name = invoice_name or frappe.form_dict.get("invoice_name") or frappe.form_dict.get("reference") or frappe.form_dict.get("clientReference")
    if not invoice_name:
        frappe.throw("Missing invoice_name")
    result = initiate_payment(reference=invoice_name)
    if result.get("status") == "success" and result.get("redirect_url"):
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = result["redirect_url"]
    else:
        frappe.throw(f"Payment init failed: {result.get('raw')}")
