import frappe
import requests
from frappe.utils import today, get_url, cint

CREATE_URL = "https://backendservices.clicknpay.africa:2081/payme/orders"
STATUS_URL = "https://backendservices.clicknpay.africa:2081/payme/orders/top-paid"

def get_settings():
    public_id = None
    try:
        mode = frappe.db.get_single_value("ClicknPay Settings", "mode") or "Test"
        public_id = frappe.db.get_single_value("ClicknPay Settings", "live_public_id") if mode == "Live" else frappe.db.get_single_value("ClicknPay Settings", "test_public_id")
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
def initiate_payment(reference=None, payment_request=None, invoice_name=None, **kwargs):
    original_pr = (payment_request or kwargs.get("payment_request_name") or "").strip()
    reference = (reference or invoice_name or kwargs.get("reference_name") or "").strip()

    site_url = get_url()
    settings = get_settings()
    pr_doc = None
    inv_name = None

    # Resolve PRQ -> SINV
    if reference and frappe.db.exists("Payment Request", reference):
        pr_doc = frappe.get_doc("Payment Request", reference)
        inv_name = pr_doc.reference_name
        original_pr = pr_doc.name
    elif original_pr and frappe.db.exists("Payment Request", original_pr):
        pr_doc = frappe.get_doc("Payment Request", original_pr)
        inv_name = pr_doc.reference_name
    elif reference and frappe.db.exists("Sales Invoice", reference):
        inv_name = reference

    # Fallback email search
    if not inv_name:
        search_email = kwargs.get("email") or kwargs.get("contact_email") or ""
        if search_email and "@" in search_email:
            inv = frappe.get_all("Sales Invoice", filters={"contact_email": search_email, "docstatus": ["!=", 2]}, limit=1, order_by="creation desc")
            if inv:
                inv_name = inv[0].name

    if not inv_name:
        frappe.throw(f"Invoice not found Ref: {reference} / PRQ: {original_pr}")

    inv_doc = frappe.get_doc("Sales Invoice", inv_name)
    grand = float(inv_doc.grand_total or 0)
    phone = (kwargs.get("phone") or kwargs.get("contact_phone") or "").strip()

    # UNIQUE clientReference - fixes cached 23.97 / 57.75 bug
    if original_pr:
        client_ref = f"{inv_name}-{original_pr}"
    else:
        client_ref = f"{inv_name}-{frappe.generate_hash(length=6)}"

    return_url = f"{site_url}/api/method/clicknpay_integration.api.clicknpay_callback?clientReference={client_ref}"

    # Single product = grand_total incl. VAT - fixes 100 vs 115.50 bug
    products = [{
        "description": f"Payment for {inv_name}"[:100],
        "id": 1,
        "price": grand,
        "productName": inv_name[:50],
        "quantity": 1
    }]

    payload = {
        "channel": "AUTOMATED",
        "clientReference": client_ref,
        "currency": inv_doc.currency or "USD",
        "customerCharged": True,
        "amount": grand, # FIXES Pay USD empty + Charge -115.50
        "customerPhoneNumber": (phone.replace(" ", "") or "263771234567")[:15],
        "description": f"Payment for {inv_name} - {grand} USD"[:200],
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
        return {"status": "success", "redirect_url": pay_url, "payment_url": pay_url, "invoice": inv_name, "clientReference": client_ref, "amount": grand, "raw": j}
    return {"status": "error", "raw": j, "payload": payload}

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
    client_ref = (frappe.form_dict.get("clientReference") or frappe.form_dict.get("reference") or "UNKNOWN").strip()

    # Extract SINV from client_ref like ACC-SINV-2026-00026-ACC-PRQ-2026-00012
    sinv_ref = client_ref.split("-ACC-PRQ-")[0] if "-ACC-PRQ-" in client_ref else client_ref
    if frappe.db.exists("Payment Request", client_ref):
        sinv_ref = frappe.db.get_value("Payment Request", client_ref, "reference_name") or sinv_ref
    elif "-ACC-PRQ-" in client_ref:
        # Try reconstruct PRQ name
        try:
            prq_name = "ACC-PRQ-" + "-".join(client_ref.split("-ACC-PRQ-")[1].split("-")[:3])
            # More robust: find PRQ that ends with this hash
            if frappe.db.exists("Payment Request", prq_name):
                sinv_ref = frappe.db.get_value("Payment Request", prq_name, "reference_name") or sinv_ref
        except Exception:
            pass

    # Check REAL status from ClicknPay
    real_status = "UNKNOWN"
    try:
        s = check_status(client_ref)
        if isinstance(s, dict):
            real_status = (s.get("status") or s.get("paymentStatus") or "UNKNOWN").upper()
    except Exception:
        pass

    success_statuses = ("SUCCESS","PAID","COMPLETED","APPROVED","TOP-PAID")
    is_success = real_status in success_statuses

    # ONLY create PE on SUCCESS - fixes fail counted as success
    if is_success and sinv_ref!= "UNKNOWN" and frappe.db.exists("Sales Invoice", sinv_ref):
        try:
            inv = frappe.get_doc("Sales Invoice", sinv_ref)
            if inv.docstatus == 1 and inv.outstanding_amount > 0:
                frappe.set_user("Administrator")
                frappe.flags.ignore_permissions = True
                if not frappe.db.exists("Payment Entry", {"reference_no": client_ref, "docstatus": ["<", 2]}):
                    paid_to = frappe.db.get_value("Mode of Payment Account", {"parent": "ClicknPay", "company": inv.company}, "default_account")
                    if not paid_to:
                        paid_to = frappe.db.get_value("Company", inv.company, "default_bank_account") or frappe.db.get_value("Company", inv.company, "default_cash_account") or "Bank Account - CSPL"
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
                    pe.reference_no = client_ref
                    pe.reference_date = today()
                    pe.append("references", {"reference_doctype": "Sales Invoice", "reference_name": sinv_ref, "allocated_amount": inv.outstanding_amount})
                    pe.insert(ignore_permissions=True)
                    pe.submit()
                    frappe.db.commit()
        except Exception as e:
            frappe.log_error(title=f"ClicknPay PE {client_ref} FAIL", message=frappe.get_traceback())
            is_success = False
            real_status = "PE_ERROR"

    frappe.local.response["type"] = "redirect"
    if is_success:
        frappe.local.response["location"] = f"{get_url()}/payment-success?doctype=Sales Invoice&docname={sinv_ref}&invoice={sinv_ref}&status={real_status}&gateway=clicknpay&ref={client_ref}"
    else:
        if real_status == "UNKNOWN":
            real_status = "FAILED"
        frappe.local.response["location"] = f"{get_url()}/payment-failed?doctype=Sales Invoice&docname={sinv_ref}&invoice={sinv_ref}&status={real_status}&gateway=clicknpay&ref={client_ref}"

@frappe.whitelist(allow_guest=True)
def pay_invoice(invoice_name=None):
    invoice_name = invoice_name or frappe.form_dict.get("invoice_name") or frappe.form_dict.get("reference") or frappe.form_dict.get("clientReference") or ""
    if not invoice_name:
        frappe.throw("Missing invoice_name")
    result = initiate_payment(reference=invoice_name)
    if result.get("status") == "success" and result.get("redirect_url"):
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = result["redirect_url"]
    else:
        frappe.throw(f"Payment init failed: {result.get('raw')}")
