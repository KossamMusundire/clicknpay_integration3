app_name = "clicknpay_integration"
app_title = "ClicknPay Integration with Fiscalisation"
app_publisher = "Cyteerp Systems"
app_description = "Frappe integration for ClicknPay (openapi.africa) - create orders, check status, handle callbacks + ZIMRA fiscalisation"
app_email = "zw@cyteersystems.com"
app_license = "mit"
app_version = "1.0.0"

# Apps
# ------------------
# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "clicknpay_integration",
# 		"logo": "/assets/clicknpay_integration/logo.png",
# 		"title": "ClicknPay Integration with Fiscalisation",
# 		"route": "/clicknpay_integration",
# 		"has_permission": "clicknpay_integration.api.permission_query"
# 	}
# ]

# Includes in <head>
# ------------------
# include js, css files in header of desk.html
# app_include_css = "/assets/clicknpay_integration/css/clicknpay_integration.css"
# app_include_js = "/assets/clicknpay_integration/js/clicknpay_integration.js"

# include js, css files in header of web template
# web_include_css = "/assets/clicknpay_integration/css/clicknpay_integration.css"
# web_include_js = "/assets/clicknpay_integration/js/clicknpay_integration.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "clicknpay_integration/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include svg icons in desk.html
# app_include_icons = "clicknpay_integration/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "clicknpay_integration.utils.jinja_methods",
# 	"filters": "clicknpay_integration.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "clicknpay_integration.install.before_install"
# after_install = "clicknpay_integration.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "clicknpay_integration.uninstall.before_uninstall"
# after_uninstall = "clicknpay_integration.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "clicknpay_integration.utils.before_app_install"
# after_app_install = "clicknpay_integration.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "clicknpay_integration.utils.before_app_uninstall"
# after_app_uninstall = "clicknpay_integration.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "clicknpay_integration.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

#doc_events = {
 #   "Sales Invoice": {
       # "on_submit": "clicknpay_integration.api.create_payment_request"
   # }
#}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"clicknpay_integration.tasks.all"
# 	],
# 	"daily": [
# 		"clicknpay_integration.tasks.daily"
# 	],
# 	"hourly": [
# 		"clicknpay_integration.tasks.hourly"
# 	],
# 	"weekly": [
# 		"clicknpay_integration.tasks.weekly"
# 	],
# 	"monthly": [
# 		"clicknpay_integration.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "clicknpay_integration.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "clicknpay_integration.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the whitelisted method, to get
# generated docs
# def custom_function(data):
# 	return data

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["clicknpay_integration.utils.before_request"]
# after_request = ["clicknpay_integration.utils.after_request"]

# Job Events
# ----------
# before_job = ["clicknpay_integration.utils.before_job"]
# after_job = ["clicknpay_integration.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"clicknpay_integration.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType": 30  # days to retain logs
# }
