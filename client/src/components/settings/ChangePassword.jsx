import { useState } from "react";
import { changePassword } from "../../api/auth.js";
import toast from "react-hot-toast";
import { Lock } from "lucide-react";

export default function ChangePassword() {
  const [form, setForm] = useState({ currentPassword: "", newPassword: "", confirm: "" });
  const [loading, setLoading] = useState(false);

  function update(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (form.newPassword !== form.confirm) {
      toast.error("Las contraseñas no coinciden");
      return;
    }
    if (form.newPassword.length < 4) {
      toast.error("La nueva contraseña debe tener al menos 4 caracteres");
      return;
    }
    setLoading(true);
    try {
      await changePassword({ currentPassword: form.currentPassword, newPassword: form.newPassword });
      toast.success("Contraseña actualizada");
      setForm({ currentPassword: "", newPassword: "", confirm: "" });
    } catch (err) {
      toast.error(err.response?.data?.message || "Error al cambiar la contraseña");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
      <div className="flex items-center gap-2 mb-5">
        <Lock size={18} className="text-indigo-500" />
        <h2 className="font-semibold text-slate-800">Cambiar contraseña</h2>
      </div>
      <form onSubmit={handleSubmit} className="space-y-4">
        {[
          { field: "currentPassword", label: "Contraseña actual", placeholder: "••••••••" },
          { field: "newPassword", label: "Nueva contraseña", placeholder: "••••••••" },
          { field: "confirm", label: "Confirmar nueva contraseña", placeholder: "••••••••" },
        ].map(({ field, label, placeholder }) => (
          <div key={field}>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">{label}</label>
            <input
              type="password"
              value={form[field]}
              onChange={update(field)}
              placeholder={placeholder}
              required
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
            />
          </div>
        ))}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm disabled:opacity-50 transition mt-2"
        >
          {loading ? "Guardando…" : "Actualizar contraseña"}
        </button>
      </form>
    </div>
  );
}
