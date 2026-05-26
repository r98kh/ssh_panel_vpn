from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    # Auth
    path("auth/login/", views.AuthLoginView.as_view(), name="auth-login"),
    path("auth/logout/", views.AuthLogoutView.as_view(), name="auth-logout"),
    path("auth/me/", views.AuthMeView.as_view(), name="auth-me"),

    # Dashboard
    path("dashboard/", views.dashboard_summary, name="dashboard-summary"),

    # Servers
    path("servers/", views.ServerListView.as_view(), name="server-list"),
    path("servers/<int:pk>/", views.ServerDetailView.as_view(), name="server-detail"),
    path("servers/<int:pk>/health-check/", views.server_health_check, name="server-health"),

    # Plans
    path("plans/", views.PlanListView.as_view(), name="plan-list"),
    path("plans/<int:pk>/", views.PlanDetailView.as_view(), name="plan-detail"),

    # Accounts
    path("accounts/", views.AccountListView.as_view(), name="account-list"),
    path("accounts/<int:pk>/", views.AccountDetailView.as_view(), name="account-detail"),
    path("create-user/", views.CreateAccountView.as_view(), name="create-account"),
    path("bulk-create/", views.BulkCreateAccountView.as_view(), name="bulk-create"),
    path("delete-user/<int:pk>/", views.delete_account_view, name="delete-account"),
    path("suspend-user/<int:pk>/", views.suspend_account_view, name="suspend-account"),
    path("activate-user/<int:pk>/", views.activate_account_view, name="activate-account"),
    path("extend-user/<int:pk>/", views.extend_account_view, name="extend-account"),
    path("reset-password/<int:pk>/", views.reset_password_view, name="reset-password"),

    # Sessions & Logs
    path("sessions/", views.ActiveSessionListView.as_view(), name="session-list"),
    path("logs/", views.AuditLogListView.as_view(), name="log-list"),

    # Payment webhook
    path("webhook/payment/", views.PaymentWebhookView.as_view(), name="payment-webhook"),

    # Public (no auth required)
    path("public/status/<uuid:token>/", views.PublicAccountStatusView.as_view(), name="public-status"),
    path("public/plans/", views.PublicPlanListView.as_view(), name="public-plans"),
]
