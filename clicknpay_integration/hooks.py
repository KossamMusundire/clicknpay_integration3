app_name = "clicknpay_integration"
app_title = "ClicknPay Integration"
app_publisher = "Cyteer Systems"
app_description = "Frappe integration for ClicknPay (openapi.africa) - create orders, check status, handle callbacks"
app_email = "support@cyteersystems.com"
app_license = "mit"
app_version = "1.0.0"


doc_events = {
    "Sales Invoice": {
        "on_submit": "clicknpay_integration.api.create_payment_request"
    }
}