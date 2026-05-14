import { useState } from "react";
import { changePassword } from "../../api/auth.js";
import toast from "react-hot-toast";
import { Lock, Eye, EyeOff } from "lucide-react";

export default function ChangePassword() {
  const [form, setForm] = useState({ currentPassword: "", newPassword: "", confirm: "" });
  const [visible, setVisible] = useState({ currentPassword: false, newPassword: false, confirm: false });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  function toggleVisible(field) {
    setVisible((v) => ({ ...v, [field]: !v[field] }));
  }

  function update(field) {
    return (e) => {
      setForm((f) => ({ ...f, [field]: e.target.value }));
      if (errors[field]) setErrors((err) => ({ ...err, [field]: null }));
    };
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const newErrors = {};

    if (form.newPassword.length < 4)
      newErrors.newPassword = "Mínimo 4 caracteres";
    if (form.newPassword !== form.confirm)
      newErrors.confirm = "Las contraseñas no coinciden";

    if (Object.keys(newErrors).length) {
      setErrors(newErrors);
      return;
    }

    setLoading(true);
    setErrors({});
    try {
      await changePassword({ currentPassword: form.currentPassword, newPassword: form.newPassword });
      toast.success("Contraseña actualizada");
      setForm({ currentPassword: "", newPassword: "", confirm: "" });
    } catch (err) {
      setErrors({ currentPassword: err.response?.data?.message || "Contraseña incorrecta" });
    } finally {
      setLoading(false);
    }
  }

  const FIELDS = [
    { field: "currentPassword", label: "Contraseña actual",          placeholder: "••••••••" },
    { field: "newPassword",     label: "Nueva contraseña",           placeholder: "••••••••" },
    { field: "confirm",         label: "Confirmar nueva contraseña", placeholder: "••••••••" },
  ];

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-sm">
      <div className="flex items-center gap-2 mb-5">
        <Lock size={18} className="text-indigo-500" />
        <h2 className="font-semibold text-slate-800 dark:text-slate-100">Cambiar contraseña</h2>
      </div>
      <form onSubmit={handleSubmit} className="space-y-4">
        {FIELDS.map(({ field, label, placeholder }) => (
          <div key={field}>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">{label}</label>
            <div className="relative">
              <input
                type={visible[field] ? "text" : "password"}
                value={form[field]}
                onChange={update(field)}
                placeholder={placeholder}
                required
                className={`w-full px-4 py-2.5 pr-10 rounded-xl border text-sm focus:outline-none focus:ring-2 focus:border-transparent transition
                  bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500
                  ${errors[field]
                    ? "border-red-400 dark:border-red-500 focus:ring-red-400"
                    : "border-slate-200 dark:border-slate-600 focus:ring-indigo-500"
                  }`}
              />
              <button
                type="button"
                onClick={() => toggleVisible(field)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition"
              >
                {visible[field] ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {errors[field] && (
              <p className="text-red-500 dark:text-red-400 text-xs mt-1.5">{errors[field]}</p>
            )}
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
