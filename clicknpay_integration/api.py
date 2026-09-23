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

    products = []
    for idx, i in enumerate(inv_doc.items):
        products.append({
            "description": (i.description or i.item_name or "")[:100],
            "id": idx + 1,
            "price": float(i.rate or 0),
            "productName": i.item_code,
            "quantity": int(i.qty or 1)
        })
    if not products:
        products = [{"description": (description or "Payment")[:100], "id": 1, "price": float(inv_doc.grand_total), "productName": "ITEM", "quantity": qty}]

    payload = {
        "channel": "AUTOMATED",
        "clientReference": invoice_name,
        "currency": curr,
        "customerCharged": True,
        "customerPhoneNumber": phone.replace(" ", "") or "263771234567",
        "description": (description or "Payment x{0}".format(qty))[:200],
        "multiplePayments": False,
        "orderYpe": "DYNAMIC",
        "productsList": products,
        "publicUniqueId": settings["public_id"],
        "returnUrl": return_url
    }
    resp = requests.post(settings["create_url"], json=payload, timeout=30)
    j = resp.json()
    pay_url = j.get("paymeURL") or j.get("paymeUrl") or j.get("paymentUrl")
    if pay_url:
        return {"status": "success", "redirect_url": pay_url, "invoice": invoice_name, "raw": j}
    return {"status": "error", "raw": j}

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
    gateway_status = (frappe.form_dict.get("status") or "").upper()

    # Get REAL status from ClicknPay
    real_status = "UNKNOWN"
    try:
        if ref!= "UNKNOWN":
            s = check_status(ref) or {}
            if isinstance(s, list) and s:
                s = s[0]
            if isinstance(s, dict):
                real_status = (s.get("status") or s.get("paymentStatus") or gateway_status or "UNKNOWN").upper()
    except Exception:
        real_status = gateway_status or "UNKNOWN"

    success_statuses = ("SUCCESS","PAID","COMPLETED","APPROVED","TOP-PAID")
    is_success = real_status in success_statuses or gateway_status in success_statuses

    # ONLY create PE on SUCCESS
    if is_success:
        try:
            if ref!= "UNKNOWN" and frappe.db.exists("Sales Invoice", ref):
                inv = frappe.get_doc("Sales Invoice", ref)
                if inv.docstatus == 1 and inv.outstanding_amount > 0:
                    frappe.set_user("Administrator")
                    frappe.flags.ignore_permissions = True
                    if not frappe.db.exists("Payment Entry", {"reference_no": ref, "docstatus": ["<", 2]}):
                        # Dynamic paid_to from your Mode of Payment ClicknPay
                        paid_to = frappe.db.get_value("Mode of Payment Account", {"parent": "ClicknPay", "company": inv.company}, "default_account") or "GW Keys FBC USD - GW"
                        pe = frappe.new_doc("Payment Entry")
                        pe.company = inv.company
                        pe.payment_type = "Receive"
                        pe.party_type = "Customer"
                        pe.party = inv.customer
                        pe.paid_from = inv.debit_to
                        pe.paid_to = paid_to
                        pe.mode_of_payment = "ClicknPay"
                        pe.posting_date = today()
                        pe.paid_amount = inv.outstanding_amount
                        pe.received_amount = inv.outstanding_amount
                        pe.source_exchange_rate = 1
                        pe.target_exchange_rate = 1
                        pe.paid_from_account_currency = inv.currency
                        pe.paid_to_account_currency = inv.currency
                        pe.reference_no = ref
                        pe.reference_date = today()
                        pe.append("references", {
                            "reference_doctype": "Sales Invoice",
                            "reference_name": ref,
                            "allocated_amount": inv.outstanding_amount
                        })
                        pe.insert(ignore_permissions=True)
                        pe.submit()
                        frappe.db.commit()
        except Exception as e:
            frappe.log_error(title=f"ClicknPay PE {ref} FAIL {str(e)[:100]}", message=frappe.get_traceback())
            is_success = False
            real_status = "PE_FAILED"

    frappe.local.response["type"] = "redirect"
    if is_success:
        frappe.local.response["location"] = f"{get_url()}/payment-success?doctype=Sales Invoice&docname={ref}&invoice={ref}&status={real_status}&gateway=clicknpay"
    else:
        if real_status == "UNKNOWN":
            real_status = "FAILED"
        frappe.local.response["location"] = f"{get_url()}/payment-failed?doctype=Sales Invoice&docname={ref}&invoice={ref}&status={real_status}&gateway=clicknpay"

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