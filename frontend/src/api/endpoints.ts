import api from "./client";
import type {
  SSHAccount,
  Server,
  Plan,
  ActiveSession,
  AuditLog,
  DashboardData,
  PaginatedResponse,
  User,
  PublicAccountStatus,
} from "../lib/types";

// --- Auth ---
export const authLogin = (username: string, password: string) =>
  api.post<{ user: User; csrftoken: string }>("/auth/login/", { username, password });

export const authLogout = () => api.post("/auth/logout/");

export const authMe = () => api.get<User>("/auth/me/");

// --- Dashboard ---
export const getDashboard = () => api.get<DashboardData>("/dashboard/");

// --- Servers ---
export const getServers = (page = 1) =>
  api.get<PaginatedResponse<Server>>("/servers/", { params: { page } });

export const getServer = (id: number) => api.get<Server>(`/servers/${id}/`);

export const createServer = (data: Partial<Server>) =>
  api.post<Server>("/servers/", data);

export const updateServer = (id: number, data: Partial<Server>) =>
  api.patch<Server>(`/servers/${id}/`, data);

export const deleteServer = (id: number) => api.delete(`/servers/${id}/`);

export const triggerHealthCheck = (id: number) =>
  api.post(`/servers/${id}/health-check/`);

// --- Plans ---
export const getPlans = (page = 1) =>
  api.get<PaginatedResponse<Plan>>("/plans/", { params: { page } });

export const getPlan = (id: number) => api.get<Plan>(`/plans/${id}/`);

export const createPlan = (data: Partial<Plan>) =>
  api.post<Plan>("/plans/", data);

export const updatePlan = (id: number, data: Partial<Plan>) =>
  api.patch<Plan>(`/plans/${id}/`, data);

export const deletePlan = (id: number) => api.delete(`/plans/${id}/`);

// --- Accounts ---
export const getAccounts = (params?: Record<string, string | number>) =>
  api.get<PaginatedResponse<SSHAccount>>("/accounts/", { params });

export const getAccount = (id: number) =>
  api.get<SSHAccount>(`/accounts/${id}/`);

export const createAccount = (data: {
  username: string;
  plan_id: number;
  server_id?: number;
  password?: string;
  note?: string;
  duration_days?: number;
  bandwidth_limit_gb?: number;
  max_connections?: number;
}) => api.post<SSHAccount>("/create-user/", data);

export const updateAccount = (id: number, data: {
  duration_days?: number;
  bandwidth_limit_gb?: number;
  max_connections?: number;
  expire_date?: string;
  note?: string;
}) => api.patch<SSHAccount>(`/accounts/${id}/update/`, data);

export const bulkCreateAccounts = (data: {
  prefix: string;
  count: number;
  plan_id: number;
  server_id?: number;
}) => api.post<SSHAccount[]>("/bulk-create/", data);

export const deleteAccount = (id: number) =>
  api.post(`/delete-user/${id}/`);

export const suspendAccount = (id: number) =>
  api.post(`/suspend-user/${id}/`);

export const activateAccount = (id: number) =>
  api.post(`/activate-user/${id}/`);

export const extendAccount = (id: number, days: number) =>
  api.post(`/extend-user/${id}/`, { days });

export const resetPassword = (id: number) =>
  api.post<{ username: string; new_password: string }>(`/reset-password/${id}/`);

// --- Sessions ---
export const getSessions = (params?: Record<string, string | number>) =>
  api.get<PaginatedResponse<ActiveSession>>("/sessions/", { params });

// --- Logs ---
export const getLogs = (params?: Record<string, string | number>) =>
  api.get<PaginatedResponse<AuditLog>>("/logs/", { params });

// --- Public ---
export const getPublicStatus = (token: string) =>
  api.get<PublicAccountStatus>(`/public/status/${token}/`);

export const getPublicPlans = () =>
  api.get<Plan[]>("/public/plans/");
