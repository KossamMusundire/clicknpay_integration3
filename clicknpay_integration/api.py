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
def initiate_payment(reference=None, subscription=None, email=None, phone=None, plan_name=None, qty=1, description=None, return_url=None, currency=None):
    reference = (reference or "").strip()
    subscription_arg = (subscription or "").strip()
    email = (email or "").strip()
    phone = (phone or "").strip()
    qty = cint(qty or 1) or 1
    invoice_name = None
    site_url = get_url()
    settings = get_settings()

    if reference and frappe.db.exists("Payment Request", reference):
        reference = frappe.db.get_value("Payment Request", reference, "reference_name") or reference

    if subscription_arg and frappe.db.exists("Subscription", subscription_arg):
        outs = frappe.get_all("Sales Invoice", filters={"subscription": subscription_arg, "docstatus": 1, "outstanding_amount": [">", 0]}, limit=1, order_by="creation desc")
        if outs:
            invoice_name = outs[0].name

    if not invoice_name and reference and frappe.db.exists("Sales Invoice", reference):
        invoice_name = reference

    search_email = email or (reference if "@" in reference else "")
    if not invoice_name and search_email:
        inv = frappe.get_all("Sales Invoice", filters={"contact_email": search_email, "docstatus": ["!=", 2]}, limit=1, order_by="creation desc")
        if inv:
            invoice_name = inv[0].name

    if not invoice_name:
        frappe.throw("Invoice not found Ref: {0}".format(reference))

    inv_doc = frappe.get_doc("Sales Invoice", invoice_name)
    curr = currency or inv_doc.currency or "USD"

    if not return_url:
        return_url = "{0}/api/method/clicknpay_integration.api.clicknpay_callback?clientReference={1}".format(site_url, invoice_name)

    # --- FIXED PRODUCTS BUILDER WITH TAXES ---
    products = []
    total_products_amount = 0

    for idx, i in enumerate(inv_doc.items):
        # Use net rate for items
        price = float(i.rate or 0)
        q = int(i.qty or 1)
        products.append({
            "description": (i.description or i.item_name or "")[:100],
            "id": idx + 1,
            "price": price,
            "productName": (i.item_code or "ITEM")[:50],
            "quantity": q
        })
        total_products_amount += price * q

    # Add taxes as separate product lines so gateway total = grand_total
    tax_offset = len(products)
    if inv_doc.taxes:
        for t_idx, t in enumerate(inv_doc.taxes):
            tax_amt = float(t.tax_amount or 0)
            if tax_amt!= 0:
                products.append({
                    "description": (t.description or "Tax")[:100],
                    "id": tax_offset + t_idx + 1,
                    "price": tax_amt,
                    "productName": "TAX-{0}".format(t_idx+1),
                    "quantity": 1
                })
                total_products_amount += tax_amt

    # Safety: If rounding diff still exists, force to grand_total with single line
    # This guarantees what user sees on your invoice = what gateway charges
    grand = float(inv_doc.grand_total or 0)
    if abs(total_products_amount - grand) > 0.01 or not products:
        # Fallback: send single line = grand_total - this is 100% accurate
        products = [{
            "description": (description or "Payment for {0} - Incl. Tax".format(invoice_name))[:100],
            "id": 1,
            "price": grand,
            "productName": invoice_name,
            "quantity": 1
        }]

    payload = {
        "channel": "AUTOMATED",
        "clientReference": invoice_name,
        "currency": curr,
        "customerCharged": True,
        "customerPhoneNumber": (phone.replace(" ", "") or "263771234567")[:15],
        "description": (description or "Payment x{0} - {1}".format(len(inv_doc.items), invoice_name))[:200],
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

    pay_url = j.get("paymeURL") or j.get("paymeUrl") or j.get("paymentUrl")

    if pay_url:
        # Also update linked Payment Request with correct URL and amount
        pr_name = frappe.db.get_value("Payment Request", {"reference_name": invoice_name, "status": ["in", ["Requested", "Initiated"]]}, "name")
        if pr_name:
            frappe.db.set_value("Payment Request", pr_name, {
                "payment_url": pay_url,
                "grand_total": grand, # force correct total
                "outstanding_amount": grand
            })
            frappe.db.commit()
        return {"status": "success", "redirect_url": pay_url, "invoice": invoice_name, "raw": j, "sent_amount": grand}
    return {"status": "error", "raw": j, "payload_sent": payload}

#... keep check_status, clicknpay_callback, pay_invoice same as yours...
@frappe.whitelist(allow_guest=True)
def check_status(reference):
    settings = get_settings()
    try:
        r = requests.get("{0}/{1}".format(settings["status_url"], reference), timeout=15)
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
        if isinstance(s, list) and s:
            s = s[0]
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
                        paid_to = "GW Keys FBC USD - GW"
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
        frappe.log_error(title="ClicknPay PE {0}".format(ref), message=frappe.get_traceback())
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = "{0}/payment-success?doctype=Sales Invoice&docname={1}&invoice={1}&status={2}&gateway=clicknpay".format(get_url(), ref, status_val)

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
        frappe.throw("Payment init failed: {0}".format(result.get("raw")))
