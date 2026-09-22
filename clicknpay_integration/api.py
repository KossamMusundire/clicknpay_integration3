import frappe
import requests
from frappe.utils import today, getdate, add_days, add_months, get_url, cint
import json

CREATE_URL = "https://backendservices.clicknpay.africa:2081/payme/orders"
STATUS_URL = "https://backendservices.clicknpay.africa:2081/payme/orders/top-paid"

def get_settings():
    # SAFE FOR GUEST - no get_cached_doc that checks Account permission
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
    subscription_name = None
    site_url = get_url()
    settings = get_settings()

    # === COMACO FIX: If reference is PRQ, resolve to SINV ===
    if reference and frappe.db.exists("Payment Request", reference):
        pr = frappe.get_doc("Payment Request", reference)
        reference = pr.reference_name

    if subscription_arg and frappe.db.exists("Subscription", subscription_arg):
        outs = frappe.get_all("Sales Invoice", filters={"subscription": subscription_arg, "docstatus": 1, "outstanding_amount": [">", 0]}, limit=1, order_by="creation desc")
        if outs:
            invoice_name = outs[0].name
            subscription_name = subscription_arg

    if not invoice_name and reference:
        if frappe.db.exists("Sales Invoice", reference):
            invoice_name = reference
        elif frappe.db.exists("Subscription", reference):
            outs = frappe.get_all("Sales Invoice", filters={"subscription": reference, "docstatus": 1, "outstanding_amount": [">", 0]}, limit=1, order_by="creation desc")
            if outs:
                invoice_name = outs[0].name
                subscription_name = reference

    # === ORIGINAL GW KEYS FIX: email search - KEEP THIS, this is why Guest worked ===
    search_email = email or (reference if "@" in reference else "")
    if not invoice_name and search_email:
        inv = frappe.get_all("Sales Invoice", filters={"contact_email": search_email, "docstatus": ["!=", 2]}, limit=1, order_by="creation desc")
        if inv:
            invoice_name = inv[0].name

    if not invoice_name:
        frappe.throw(f"Invoice not found Ref: {reference}")

    inv_doc = frappe.get_doc("Sales Invoice", invoice_name)
    if not phone:
        phone = frappe.db.get_value("Customer", inv_doc.customer, "mobile_no") or "263771234567"
    curr = currency or inv_doc.currency or "USD"
    if not return_url:
    return_url = f"{site_url}/api/method/clicknpay_integration.api.clicknpay_callback?clientReference={invoice_name}"
    products = [{"description": (i.description or i.item_name)[:100], "id": idx+1, "price": float(i.rate or 0), "productName": i.item_code, "quantity": int(i.qty or 1)} for idx, i in enumerate(inv_doc.items)]
    if not products:
        products = [{"description": (description or "Payment")[:100], "id": 1, "price": float(inv_doc.grand_total), "productName": "ITEM", "quantity": qty}]

    payload = {
        "channel": "AUTOMATED",
        "clientReference": invoice_name,
        "currency": curr,
        "customerCharged": True,
        "customerPhoneNumber": phone.replace(" ", ""),
        "description": (description or f"Payment x{qty}")[:200],
        "multiplePayments": False,
        "orderYpe": "DYNAMIC",
        "productsList": products,
        "publicUniqueId": settings["public_id"],
        "returnUrl": return_url
    }

    try:
        resp = requests.post(settings["create_url"], json=payload, timeout=30)
        j = resp.json()
    except Exception as e:
        frappe.log_error(title="ClicknPay Error", message=str(e))
        frappe.throw(f"ClicknPay failed: {e}")

    pay_url = j.get("paymeURL") or j.get("paymeUrl") or j.get("paymentUrl")

    # === SAFE LOG - Only if Transaction Log is standalone (istable=0) AND as Admin ===
    try:
        # Check if doctype is standalone, not child
        if frappe.db.exists("DocType", "ClicknPay Transaction Log"):
            is_table = frappe.db.get_value("DocType", "ClicknPay Transaction Log", "istable")
            if not is_table: # Only log if istable=0
                original_user = frappe.session.user
                frappe.set_user("Administrator")
                frappe.get_doc({
                    "doctype": "ClicknPay Transaction Log",
                    "order_id": j.get("orderId") or invoice_name,
                    "reference": invoice_name,
                    "status": "PENDING",
                    "amount": inv_doc.grand_total,
                    "payme_url": pay_url or ""
                }).insert(ignore_permissions=True, ignore_if_duplicate=True)
                frappe.db.commit()
                frappe.set_user(original_user)
    except:
        pass # Never block payment if log fails

    if pay_url:
        return {"status": "success", "redirect_url": pay_url, "invoice": invoice_name, "raw": j}
    return {"status": "error", "raw": j}

@frappe.whitelist(allow_guest=True)
def check_status(reference):
    settings = get_settings()
    try:
        r = requests.get(f"{settings['status_url']}/{reference}", timeout=15)
        data = r.json()
        return data[0] if isinstance(data, list) and data else data
    except Exception as e:
        return {"status": "UNKNOWN", "error": str(e)}

@frappe.whitelist(allow_guest=True)
def clicknpay_callback():
    ref = frappe.form_dict.get("clientReference") or frappe.form_dict.get("reference")
    if not ref:
        frappe.throw("clientReference missing")
    status_data = check_status(ref)
    status_val = (status_data.get("status") or status_data.get("paymentStatus") or "").upper()

    if status_val in ("SUCCESS", "PAID", "COMPLETED", "APPROVED", "TOP-PAID"):
        try:
            # Run as Admin to avoid Account permission for Guest
            original_user = frappe.session.user
            frappe.set_user("Administrator")
            frappe.flags.ignore_permissions = True

            inv = frappe.get_doc("Sales Invoice", ref)
            if inv.outstanding_amount > 0:
                if not frappe.get_all("Payment Entry", filters={"reference_no": ref, "docstatus": ["<", 2]}, limit=1):
                    pe = frappe.get_doc({
                        "doctype": "Payment Entry",
                        "payment_type": "Receive",
                        "party_type": "Customer",
                        "party": inv.customer,
                        "posting_date": today(),
                        "paid_amount": inv.grand_total,
                        "received_amount": inv.grand_total,
                        "reference_no": ref,
                        "reference_date": today(),
                        "mode_of_payment": "ClicknPay",
                        "references": [{"reference_doctype": "Sales Invoice", "reference_name": ref, "allocated_amount": inv.outstanding_amount}]
                    })
                    pe.insert(ignore_permissions=True)
                    pe.submit()
                    frappe.db.commit()
            frappe.set_user(original_user)
        except Exception:

            # ===== ADD THIS - DIRECT GUEST LINK FOR INVOICE EMAIL & PDF =====
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
        frappe.throw(f"Payment init failed: {result.get('message') or result.get('raw')}")
            frappe.log_error(title="ClicknPay Callback", message=frappe.get_traceback())

    # FIX: Redirect with BOTH formats so no 500
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
        frappe.throw(f"Payment init failed: {result.get('message') or result.get('raw')}")
