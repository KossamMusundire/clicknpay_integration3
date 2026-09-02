# ClicknPay Integration for Frappe / ERPNext

A reusable, generic payment integration for **Frappe Framework and ERPNext** that connects your site to **ClicknPay / OpenAPI Africa**.

The app allows Frappe applications to initiate ClicknPay payments, redirect customers to the ClicknPay payment page, verify payment status, and automatically create ERPNext Payment Entries after successful payment.

It is designed as a **generic payment layer**, so it can be used for sales, subscriptions, memberships, services, SaaS billing, custom checkout flows, and other Frappe applications.

> **ClicknPay API:** https://openapi.africa
> **Create Order API:** `https://backendservices.clicknpay.africa:2081/payme/orders`

---

## Features

* **ClicknPay payment initiation**

  * Create dynamic ClicknPay payment orders.
  * Generate a customer-facing `paymeURL`.
  * Redirect customers to ClicknPay checkout.

* **Payment status verification**

  * Query ClicknPay for the latest payment status.
  * Verify payments using the customer's `clientReference`.

* **Automatic payment processing**

  * Handle ClicknPay return/callback requests.
  * Verify the payment before marking it as paid.
  * Automatically create an ERPNext `Payment Entry`.

* **ERPNext integration**

  * Supports Sales Invoices.
  * Supports Sales Orders and custom references.
  * Supports Subscription-related invoices.
  * Uses ERPNext's standard payment infrastructure.

* **Generic references**

  * A payment reference can be any valid business identifier.
  * Examples:

    * `SINV-00001`
    * `SO-00001`
    * `SUB-00001`
    * `MEMBER-00001`
    * `ORDER-10001`
    * Custom application IDs

* **Configuration through Desk**

  * Test / Live mode.
  * Public Unique ID.
  * API URLs.
  * Supported currencies.

* **`site_config.json` fallback**

  * Useful for deployments where credentials/configuration should be managed outside the Desk.

* **Subscription aware**

  * Can locate outstanding Sales Invoices associated with a Subscription.

* **Reusable**

  * No hard-coded customer, company, item, subscription, or business logic.
  * Suitable for multiple Frappe/ERPNext implementations.

---

# Payment Flow

The integration follows the general ClicknPay payment workflow:

```text
Customer
   |
   | 1. Click "Pay"
   v
Frappe / ERPNext
   |
   | 2. initiate_payment()
   v
ClicknPay API
   |
   | 3. Create DYNAMIC order
   v
ClicknPay
   |
   | 4. Return paymeURL
   v
Frappe / Browser
   |
   | 5. Redirect customer
   v
ClicknPay Checkout
   |
   | 6. Customer completes payment
   v
ClicknPay
   |
   | 7. Return to Frappe callback
   v
Frappe / ERPNext
   |
   | 8. Verify payment status
   v
ClicknPay API
   |
   | 9. PAID
   v
ERPNext
   |
   | 10. Create Payment Entry
   v
Sales Invoice / Customer Account
```

The integration **does not trust the browser redirect alone**. The callback should verify the transaction status against ClicknPay before creating a Payment Entry.

---

# Requirements

## Frappe / ERPNext

Supported versions:

```text
Frappe >= 15.0.0
Frappe < 17.0.0
```

Recommended:

```text
Python >= 3.10
```

The application requires the Python `requests` package.

For ERPNext-specific functionality such as Sales Invoice and Payment Entry handling, ERPNext should be installed on the site.

---

# Installation

## 1. Get the application

From your Frappe bench:

```bash
bench get-app https://github.com/cyteersystems/clicknpay_integration.git
```

## 2. Install the application

```bash
bench --site your.site.name install-app clicknpay_integration
```

## 3. Migrate

```bash
bench --site your.site.name migrate
```

## 4. Clear cache

```bash
bench --site your.site.name clear-cache
```

## 5. Restart

For a development environment:

```bash
bench restart
```

For production deployments, restart the appropriate Frappe services after installation.

---

# Configuration

There are two supported configuration methods.

## Option A — Desk Configuration

This is the recommended method for most users.

Navigate to:

```text
Desk → ClicknPay Settings
```

Configure:

| Setting               | Description                       |
| --------------------- | --------------------------------- |
| Mode                  | `Test` or `Live`                  |
| Test Public Unique ID | ClicknPay test Public Unique ID   |
| Live Public Unique ID | ClicknPay live Public Unique ID   |
| Create Order URL      | ClicknPay order creation endpoint |
| Status URL            | ClicknPay payment status endpoint |
| Supported Currency    | Currency used by the payment      |

Example:

```text
Mode:
Test

Test Public Unique ID:
HQGVaTYJihldpvzsw

Create Order URL:
https://backendservices.clicknpay.africa:2081/payme/orders

Status URL:
https://backendservices.clicknpay.africa:2081/payme/orders/top-paid
```

For production, replace the test Public Unique ID with the Public Unique ID provided for your ClicknPay live account.

---

# Option B — `site_config.json`

Configuration can also be stored in the site's `site_config.json`.

Example:

```json
{
    "clicknpay_public_id": "YOUR_PUBLIC_UNIQUE_ID",
    "clicknpay_create_url": "https://backendservices.clicknpay.africa:2081/payme/orders",
    "clicknpay_status_url": "https://backendservices.clicknpay.africa:2081/payme/orders/top-paid"
}
```

The application can use these values when the corresponding Desk configuration is not available.

### Security recommendation

Do not commit `site_config.json` containing production credentials or private configuration to a public Git repository.

---

# API

The application exposes Frappe whitelisted methods for payment processing.

## 1. Initiate Payment

```http
GET /api/method/clicknpay_integration.api.initiate_payment
```

Example:

```text
/api/method/clicknpay_integration.api.initiate_payment
    ?reference=SINV-00001
    &email=customer@example.com
    &phone=263771234567
    &plan_name=Gold%20Plan
    &qty=1
    &currency=USD
```

### Parameters

| Parameter      | Required | Description                           |
| -------------- | -------: | ------------------------------------- |
| `reference`    |      Yes | Unique business/payment reference     |
| `email`        |       No | Customer email address                |
| `phone`        |       No | Customer phone number                 |
| `subscription` |       No | ERPNext Subscription reference        |
| `plan_name`    |       No | Product, plan, or service description |
| `qty`          |       No | Quantity                              |
| `currency`     |       No | Payment currency                      |

The method creates a ClicknPay `DYNAMIC` order and returns the payment URL.

Example response:

```json
{
    "message": {
        "success": true,
        "redirect_url": "https://...",
        "client_reference": "SINV-00001"
    }
}
```

The frontend can then redirect the customer:

```javascript
frappe.call({
    method: "clicknpay_integration.api.initiate_payment",
    args: {
        reference: docName,
        email: customerEmail,
        phone: customerPhone,
        plan_name: planName,
        qty: 1,
        currency: "USD"
    },
    callback: function (r) {
        if (r.message && r.message.redirect_url) {
            window.location.assign(r.message.redirect_url);
        }
    }
});
```

---

# 2. Check Payment Status

```http
GET /api/method/clicknpay_integration.api.check_status
```

Example:

```text
/api/method/clicknpay_integration.api.check_status?reference=SINV-00001
```

This queries ClicknPay using the payment's client reference.

Example:

```json
{
    "message": {
        "success": true,
        "status": "PAID",
        "reference": "SINV-00001"
    }
}
```

Applications should use this endpoint when they need to independently verify a payment.

---

# 3. ClicknPay Callback

```http
GET /api/method/clicknpay_integration.api.clicknpay_callback
```

Example:

```text
/api/method/clicknpay_integration.api.clicknpay_callback?clientReference=SINV-00001
```

The callback:

1. Receives the ClicknPay reference.
2. Identifies the corresponding Frappe transaction.
3. Queries ClicknPay for the payment status.
4. Verifies that the payment is successful.
5. Creates the appropriate ERPNext Payment Entry.
6. Redirects the customer to the payment success page.

Example:

```text
ClicknPay
   ↓
clientReference
   ↓
Find transaction
   ↓
Check ClicknPay status
   ↓
PAID?
   ↓
Create Payment Entry
   ↓
Payment Success
```

---

# ERPNext Payment Entry

When a payment is successfully verified, the integration can create an ERPNext `Payment Entry`.

For a Sales Invoice payment, the Payment Entry should contain information such as:

```text
Payment Type: Receive
Party Type: Customer
Party: Customer
Paid Amount: Transaction Amount
Reference Type: Sales Invoice
Reference Name: SINV-00001
```

The exact accounting configuration depends on the ERPNext site's:

* Company
* Accounts
* Currency
* Bank/Cash account
* Customer
* Payment Mode
* Exchange-rate configuration

The integration is intended to use ERPNext's standard accounting documents rather than maintaining a separate payment ledger.

---

# Idempotency

Payment callbacks can potentially be received more than once.

The integration should therefore avoid creating duplicate Payment Entries for the same successful transaction.

A recommended flow is:

```text
Callback received
      |
      v
Find existing payment/reference
      |
   Exists?
   /     \
 Yes      No
 |         |
Stop     Verify
           |
          PAID?
         /    \
       No      Yes
               |
        Create Payment Entry
```

Implementations should treat the payment reference or ClicknPay transaction identifier as the unique payment identifier.

---

# Frontend Integration

A payment button can be added to:

* Web pages
* Customer portals
* Subscription pages
* Sales Invoice pages
* Custom DocTypes
* Membership portals
* Public checkout pages

Example:

```javascript
frappe.call({
    method: "clicknpay_integration.api.initiate_payment",
    args: {
        reference: doc.name,
        email: doc.contact_email,
        phone: doc.contact_mobile,
        currency: "USD"
    },
    callback: function (r) {

        if (r.message && r.message.redirect_url) {
            window.location.href = r.message.redirect_url;
        }

    }
});
```

For public/guest checkout pages, ensure that the API method only exposes information that is safe for unauthenticated users.

---

# Generic Checkout Architecture

The application intentionally does not assume that every payment belongs to a Sales Invoice.

A custom application can use its own reference:

```text
reference = "MEMBER-00001"
```

or:

```text
reference = "ORDER-2026-00045"
```

or:

```text
reference = "BOOKING-00032"
```

The application can then resolve that reference to the appropriate business document.

This makes the integration suitable for:

* Membership systems
* Subscription systems
* SaaS applications
* Online stores
* Service bookings
* School fees
* Donations
* Event registrations
* Customer deposits
* Custom Frappe applications

---

# Sales Invoice Payments

A typical ERPNext Sales Invoice flow is:

```text
Sales Invoice
     |
     | outstanding_amount > 0
     v
Pay Online
     |
     v
ClicknPay Order
     |
     v
Customer Payment
     |
     v
Callback
     |
     v
Verify Payment
     |
     v
Payment Entry
     |
     v
Sales Invoice Outstanding = 0
```

A payment link can be included in an ERPNext Email Notification.

Example:

```jinja
{{ frappe.utils.get_url() }}/subscriptions/{{ doc.subscription }}?invoice={{ doc.name }}
```

The actual URL should be adapted to the application's portal or checkout implementation.

---

# Subscription Payments

For subscription-based implementations, the integration can use the Subscription reference to locate the relevant outstanding Sales Invoice.

Example:

```text
Subscription
    |
    v
Outstanding Sales Invoice
    |
    v
ClicknPay Checkout
    |
    v
Payment
    |
    v
Payment Entry
```

This allows the same integration to support recurring membership or subscription workflows without hard-coding a particular subscription product.

---

# Currency Support

The integration supports configurable currencies, including:

```text
USD
ZWG
ZWL
AED
```

Additional currencies can be supported where they are accepted by the ClicknPay account and API configuration.

The currency used for the payment should match the currency of the underlying ERPNext transaction where applicable.

> **Important:** Currency availability and payment methods are ultimately determined by ClicknPay and the merchant account configuration.

---

# Test and Live Environments

Use **Test mode** during development.

Typical workflow:

```text
Development
     |
     v
ClicknPay Test Environment
     |
     v
Test payment
     |
     v
Verify callback
     |
     v
Test Payment Entry
```

Once the integration has been validated:

```text
Production
     |
     v
ClicknPay Live Environment
     |
     v
Real payment
```

Always verify your ClicknPay account's current API documentation and credentials before switching to production.

---

# Security

Payment integrations should be treated as security-sensitive.

## Do not trust the redirect

A customer returning to your website does **not** by itself prove that payment was successful.

Always verify the transaction against ClicknPay.

```text
Browser says:
"Payment successful"

        ↓

Do NOT immediately create Payment Entry.

        ↓

Ask ClicknPay:
"What is the status of this reference?"

        ↓

PAID

        ↓

Create Payment Entry
```

## Protect configuration

Do not expose:

* Private API credentials
* Server configuration
* Internal ERPNext API keys
* Database credentials

in frontend JavaScript or public web pages.

## Validate references

Payment references should be validated before being used to locate ERPNext documents.

## Prevent duplicate payments

Payment processing should be idempotent to prevent duplicate Payment Entries.

---

# Customization

The application is intentionally designed as a reusable integration layer.

Business-specific logic should normally be implemented by the application using ClicknPay rather than hard-coded into the integration itself.

For example:

```text
clicknpay_integration
        |
        | generic payment functionality
        v
-----------------------------
Your Frappe Application
-----------------------------
        |
        +-- Membership
        +-- Sales
        +-- Subscriptions
        +-- Bookings
        +-- SaaS Billing
        +-- Custom Checkout
```

This keeps the payment integration reusable across different projects.

---

# Recommended Integration Pattern

For a custom application, use the following approach:

### Step 1 — Create your business transaction

For example:

```text
Membership
MEM-00001
Amount: USD 50
Status: Unpaid
```

### Step 2 — Generate a unique payment reference

```text
MEM-00001
```

### Step 3 — Initiate ClicknPay payment

```text
initiate_payment(reference="MEM-00001")
```

### Step 4 — Redirect the customer

Use the returned:

```text
redirect_url
```

### Step 5 — Handle callback

ClicknPay returns the customer to your configured callback URL.

### Step 6 — Verify

Query ClicknPay using the client reference.

### Step 7 — Update your application

Only after successful verification:

```text
Payment Status = Paid
```

For ERPNext accounting workflows, create the appropriate `Payment Entry`.

---

# Email Payment Links

For ERPNext implementations, payment links can be included in Email Notifications.

Example condition:

```python
doc.outstanding_amount > 0
```

A generic email template could provide a button pointing to the application's checkout page:

```text
Customer
   |
   | Receives invoice
   v
Email
   |
   | "Pay Now"
   v
Frappe Checkout
   |
   v
ClicknPay
```

The checkout page can then call:

```text
clicknpay_integration.api.initiate_payment
```

---

# API Authentication

Frappe API authentication depends on how the endpoint is exposed.

For authenticated users, standard Frappe authentication mechanisms can be used.

For public checkout flows, carefully review whether the endpoint needs guest access and ensure that:

* References cannot be used to access private ERPNext data.
* Customer information is not unnecessarily exposed.
* Payment amounts cannot be manipulated by the browser.
* The server determines the amount from the authoritative business document.

**Never trust a payment amount supplied directly by an untrusted client.**

A safer pattern is:

```text
Browser
   |
   | reference = SINV-00001
   v
Frappe
   |
   | Look up Sales Invoice
   v
ERPNext
   |
   | Read authoritative amount
   v
ClicknPay
```

rather than:

```text
Browser
   |
   | amount = $1
   v
ClicknPay
```

---

# Troubleshooting

## Payment URL is not returned

Check:

1. ClicknPay Public Unique ID.
2. Test/Live mode.
3. Create Order URL.
4. Currency.
5. Required request parameters.
6. Frappe error logs.

Useful commands:

```bash
bench --site your.site.name console
```

and:

```bash
bench --site your.site.name logs
```

---

## Callback is received but Payment Entry is not created

Check:

1. The callback contains the correct `clientReference`.
2. ClicknPay reports the transaction as `PAID`.
3. The reference resolves to the correct ERPNext document.
4. The Customer exists.
5. The Company is valid.
6. A valid receivable/bank account is configured.
7. The transaction has not already been processed.
8. The ERPNext user has permission to create the Payment Entry.

---

## Payment shows successful but invoice remains outstanding

Check the generated Payment Entry.

Verify:

```text
Payment Entry = Submitted
Reference Type = Sales Invoice
Reference Name = Correct Invoice
Allocated Amount = Correct Amount
```

Also verify that the Payment Entry currency and account configuration are correct.

---

# Logging

During development, enable appropriate application logging to diagnose:

* ClicknPay API requests
* API responses
* Client references
* Callback processing
* Payment status
* Payment Entry creation errors

Do **not** log sensitive credentials or private payment information.

---

# Project Structure

A typical application structure:

```text
clicknpay_integration/
│
├── clicknpay_integration/
│   ├── api.py
│   ├── hooks.py
│   │
│   ├── doctype/
│   │   └── clicknpay_settings/
│   │       ├── clicknpay_settings.json
│   │       └── clicknpay_settings.py
│   │
│   └── ...
│
├── clicknpay_integration/
│   └── config/
│
├── pyproject.toml
├── README.md
└── license.txt
```

The exact structure may change as the application evolves.

---

# Development

Clone the application into a development bench:

```bash
bench get-app https://github.com/cyteersystems/clicknpay_integration.git
```

Install it on a development site:

```bash
bench --site development.local install-app clicknpay_integration
```

After making changes:

```bash
bench --site development.local migrate
bench --site development.local clear-cache
bench restart
```

---

# Production Checklist

Before going live, verify:

* [ ] ClicknPay Live account is active.
* [ ] Live Public Unique ID is configured.
* [ ] Live API endpoint is configured.
* [ ] Currency is supported.
* [ ] Callback URL is publicly accessible over HTTPS.
* [ ] Payment status is verified server-side.
* [ ] Duplicate callbacks are handled.
* [ ] Payment Entry creation works.
* [ ] Customer and Company configuration is correct.
* [ ] Payment account is configured.
* [ ] Guest/public endpoints are secured.
* [ ] Payment amounts are determined server-side.
* [ ] Error logging is enabled.
* [ ] Sensitive credentials are not exposed.
* [ ] A complete test payment has been performed.

---

# Example Use Cases

The same integration can be used by many types of Frappe applications.

### ERPNext Sales

```text
Sales Invoice → ClicknPay → Payment Entry
```

### Membership

```text
Membership → Checkout → ClicknPay → Membership Activated
```

### Subscription

```text
Subscription → Sales Invoice → ClicknPay → Payment Entry
```

### SaaS Billing

```text
Plan → Checkout → ClicknPay → Payment → Account Activated
```

### Custom Application

```text
Custom DocType → Payment Reference → ClicknPay → Callback → Update Document
```

---

# Design Principles

The application follows several principles:

### Generic

No business-specific workflows are hard-coded into the payment integration.

### Server-side verification

Successful payment status should be verified against ClicknPay before financial records are updated.

### ERPNext-native

Where ERPNext accounting is involved, standard ERPNext documents such as `Sales Invoice` and `Payment Entry` are used.

### Configurable

API endpoints, Public Unique IDs, currencies, and environment settings can be configured without changing source code.

### Reusable

The same application can be installed across multiple Frappe/ERPNext sites.

### Extensible

Custom Frappe applications can build their own checkout and business workflows on top of the integration.

---

# Support and Contributions

This project is maintained by **Cyteer Systems**.

For support or integration assistance:

**Email:** [support@cyteersystems.com](mailto:support@cyteersystems.com)

Issues, improvements, and contributions are welcome.

When reporting an issue, include:

* Frappe version
* ERPNext version
* ClicknPay environment
* Error message
* Relevant application logs
* Steps required to reproduce the problem

Do not include passwords, API credentials, private keys, or other sensitive information in issue reports.

---

# License

MIT License

Copyright © Cyteer Systems

This project is provided as open-source software under the MIT License.
