import frappe
import requests
from frappe.utils import today, get_url, cint
import json

CREATE_URL = "https://backendservices.clicknpay.africa:2081/payme/orders"
STATUS_URL = "https://backendservices.clicknpay.africa:2081/payme/orders/top-paid"

def get_settings():
    public_id = None
    try:
        if frappe.db.exists("DocType", "ClicknPay Settings"):
            doc = frappe.get_cached_doc("ClicknPay Settings")
            public_id = doc.live_public_id if doc.mode == "Live" else doc.test_public_id
    except Exception:
        pass
    if not public_id:
        public_id = frappe.conf.get("clicknpay_public_id") or "HQGVaTYJihldpvzsw"
    return {
        "public_id": public_id,
        "create_url": frappe.conf.get("clicknpay_create_url") or CREATE_URL,
        "status_url": frappe.conf.get("clicknpay_status_url") or STATUS_URL,
    }

def create_or_update_log(order_id, reference, amount=0, status="PENDING", payme_url=None, raw=None, payment_entry=None, pr_name=None, source="CyteERP Portal", customer=None, email=None):
    try:
        if not order_id:
            order_id = reference
        # Try get existing
        if frappe.db.exists("ClicknPay Transaction Log", order_id):
            doc = frappe.get_doc("ClicknPay Transaction Log", order_id)
            doc.status = status
            if payme_url: doc.payme_url = payme_url
            if payment_entry: doc.payment_entry = payment_entry
            if raw: doc.raw_response = json.dumps(raw, indent=2)[:10000]
            doc.save(ignore_permissions=True)
            return doc
        else:
            doc = frappe.get_doc({
                "doctype": "ClicknPay Transaction Log",
                "order_id": order_id,
                "reference": reference,
                "status": status,
                "amount": amount,
                "customer": customer,
                "customer_email": email,
                "payme_url": payme_url or "",
                "raw_response": json.dumps(raw, indent=2)[:10000] if raw else "",
                "creation_time": frappe.utils.now(),
                "payment_entry": payment_entry,
                "payment_request": pr_name,
                "sales_invoice": reference if frappe.db.exists("Sales Invoice", reference) else None,
                "source_module": source
            })
            doc.insert(ignore_permissions=True)
            return doc
    except Exception as e:
        frappe.log_error(f"Log create failed {e}", "ClicknPay Log")
        return None

@frappe.whitelist(allow_guest=True)
def initiate_payment(reference=None, subscription=None, email=None, phone=None, qty=1, description=None, return_url=None, currency=None, payment_request=None):
    reference = (reference or "").strip()
    qty = cint(qty or 1) or 1
    invoice_name = reference
    site_url = get_url()
    settings = get_settings()
    pr_name = payment_request or frappe.form_dict.get("payment_request")

    if frappe.db.exists("Subscription", reference):
        outs = frappe.get_all("Sales Invoice", filters={"subscription": reference, "docstatus": 1, "outstanding_amount": [">", 0]}, limit=1, order_by="creation desc")
        if outs:
            invoice_name = outs[0].name

    if not frappe.db.exists("Sales Invoice", invoice_name):
        frappe.throw(f"Invoice not found: {reference}")

    inv_doc = frappe.get_doc("Sales Invoice", invoice_name)
    phone = phone or frappe.db.get_value("Customer", inv_doc.customer, "mobile_no") or "263771234567"
    curr = currency or inv_doc.currency or "USD"
    source = "GW Keys Subscription" if frappe.db.exists("Subscription", reference) else "CyteERP Portal"

    if not return_url:
        return_url = f"{site_url}/api/method/clicknpay_integration.api.clicknpay_callback?clientReference={invoice_name}"

    products = [
        {"description": (i.description or i.item_name)[:100], "id": idx+1, "price": float(i.rate or 0), "productName": i.item_code, "quantity": int(i.qty or 1)}
        for idx, i in enumerate(inv_doc.items)
    ]
    if not products:
        products = [{"description": (description or "Cyteerp Service")[:100], "id": 1, "price": float(inv_doc.grand_total), "productName": "SERVICE", "quantity": qty}]

    payload = {
        "channel": "AUTOMATED",
        "clientReference": invoice_name,
        "currency": curr,
        "customerCharged": True,
        "customerPhoneNumber": phone.replace(" ", ""),
        "description": (description or f"Cyteerp Invoice {invoice_name}")[:200],
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
        frappe.log_error(title="ClicknPay Create Error", message=str(e))
        return {"status": "error", "message": str(e)}

    pay_url = j.get("paymeURL") or j.get("paymeUrl") or j.get("paymentUrl")
    order_id = j.get("orderId") or j.get("order_id") or invoice_name

    # HOOK 1: Create log on order creation - handles both GW Keys and CyteERP
    create_or_update_log(
        order_id=order_id,
        reference=invoice_name,
        amount=inv_doc.grand_total,
        status="PENDING",
        payme_url=pay_url,
        raw=j,
        pr_name=pr_name,
        source=source,
        customer=inv_doc.customer,
        email=email
    )

    if pay_url:
        return {"status": "success", "redirect_url": pay_url, "invoice": invoice_name, "order_id": order_id, "raw": j}
    return {"status": "error", "message": j.get("message") or "No paymeURL", "raw": j}

@frappe.whitelist(allow_guest=True)
def get_payment_url(payment_request_name=None, reference_docname=None):
    if payment_request_name:
        pr = frappe.get_doc("Payment Request", payment_request_name)
        reference_docname = pr.reference_name
    result = initiate_payment(reference=reference_docname, payment_request=payment_request_name)
    if result.get("status") == "success":
        if payment_request_name:
            frappe.db.set_value("Payment Request", payment_request_name, "payment_url", result["redirect_url"])
            frappe.db.commit()
        return result["redirect_url"]
    frappe.throw(f"ClicknPay failed: {result.get('message')}")

@frappe.whitelist(allow_guest=True)
def pay_invoice(invoice_name=None):
    invoice_name = invoice_name or frappe.form_dict.get("invoice_name") or frappe.form_dict.get("reference") or frappe.form_dict.get("clientReference")
    if not invoice_name:
        frappe.throw("Missing invoice_name")
    result = initiate_payment(reference=invoice_name)
    if result.get("status") == "success":
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = result["redirect_url"]
    else:
        frappe.throw(f"Payment init failed: {result.get('message')}")

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
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = f"{get_url()}/payment-success?invoice=UNKNOWN&status=FAILED"
        return

    status_data = check_status(ref)
    status_val = (status_data.get("status") or status_data.get("paymentStatus") or "UNKNOWN").upper()

    pe_name = None
    if status_val in ("SUCCESS", "PAID", "COMPLETED", "APPROVED"):
        try:
            if frappe.db.exists("Sales Invoice", ref):
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
                        pe_name = pe.name
                        frappe.enqueue("clicknpay_integration.fiscal_hook.trigger_fiscalisation", payment_entry_name=pe.name, invoice_name=ref, queue="short")
        except Exception:
            frappe.log_error(title="ClicknPay Callback Error", message=frappe.get_traceback())

    # HOOK 2: Update log with final status
    create_or_update_log(order_id=ref, reference=ref, status=status_val, raw=status_data, payment_entry=pe_name)

    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = f"{get_url()}/payment-success?invoice={ref}&status={status_val}"
