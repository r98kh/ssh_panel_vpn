import { useState } from "react";
import { CreditCard, Plus, Edit2, Trash2, ToggleLeft, ToggleRight } from "lucide-react";
import { getPlans, createPlan, updatePlan, deletePlan } from "../api/endpoints";
import type { Plan } from "../lib/types";
import { useFetch } from "../hooks/useFetch";
import { useToast } from "../context/ToastContext";
import Modal from "../components/Modal";
import ConfirmDialog from "../components/ConfirmDialog";
import Spinner from "../components/Spinner";
import EmptyState from "../components/EmptyState";

export default function PlansPage() {
  const { data, loading, refetch } = useFetch(() => getPlans(1));
  const { toast } = useToast();
  const [modalOpen, setModalOpen] = useState(false);
  const [editPlan, setEditPlan] = useState<Plan | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [form, setForm] = useState({
    name: "",
    duration_days: "30",
    price: "",
    currency: "USD",
    max_connections: "1",
    bandwidth_limit_gb: "0",
    description: "",
  });

  const openCreate = () => {
    setEditPlan(null);
    setForm({ name: "", duration_days: "30", price: "", currency: "USD", max_connections: "1", bandwidth_limit_gb: "0", description: "" });
    setModalOpen(true);
  };

  const openEdit = (p: Plan) => {
    setEditPlan(p);
    setForm({
      name: p.name,
      duration_days: String(p.duration_days),
      price: String(p.price),
      currency: p.currency,
      max_connections: String(p.max_connections),
      bandwidth_limit_gb: String(p.bandwidth_limit_gb),
      description: p.description,
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const payload = {
        name: form.name,
        duration_days: Number(form.duration_days),
        price: form.price,
        currency: form.currency,
        max_connections: Number(form.max_connections),
        bandwidth_limit_gb: Number(form.bandwidth_limit_gb),
        description: form.description,
      };
      if (editPlan) {
        await updatePlan(editPlan.id, payload);
        toast("success", "پلن بروزرسانی شد");
      } else {
        await createPlan(payload);
        toast("success", "پلن ایجاد شد");
      }
      setModalOpen(false);
      refetch();
    } catch (err: any) {
      toast("error", err.response?.data?.detail || "خطا در عملیات");
    }
  };

  const handleToggle = async (p: Plan) => {
    try {
      await updatePlan(p.id, { is_active: !p.is_active });
      toast("success", p.is_active ? "پلن غیرفعال شد" : "پلن فعال شد");
      refetch();
    } catch {
      toast("error", "خطا");
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    setDeleting(true);
    try {
      await deletePlan(deleteId);
      toast("success", "پلن حذف شد");
      setDeleteId(null);
      refetch();
    } catch (err: any) {
      toast("error", err.response?.data?.detail || "خطا در حذف");
    } finally {
      setDeleting(false);
    }
  };

  if (loading) return <div className="flex justify-center py-20"><Spinner className="w-10 h-10" /></div>;

  const plans = data?.results || [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">پلن‌ها</h1>
          <p className="text-gray-500 text-sm mt-1">{plans.length} پلن</p>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          پلن جدید
        </button>
      </div>

      {plans.length === 0 ? (
        <EmptyState
          icon={<CreditCard className="w-12 h-12" />}
          title="پلنی وجود ندارد"
          action={<button onClick={openCreate} className="btn-primary btn-sm">ایجاد پلن</button>}
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {plans.map((p) => (
            <div key={p.id} className={`card relative ${!p.is_active ? "opacity-60" : ""}`}>
              {!p.is_active && (
                <div className="absolute top-3 left-3 text-xs bg-gray-700 text-gray-400 px-2 py-0.5 rounded">غیرفعال</div>
              )}
              <h3 className="text-lg font-bold text-white mb-1">{p.name}</h3>
              <div className="text-3xl font-bold text-indigo-400 mb-4">
                {p.price} <span className="text-sm text-gray-500">{p.currency}</span>
              </div>
              <ul className="space-y-2 text-sm text-gray-400 mb-6">
                <li>مدت: {p.duration_days} روز</li>
                <li>اتصال همزمان: {p.max_connections}</li>
                <li>حجم: {p.bandwidth_limit_gb === 0 ? "نامحدود" : `${p.bandwidth_limit_gb} GB`}</li>
                {p.description && <li className="text-gray-500">{p.description}</li>}
              </ul>
              <div className="flex gap-2">
                <button onClick={() => handleToggle(p)} className="btn-secondary btn-sm flex items-center gap-1 flex-1">
                  {p.is_active ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}
                  {p.is_active ? "غیرفعال" : "فعال"}
                </button>
                <button onClick={() => openEdit(p)} className="btn-secondary btn-sm flex items-center gap-1 flex-1">
                  <Edit2 className="w-3.5 h-3.5" /> ویرایش
                </button>
                <button onClick={() => setDeleteId(p.id)} className="btn-danger btn-sm">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editPlan ? "ویرایش پلن" : "ایجاد پلن"}>
        <div className="space-y-4">
          <div>
            <label className="label">نام پلن</label>
            <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">مدت (روز)</label>
              <input className="input" dir="ltr" type="number" value={form.duration_days} onChange={(e) => setForm({ ...form, duration_days: e.target.value })} />
            </div>
            <div>
              <label className="label">قیمت</label>
              <input className="input" dir="ltr" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="label">واحد پول</label>
              <input className="input" dir="ltr" value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} />
            </div>
            <div>
              <label className="label">اتصال همزمان</label>
              <input className="input" dir="ltr" type="number" value={form.max_connections} onChange={(e) => setForm({ ...form, max_connections: e.target.value })} />
            </div>
            <div>
              <label className="label">حجم (GB)</label>
              <input className="input" dir="ltr" type="number" value={form.bandwidth_limit_gb} onChange={(e) => setForm({ ...form, bandwidth_limit_gb: e.target.value })} placeholder="0 = نامحدود" />
            </div>
          </div>
          <div>
            <label className="label">توضیحات</label>
            <textarea className="input" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button className="btn-secondary" onClick={() => setModalOpen(false)}>انصراف</button>
            <button className="btn-primary" onClick={handleSubmit}>{editPlan ? "بروزرسانی" : "ایجاد"}</button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={deleteId !== null}
        onClose={() => setDeleteId(null)}
        onConfirm={handleDelete}
        title="حذف پلن"
        message="آیا از حذف این پلن اطمینان دارید؟"
        confirmLabel="حذف"
        danger
        loading={deleting}
      />
    </div>
  );
}
