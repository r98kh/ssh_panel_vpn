import { useState } from "react";
import { Server as ServerIcon, Plus, RefreshCw, Trash2, Edit2 } from "lucide-react";
import { getServers, createServer, updateServer, deleteServer, triggerHealthCheck } from "../api/endpoints";
import type { Server } from "../lib/types";
import { useFetch } from "../hooks/useFetch";
import { useToast } from "../context/ToastContext";
import StatusBadge from "../components/StatusBadge";
import ProgressBar from "../components/ProgressBar";
import Modal from "../components/Modal";
import ConfirmDialog from "../components/ConfirmDialog";
import Spinner from "../components/Spinner";
import EmptyState from "../components/EmptyState";
import { formatUptime } from "../lib/utils";

export default function ServersPage() {
  const { data, loading, refetch } = useFetch(() => getServers(1));
  const { toast } = useToast();
  const [modalOpen, setModalOpen] = useState(false);
  const [editServer, setEditServer] = useState<Server | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [form, setForm] = useState({
    name: "",
    ip_address: "",
    ssh_port: "22",
    ssh_user: "root",
    ssh_key_path: "",
    location: "",
    max_users: "100",
  });

  const openCreate = () => {
    setEditServer(null);
    setForm({ name: "", ip_address: "", ssh_port: "22", ssh_user: "root", ssh_key_path: "", location: "", max_users: "100" });
    setModalOpen(true);
  };

  const openEdit = (s: Server) => {
    setEditServer(s);
    setForm({
      name: s.name,
      ip_address: s.ip_address,
      ssh_port: String(s.ssh_port),
      ssh_user: "",
      ssh_key_path: "",
      location: s.location,
      max_users: String(s.max_users),
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const payload = {
        name: form.name,
        ip_address: form.ip_address,
        ssh_port: Number(form.ssh_port),
        ssh_user: form.ssh_user,
        ssh_key_path: form.ssh_key_path,
        location: form.location,
        max_users: Number(form.max_users),
      };
      if (editServer) {
        await updateServer(editServer.id, { name: form.name, location: form.location, max_users: Number(form.max_users) });
        toast("success", "سرور بروزرسانی شد");
      } else {
        await createServer(payload);
        toast("success", "سرور اضافه شد");
      }
      setModalOpen(false);
      refetch();
    } catch (err: any) {
      toast("error", err.response?.data?.detail || "خطا در عملیات");
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    setDeleting(true);
    try {
      await deleteServer(deleteId);
      toast("success", "سرور حذف شد");
      setDeleteId(null);
      refetch();
    } catch (err: any) {
      toast("error", err.response?.data?.detail || "خطا در حذف");
    } finally {
      setDeleting(false);
    }
  };

  const handleHealthCheck = async (id: number) => {
    try {
      await triggerHealthCheck(id);
      toast("info", "بررسی سلامت ارسال شد");
    } catch {
      toast("error", "خطا");
    }
  };

  if (loading) return <div className="flex justify-center py-20"><Spinner className="w-10 h-10" /></div>;

  const servers = data?.results || [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">سرورها</h1>
          <p className="text-gray-500 text-sm mt-1">{servers.length} سرور</p>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          افزودن سرور
        </button>
      </div>

      {servers.length === 0 ? (
        <EmptyState
          icon={<ServerIcon className="w-12 h-12" />}
          title="سروری وجود ندارد"
          description="اولین سرور خود را اضافه کنید"
          action={<button onClick={openCreate} className="btn-primary btn-sm">افزودن سرور</button>}
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {servers.map((s) => (
            <div key={s.id} className="card">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-white">{s.name}</h3>
                  <p className="text-sm text-gray-500" dir="ltr">{s.ip_address}:{s.ssh_port}</p>
                </div>
                <StatusBadge status={s.status} />
              </div>

              <div className="text-xs text-gray-500 mb-3">
                {s.location && <span>{s.location} · </span>}
                <span>کاربران: {s.current_user_count}/{s.max_users}</span>
                {s.uptime_seconds > 0 && <span> · آپتایم: {formatUptime(s.uptime_seconds)}</span>}
              </div>

              <div className="space-y-2 mb-4">
                <ProgressBar value={s.cpu_usage} label="CPU" size="sm" />
                <ProgressBar value={s.ram_usage} label="RAM" size="sm" />
                <ProgressBar value={s.disk_usage} label="Disk" size="sm" />
              </div>

              <div className="flex gap-2">
                <button onClick={() => handleHealthCheck(s.id)} className="btn-secondary btn-sm flex items-center gap-1 flex-1">
                  <RefreshCw className="w-3.5 h-3.5" /> بررسی
                </button>
                <button onClick={() => openEdit(s)} className="btn-secondary btn-sm flex items-center gap-1 flex-1">
                  <Edit2 className="w-3.5 h-3.5" /> ویرایش
                </button>
                <button onClick={() => setDeleteId(s.id)} className="btn-danger btn-sm flex items-center gap-1">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editServer ? "ویرایش سرور" : "افزودن سرور"}>
        <div className="space-y-4">
          <div>
            <label className="label">نام</label>
            <input className="input" dir="ltr" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          {!editServer && (
            <>
              <div>
                <label className="label">آدرس IP</label>
                <input className="input" dir="ltr" value={form.ip_address} onChange={(e) => setForm({ ...form, ip_address: e.target.value })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">پورت SSH</label>
                  <input className="input" dir="ltr" type="number" value={form.ssh_port} onChange={(e) => setForm({ ...form, ssh_port: e.target.value })} />
                </div>
                <div>
                  <label className="label">کاربر SSH</label>
                  <input className="input" dir="ltr" value={form.ssh_user} onChange={(e) => setForm({ ...form, ssh_user: e.target.value })} />
                </div>
              </div>
              <div>
                <label className="label">مسیر کلید SSH</label>
                <input className="input" dir="ltr" value={form.ssh_key_path} onChange={(e) => setForm({ ...form, ssh_key_path: e.target.value })} placeholder="/root/.ssh/id_rsa" />
              </div>
            </>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">موقعیت</label>
              <input className="input" dir="ltr" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} placeholder="Frankfurt, DE" />
            </div>
            <div>
              <label className="label">حداکثر کاربر</label>
              <input className="input" dir="ltr" type="number" value={form.max_users} onChange={(e) => setForm({ ...form, max_users: e.target.value })} />
            </div>
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button className="btn-secondary" onClick={() => setModalOpen(false)}>انصراف</button>
            <button className="btn-primary" onClick={handleSubmit}>{editServer ? "بروزرسانی" : "ایجاد"}</button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={deleteId !== null}
        onClose={() => setDeleteId(null)}
        onConfirm={handleDelete}
        title="حذف سرور"
        message="آیا از حذف این سرور اطمینان دارید؟ اکانت‌های مرتبط ممکن است تحت تاثیر قرار بگیرند."
        confirmLabel="حذف"
        danger
        loading={deleting}
      />
    </div>
  );
}
