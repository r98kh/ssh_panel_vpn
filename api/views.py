import logging

from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status, views
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.models import SSHAccount, ActiveSession, AuditLog
from accounts.services import (
    AccountError,
    activate_account,
    bulk_create_accounts,
    create_account,
    delete_account,
    extend_account,
    reset_password,
    suspend_account,
)
from plans.models import Plan
from servers.models import Server
from servers.tasks import check_single_server

from .serializers import (
    AccountUpdateSerializer,
    ActiveSessionSerializer,
    AuditLogSerializer,
    BulkCreateSerializer,
    CreateAccountSerializer,
    CreateShadowLinkAccountSerializer,
    ExtendAccountSerializer,
    PaymentWebhookSerializer,
    PlanSerializer,
    PublicAccountStatusSerializer,
    ShadowLinkAccountSerializer,
    ShadowLinkClientConfigSerializer,
    SSHAccountSerializer,
    ServerCreateSerializer,
    ServerSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Server endpoints
# ---------------------------------------------------------------------------

class ServerListView(generics.ListCreateAPIView):
    queryset = Server.objects.all()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ServerCreateSerializer
        return ServerSerializer


class ServerDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Server.objects.all()
    serializer_class = ServerSerializer


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def server_health_check(request, pk):
    server = get_object_or_404(Server, pk=pk)
    check_single_server.delay(server.id)
    return Response({"detail": "Health check dispatched."})


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def server_set_status(request, pk):
    server = get_object_or_404(Server, pk=pk)
    new_status = request.data.get("status", "active")
    valid = [c[0] for c in Server.Status.choices]
    if new_status not in valid:
        return Response({"detail": f"Invalid status. Choose from: {valid}"}, status=status.HTTP_400_BAD_REQUEST)
    server.status = new_status
    server.save(update_fields=["status", "updated_at"])
    return Response({"detail": f"Server status set to {new_status}.", "status": new_status})


# ---------------------------------------------------------------------------
# Plan endpoints
# ---------------------------------------------------------------------------

class PlanListView(generics.ListCreateAPIView):
    queryset = Plan.objects.filter(is_active=True)
    serializer_class = PlanSerializer


class PlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer


# ---------------------------------------------------------------------------
# Account endpoints
# ---------------------------------------------------------------------------

class AccountListView(generics.ListAPIView):
    serializer_class = SSHAccountSerializer
    filterset_fields = ["status", "server", "plan"]
    search_fields = ["username", "note"]
    ordering_fields = ["created_at", "expire_date", "username"]

    def get_queryset(self):
        return SSHAccount.objects.select_related("server", "plan").exclude(
            status=SSHAccount.Status.DELETED
        )


class AccountDetailView(generics.RetrieveAPIView):
    queryset = SSHAccount.objects.select_related("server", "plan")
    serializer_class = SSHAccountSerializer


class AccountUpdateView(views.APIView):
    def patch(self, request, pk):
        account = get_object_or_404(SSHAccount, pk=pk)
        ser = AccountUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        if "duration_days" in data:
            from datetime import timedelta as td
            account.expire_date = timezone.now() + td(days=data["duration_days"])
        if "expire_date" in data:
            account.expire_date = data["expire_date"]
        if "bandwidth_limit_gb" in data:
            account.bandwidth_limit_gb = data["bandwidth_limit_gb"]
        if "max_connections" in data:
            account.max_connections = data["max_connections"]
        if "note" in data:
            account.note = data["note"]

        account.save()

        from servers.ssh import get_ssh_manager
        try:
            with get_ssh_manager(account.server) as ssh:
                if "duration_days" in data or "expire_date" in data:
                    ssh.set_expiry(account.username, account.expire_date.strftime("%Y-%m-%d"))
                if "max_connections" in data:
                    ssh.set_max_logins(account.username, account.max_connections)
        except Exception:
            pass

        return Response(SSHAccountSerializer(account).data)


class CreateAccountView(views.APIView):
    def post(self, request):
        ser = CreateAccountSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        plan = get_object_or_404(Plan, pk=data["plan_id"], is_active=True)
        server = None
        if "server_id" in data:
            server = get_object_or_404(Server, pk=data["server_id"])

        try:
            account = create_account(
                username=data["username"],
                plan=plan,
                server=server,
                password=data.get("password"),
                admin_user=request.user,
                note=data.get("note", ""),
                duration_days=data.get("duration_days"),
                bandwidth_limit_gb=data.get("bandwidth_limit_gb"),
                max_connections=data.get("max_connections"),
            )
        except AccountError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            SSHAccountSerializer(account).data,
            status=status.HTTP_201_CREATED,
        )


class BulkCreateAccountView(views.APIView):
    def post(self, request):
        ser = BulkCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        plan = get_object_or_404(Plan, pk=data["plan_id"], is_active=True)
        server = None
        if "server_id" in data:
            server = get_object_or_404(Server, pk=data["server_id"])

        try:
            accounts = bulk_create_accounts(
                prefix=data["prefix"],
                count=data["count"],
                plan=plan,
                server=server,
                admin_user=request.user,
            )
        except AccountError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            SSHAccountSerializer(accounts, many=True).data,
            status=status.HTTP_201_CREATED,
        )


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def delete_account_view(request, pk):
    account = get_object_or_404(SSHAccount, pk=pk)
    try:
        delete_account(account, admin_user=request.user)
    except AccountError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"detail": "Account deleted."})


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def suspend_account_view(request, pk):
    account = get_object_or_404(SSHAccount, pk=pk)
    try:
        suspend_account(account, admin_user=request.user)
    except AccountError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"detail": "Account suspended."})


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def activate_account_view(request, pk):
    account = get_object_or_404(SSHAccount, pk=pk)
    try:
        activate_account(account, admin_user=request.user)
    except AccountError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"detail": "Account activated."})


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def extend_account_view(request, pk):
    account = get_object_or_404(SSHAccount, pk=pk)
    ser = ExtendAccountSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    try:
        extend_account(account, days=ser.validated_data["days"], admin_user=request.user)
    except AccountError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(SSHAccountSerializer(account).data)


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def reset_password_view(request, pk):
    account = get_object_or_404(SSHAccount, pk=pk)
    try:
        new_pw = reset_password(account, admin_user=request.user)
    except AccountError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"username": account.username, "new_password": new_pw})


# ---------------------------------------------------------------------------
# Sessions & Logs
# ---------------------------------------------------------------------------

class ActiveSessionListView(generics.ListAPIView):
    serializer_class = ActiveSessionSerializer
    queryset = ActiveSession.objects.select_related("account", "account__server").all()
    filterset_fields = ["account__server"]


class AuditLogListView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.select_related("account", "admin_user").all()
    filterset_fields = ["action", "admin_user"]
    search_fields = ["detail", "account__username"]


# ---------------------------------------------------------------------------
# Payment webhook (mock)
# ---------------------------------------------------------------------------

class PaymentWebhookView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = PaymentWebhookSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        if data["status"] != "paid":
            return Response({"detail": "Payment not confirmed."}, status=status.HTTP_200_OK)

        plan = get_object_or_404(Plan, pk=data["plan_id"])
        existing = SSHAccount.objects.filter(
            username=data["username"],
            status__in=[SSHAccount.Status.ACTIVE, SSHAccount.Status.EXPIRED],
        ).first()

        if existing:
            extend_account(existing, days=plan.duration_days)
            return Response({"detail": f"Extended {existing.username} by {plan.duration_days}d."})

        try:
            account = create_account(username=data["username"], plan=plan)
        except AccountError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            SSHAccountSerializer(account).data,
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def dashboard_summary(request):
    from django.db.models import Count, Q, Sum
    total = SSHAccount.objects.exclude(status=SSHAccount.Status.DELETED).count()
    active = SSHAccount.objects.filter(status=SSHAccount.Status.ACTIVE).count()
    expired = SSHAccount.objects.filter(status=SSHAccount.Status.EXPIRED).count()
    suspended = SSHAccount.objects.filter(status=SSHAccount.Status.SUSPENDED).count()
    sessions = ActiveSession.objects.count()
    servers = Server.objects.aggregate(
        total=Count("id"),
        online=Count("id", filter=Q(status=Server.Status.ACTIVE)),
        down=Count("id", filter=Q(status=Server.Status.DOWN)),
    )
    recent_logs = AuditLogSerializer(
        AuditLog.objects.select_related("account", "admin_user")[:10],
        many=True,
    ).data
    return Response({
        "accounts": {"total": total, "active": active, "expired": expired, "suspended": suspended},
        "active_sessions": sessions,
        "servers": servers,
        "recent_logs": recent_logs,
    })


# ---------------------------------------------------------------------------
# Auth endpoints (session-based for SPA)
# ---------------------------------------------------------------------------

class AuthLoginView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get("username", "")
        password = request.data.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not user.is_staff:
            return Response(
                {"detail": "Access denied. Admin privileges required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        login(request, user)
        return Response({
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_superuser": user.is_superuser,
            },
            "csrftoken": get_token(request),
        })


class AuthLogoutView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"detail": "Logged out."})


class AuthMeView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
        })


# ---------------------------------------------------------------------------
# Public endpoints (no auth)
# ---------------------------------------------------------------------------

class PublicAccountStatusView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        account = get_object_or_404(
            SSHAccount.objects.select_related("server", "plan"),
            access_token=token,
        )
        return Response(PublicAccountStatusSerializer(account).data)


class PublicPlanListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PlanSerializer
    queryset = Plan.objects.filter(is_active=True)
    pagination_class = None


# ---------------------------------------------------------------------------
# ShadowLink endpoints
# ---------------------------------------------------------------------------

class ShadowLinkAccountListView(generics.ListAPIView):
    serializer_class = ShadowLinkAccountSerializer

    def get_queryset(self):
        return (
            SSHAccount.objects
            .filter(protocol_type="shadowlink")
            .select_related("server", "plan")
            .exclude(status=SSHAccount.Status.DELETED)
        )


class CreateShadowLinkAccountView(views.APIView):
    def post(self, request):
        ser = CreateShadowLinkAccountSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        plan = get_object_or_404(Plan, pk=data["plan_id"], is_active=True)
        server = None
        if "server_id" in data:
            server = get_object_or_404(Server, pk=data["server_id"])

        try:
            account = create_account(
                username=data["username"],
                plan=plan,
                server=server,
                admin_user=request.user,
                note=data.get("note", ""),
                duration_days=data.get("duration_days"),
                max_connections=data.get("max_connections"),
                protocol_type="shadowlink",
            )
        except AccountError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            ShadowLinkAccountSerializer(account).data,
            status=status.HTTP_201_CREATED,
        )


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def shadowlink_client_config(request, token):
    """Public endpoint: download ShadowLink client config by auth token."""
    account = get_object_or_404(
        SSHAccount.objects.select_related("server"),
        auth_token=token,
        protocol_type="shadowlink",
    )

    if account.status not in (SSHAccount.Status.ACTIVE,):
        return Response(
            {"detail": "Account is not active."},
            status=status.HTTP_403_FORBIDDEN,
        )

    from servers.shadowlink import ShadowLinkManager
    config = ShadowLinkManager.generate_client_config(account, account.server)
    return Response(config)


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def shadowlink_deploy_server(request, pk):
    """Deploy ShadowLink binary and config to a server node."""
    server = get_object_or_404(Server, pk=pk, protocol_type="shadowlink")
    binary_path = request.data.get("binary_path", "")

    if not binary_path:
        return Response(
            {"detail": "binary_path is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from servers.shadowlink import get_shadowlink_manager, ShadowLinkError
    mgr = get_shadowlink_manager(server)
    try:
        mgr.full_deploy(binary_path)
    except ShadowLinkError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"detail": "ShadowLink deployed successfully."})


@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def shadowlink_server_status(request, pk):
    """Check ShadowLink process status on a server."""
    server = get_object_or_404(Server, pk=pk, protocol_type="shadowlink")

    from servers.shadowlink import get_shadowlink_manager, ShadowLinkError
    mgr = get_shadowlink_manager(server)
    try:
        svc_status = mgr.service_status()
        bridge_status = mgr.health_check()
        return Response({
            "service": svc_status,
            "bridge": bridge_status,
        })
    except ShadowLinkError as e:
        return Response({
            "service": mgr.service_status() if True else {},
            "bridge": {"status": "unreachable", "error": str(e)},
        })
    except Exception as e:
        return Response(
            {"detail": f"Status check failed: {e}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
