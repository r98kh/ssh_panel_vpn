import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Users,
  Plus,
  Search,
  Ban,
  Play,
  Trash2,
  CalendarPlus,
  KeyRound,
  Eye,
  Copy,
  Layers,
} from "lucide-react";
import {
  getAccounts,
  createAccount,
  bulkCreateAccounts,
  deleteAccount,
  suspendAccount,
  activateAccount,
  extendAccount,
  resetPassword,
  getPlans,
  getServers,
} from "../api/endpoints";
import type { SSHAccount, Plan, Server } from "../lib/types";
import { useFetch } from "../hooks/useFetch";
import { useToast } from "../context/ToastContext";
import StatusBadge from "../components/StatusBadge";
import Modal from "../components/Modal";
import ConfirmDialog from "../components/ConfirmDialog";
import Spinner from "../components/Spinner";
import EmptyState from "../components/EmptyState";
import { formatDate } from "../lib/utils";

export default function AccountsPage() {
  const { toast } = useToast();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const { data, loading, refetch } = useFetch(
    () => getAccounts({ page, search: search || undefined, status: statusFilter || undefined } as any),
    [page, search, statusFilter],
  );
  const { data: plansData } = useFetch(() => getPlans(1));
  const { data: serversData } = useFetch(() => getServers(1));

  const plans: Plan[] = plansData?.results || [];
  const servers: Server[] = serversData?.results || [];

  const [createOpen, setCreateOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [extendOpen, setExtendOpen] = useState<number | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [newPassword, setNewPassword] = useState<{ username: string; password: string } | null>(null);

  const [createForm, setCreateForm] = useState({ username: "", plan_id: "", server_id: "", password: "", note: "", duration_days: "", bandwidth_limit_gb: "", max_connections: "" });
  const [bulkForm, setBulkForm] = useState({ prefix: "", count: "5", plan_id: "", server_id: "" });
  const [extendDays, setExtendDays] = useState("30");

  const handleCreate = async () => {
    try {
      setActionLoading(true);
      await createAccount({
        username: createForm.username,
        plan_id: Number(createForm.plan_id),
        server_id: createForm.server_id ? Number(createForm.server_id) : undefined,
        password: createForm.password || undefined,
        note: createForm.note,
        duration_days: createForm.duration_days ? Number(createForm.duration_days) : undefined,
        bandwidth_limit_gb: createForm.bandwidth_limit_gb ? Number(createForm.bandwidth_limit_gb) : undefined,
        max_connections: createForm.max_connections ? Number(createForm.max_connections) : undefined,
      });
      toast("success", "اکانت ایجاد شد");
      setCreateOpen(false);
      refetch();
    } catch (err: any) {
      toast("error", err.response?.data?.detail || "خطا");
    } finally {
      setActionLoading(false);
    }
  };

  const handleBulkCreate = async () => {
    try {
      setActionLoading(true);
      const result = await bulkCreateAccounts({
        prefix: bulkForm.prefix,
        count: Number(bulkForm.count),
        plan_id: Number(bulkForm.plan_id),
        server_id: bulkForm.server_id ? Number(bulkForm.server_id) : undefined,
      });
      toast("success", `${result.data.length} اکانت ایجاد شد`);
      setBulkOpen(false);
      refetch();
    } catch (err: any) {
      toast("error", err.response?.data?.detail || "خطا");
    } finally {
      setActionLoading(false);
    }
  };

  const handleSuspend = async (id: number) => {
    try {
      await suspendAccount(id);
      toast("success", "اکانت معلق شد");
      refetch();
    } catch (err: any) {
      toast("error", err.response?.data?.detail || "خطا");
    }
  };

  const handleActivate = async (id: number) => {
    try {
      await activateAccount(id);
      toast("success", "اکانت فعال شد");
      refetch();
    } catch (err: any) {
      toast("error", err.response?.data?.detail || "خطا");
    }
  };

  const handleExtend = async () => {
    if (!extendOpen) return;
    try {
      setActionLoading(true);
      await extendAccount(extendOpen, Number(extendDays));
      toast("success", `${extendDays} روز تمدید شد`);
      setExtendOpen(null);
      refetch();
    } catch (err: any) {
      toast("error", err.response?.data?.detail || "خطا");
    } finally {
      setActionLoading(false);
    }
  };

  const handleResetPassword = async (id: number) => {
    try {
      const res = await resetPassword(id);
      setNewPassword({ username: res.data.username, password: res.data.new_password });
      toast("success", "رمز عبور بازنشانی شد");
    } catch (err: any) {
      toast("error", err.response?.data?.detail || "خطا");
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    setActionLoading(true);
    try {
      await deleteAccount(deleteId);
      toast("success", "اکانت حذف شد");
      setDeleteId(null);
      refetch();
    } catch (err: any) {
      toast("error", err.response?.data?.detail || "خطا");
    } finally {
      setActionLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast("success", "کپی شد");
  };

  if (loading && !data) return <div className="flex justify-center py-20"><Spinner className="w-10 h-10" /></div>;

  const accounts: SSHAccount[] = data?.results || [];
  const totalCount = data?.count || 0;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">اکانت‌ها</h1>
          <p className="text-gray-500 text-sm mt-1">{totalCount} اکانت</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setBulkOpen(true)} className="btn-secondary flex items-center gap-2">
            <Layers className="w-4 h-4" />
            ایجاد گروهی
          </button>
          <button
            onClick={() => {
              setCreateForm({ username: "", plan_id: plans[0]?.id?.toString() || "", server_id: "", password: "", note: "" });
              setCreateOpen(true);
            }}
            className="btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            اکانت جدید
          </button>
        </div>
      </div>

      <div className="flex gap-3 mb-4">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            className="input pr-10"
            placeholder="جستجو..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            dir="ltr"
          />
        </div>
        <select
          className="input w-40"
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
        >
          <option value="">همه وضعیت‌ها</option>
          <option value="active">فعال</option>
          <option value="suspended">معلق</option>
          <option value="expired">منقضی</option>
        </select>
      </div>

      {accounts.length === 0 ? (
        <EmptyState icon={<Users className="w-12 h-12" />} title="اکانتی یافت نشد" />
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500">
                  <th className="text-right py-3 px-3 font-medium">کاربر</th>
                  <th className="text-right py-3 px-3 font-medium">سرور</th>
                  <th className="text-right py-3 px-3 font-medium">پلن</th>
                  <th className="text-right py-3 px-3 font-medium">وضعیت</th>
                  <th className="text-right py-3 px-3 font-medium">انقضا</th>
                  <th className="text-right py-3 px-3 font-medium">روز مانده</th>
                  <th className="text-right py-3 px-3 font-medium">عملیات</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((a) => (
                  <tr key={a.id} className="border-b border-gray-800/50 hover:bg-gray-900/50">
                    <td className="py-3 px-3">
                      <Link to={`/accounts/${a.id}`} className="text-indigo-400 hover:text-indigo-300 font-medium" dir="ltr">
                        {a.username}
                      </Link>
                    </td>
                    <td className="py-3 px-3 text-gray-400" dir="ltr">{a.server_name}</td>
                    <td className="py-3 px-3 text-gray-400">{a.plan_name || "—"}</td>
                    <td className="py-3 px-3"><StatusBadge status={a.status} /></td>
                    <td className="py-3 px-3 text-gray-400 text-xs" dir="ltr">{formatDate(a.expire_date)}</td>
                    <td className="py-3 px-3">
                      <span className={a.days_remaining <= 3 ? "text-red-400 font-bold" : "text-gray-400"}>
                        {a.days_remaining}
                      </span>
                    </td>
                    <td className="py-3 px-3">
                      <div className="flex gap-1">
                        <Link to={`/accounts/${a.id}`} className="p-1.5 rounded hover:bg-gray-800 text-gray-400 hover:text-white" title="جزئیات">
                          <Eye className="w-4 h-4" />
                        </Link>
                        {a.status === "active" ? (
                          <button onClick={() => handleSuspend(a.id)} className="p-1.5 rounded hover:bg-gray-800 text-gray-400 hover:text-amber-400" title="تعلیق">
                            <Ban className="w-4 h-4" />
                          </button>
                        ) : a.status !== "deleted" ? (
                          <button onClick={() => handleActivate(a.id)} className="p-1.5 rounded hover:bg-gray-800 text-gray-400 hover:text-emerald-400" title="فعال‌سازی">
                            <Play className="w-4 h-4" />
                          </button>
                        ) : null}
                        <button onClick={() => { setExtendOpen(a.id); setExtendDays("30"); }} className="p-1.5 rounded hover:bg-gray-800 text-gray-400 hover:text-blue-400" title="تمدید">
                          <CalendarPlus className="w-4 h-4" />
                        </button>
                        <button onClick={() => handleResetPassword(a.id)} className="p-1.5 rounded hover:bg-gray-800 text-gray-400 hover:text-purple-400" title="بازنشانی رمز">
                          <KeyRound className="w-4 h-4" />
                        </button>
                        <button onClick={() => setDeleteId(a.id)} className="p-1.5 rounded hover:bg-gray-800 text-gray-400 hover:text-red-400" title="حذف">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalCount > 25 && (
            <div className="flex justify-center gap-2 mt-4">
              <button className="btn-secondary btn-sm" disabled={!data?.previous} onClick={() => setPage((p) => p - 1)}>قبلی</button>
              <span className="text-gray-500 text-sm py-1.5">صفحه {page}</span>
              <button className="btn-secondary btn-sm" disabled={!data?.next} onClick={() => setPage((p) => p + 1)}>بعدی</button>
            </div>
          )}
        </>
      )}

      {/* Create Modal */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="ایجاد اکانت">
        <div className="space-y-4">
          <div>
            <label className="label">نام کاربری</label>
            <input className="input" dir="ltr" value={createForm.username} onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })} placeholder="user123" />
          </div>
          <div>
            <label className="label">پلن</label>
            <select className="input" value={createForm.plan_id} onChange={(e) => setCreateForm({ ...createForm, plan_id: e.target.value })}>
              <option value="">انتخاب پلن</option>
              {plans.map((p) => <option key={p.id} value={p.id}>{p.name} - {p.duration_days} روز</option>)}
            </select>
          </div>
          <div>
            <label className="label">سرور (اختیاری - خودکار انتخاب می‌شود)</label>
            <select className="input" value={createForm.server_id} onChange={(e) => setCreateForm({ ...createForm, server_id: e.target.value })}>
              <option value="">خودکار</option>
              {servers.filter((s) => s.is_available).map((s) => <option key={s.id} value={s.id}>{s.name} ({s.ip_address})</option>)}
            </select>
          </div>
          <div>
            <label className="label">رمز عبور (اختیاری)</label>
            <input className="input" dir="ltr" value={createForm.password} onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })} placeholder="خودکار تولید می‌شود" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="label">مدت (روز)</label>
              <input className="input" dir="ltr" type="number" value={createForm.duration_days} onChange={(e) => setCreateForm({ ...createForm, duration_days: e.target.value })} placeholder="از پلن" />
            </div>
            <div>
              <label className="label">حجم (GB)</label>
              <input className="input" dir="ltr" type="number" value={createForm.bandwidth_limit_gb} onChange={(e) => setCreateForm({ ...createForm, bandwidth_limit_gb: e.target.value })} placeholder="از پلن" />
            </div>
            <div>
              <label className="label">کانکشن</label>
              <input className="input" dir="ltr" type="number" value={createForm.max_connections} onChange={(e) => setCreateForm({ ...createForm, max_connections: e.target.value })} placeholder="از پلن" />
            </div>
          </div>
          <div>
            <label className="label">یادداشت</label>
            <input className="input" value={createForm.note} onChange={(e) => setCreateForm({ ...createForm, note: e.target.value })} />
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button className="btn-secondary" onClick={() => setCreateOpen(false)}>انصراف</button>
            <button className="btn-primary" onClick={handleCreate} disabled={actionLoading}>{actionLoading ? "..." : "ایجاد"}</button>
          </div>
        </div>
      </Modal>

      {/* Bulk Create Modal */}
      <Modal open={bulkOpen} onClose={() => setBulkOpen(false)} title="ایجاد گروهی اکانت">
        <div className="space-y-4">
          <div>
            <label className="label">پیشوند</label>
            <input className="input" dir="ltr" value={bulkForm.prefix} onChange={(e) => setBulkForm({ ...bulkForm, prefix: e.target.value })} placeholder="user" />
          </div>
          <div>
            <label className="label">تعداد</label>
            <input className="input" dir="ltr" type="number" min="1" max="500" value={bulkForm.count} onChange={(e) => setBulkForm({ ...bulkForm, count: e.target.value })} />
          </div>
          <div>
            <label className="label">پلن</label>
            <select className="input" value={bulkForm.plan_id} onChange={(e) => setBulkForm({ ...bulkForm, plan_id: e.target.value })}>
              <option value="">انتخاب پلن</option>
              {plans.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">سرور (اختیاری)</label>
            <select className="input" value={bulkForm.server_id} onChange={(e) => setBulkForm({ ...bulkForm, server_id: e.target.value })}>
              <option value="">خودکار</option>
              {servers.filter((s) => s.is_available).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button className="btn-secondary" onClick={() => setBulkOpen(false)}>انصراف</button>
            <button className="btn-primary" onClick={handleBulkCreate} disabled={actionLoading}>{actionLoading ? "..." : "ایجاد"}</button>
          </div>
        </div>
      </Modal>

      {/* Extend Modal */}
      <Modal open={extendOpen !== null} onClose={() => setExtendOpen(null)} title="تمدید اکانت">
        <div className="space-y-4">
          <div>
            <label className="label">تعداد روز</label>
            <input className="input" dir="ltr" type="number" min="1" max="365" value={extendDays} onChange={(e) => setExtendDays(e.target.value)} />
          </div>
          <div className="flex gap-3 justify-end">
            <button className="btn-secondary" onClick={() => setExtendOpen(null)}>انصراف</button>
            <button className="btn-primary" onClick={handleExtend} disabled={actionLoading}>{actionLoading ? "..." : "تمدید"}</button>
          </div>
        </div>
      </Modal>

      {/* New Password Modal */}
      <Modal open={newPassword !== null} onClose={() => setNewPassword(null)} title="رمز عبور جدید">
        {newPassword && (
          <div className="space-y-3">
            <p className="text-gray-400 text-sm">رمز عبور جدید برای <span className="text-white font-medium" dir="ltr">{newPassword.username}</span>:</p>
            <div className="flex items-center gap-2 bg-gray-800 rounded-lg px-4 py-3">
              <code className="text-emerald-400 flex-1 text-lg" dir="ltr">{newPassword.password}</code>
              <button onClick={() => copyToClipboard(newPassword.password)} className="text-gray-400 hover:text-white">
                <Copy className="w-4 h-4" />
              </button>
            </div>
            <p className="text-amber-400 text-xs">این رمز را ذخیره کنید. بعدا قابل مشاهده نخواهد بود.</p>
          </div>
        )}
      </Modal>

      {/* Delete Confirm */}
      <ConfirmDialog
        open={deleteId !== null}
        onClose={() => setDeleteId(null)}
        onConfirm={handleDelete}
        title="حذف اکانت"
        message="آیا از حذف این اکانت اطمینان دارید؟ این عمل از سرور نیز حذف خواهد شد."
        confirmLabel="حذف"
        danger
        loading={actionLoading}
      />
    </div>
  );
}
