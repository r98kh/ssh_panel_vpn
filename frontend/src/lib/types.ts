export interface Server {
  id: number;
  name: string;
  ip_address: string;
  ssh_port: number;
  status: "active" | "maintenance" | "full" | "down";
  location: string;
  max_users: number;
  current_user_count: number;
  is_available: boolean;
  cpu_usage: number;
  ram_usage: number;
  disk_usage: number;
  uptime_seconds: number;
  last_health_check: string | null;
  created_at: string;
}

export interface Plan {
  id: number;
  name: string;
  duration_days: number;
  price: string;
  currency: string;
  max_connections: number;
  bandwidth_limit_gb: number;
  is_active: boolean;
  description: string;
  created_at: string;
}

export interface SSHAccount {
  id: number;
  username: string;
  password_display: string;
  server: number;
  server_name: string;
  server_ip: string;
  server_ssh_port: number;
  plan: number | null;
  plan_name: string | null;
  status: "active" | "suspended" | "expired" | "deleted";
  expire_date: string;
  max_connections: number;
  bandwidth_limit_gb: number;
  bandwidth_used_gb: number;
  days_remaining: number;
  is_expired: boolean;
  access_token: string;
  note: string;
  created_at: string;
}

export interface ActiveSession {
  id: number;
  username: string;
  server_ip: string;
  pid: number;
  client_ip: string | null;
  connected_since: string;
}

export interface AuditLog {
  id: number;
  action: string;
  account: number | null;
  account_username: string | null;
  admin_user: number | null;
  admin_username: string | null;
  detail: string;
  created_at: string;
}

export interface DashboardData {
  accounts: {
    total: number;
    active: number;
    expired: number;
    suspended: number;
  };
  active_sessions: number;
  servers: {
    total: number;
    online: number;
    down: number;
  };
  recent_logs: AuditLog[];
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface User {
  id: number;
  username: string;
  email: string;
  is_staff: boolean;
  is_superuser: boolean;
}

export interface PublicAccountStatus {
  username: string;
  server_ip: string;
  server_ssh_port: number;
  server_location: string;
  plan_name: string | null;
  status: string;
  expire_date: string;
  max_connections: number;
  bandwidth_limit_gb: number;
  bandwidth_used_gb: number;
  days_remaining: number;
  is_expired: boolean;
  created_at: string;
}
