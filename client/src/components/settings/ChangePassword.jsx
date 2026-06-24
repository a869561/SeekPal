import { useState } from "react";
import { useTranslation } from "react-i18next";
import { changePassword } from "../../api/auth.js";
import toast from "react-hot-toast";
import { Lock, Eye, EyeOff } from "lucide-react";
import CollapsibleHeader from "../ui/CollapsibleHeader.jsx";
import useCollapsed from "../../hooks/useCollapsed.js";

export default function ChangePassword() {
  const { t } = useTranslation();
  const [form, setForm] = useState({ currentPassword: "", newPassword: "", confirm: "" });
  const [visible, setVisible] = useState({ currentPassword: false, newPassword: false, confirm: false });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [collapsed, toggleCollapsed] = useCollapsed("password");

  const FIELDS = [
    { field: "currentPassword", labelKey: "password.current" },
    { field: "newPassword",     labelKey: "password.new" },
    { field: "confirm",         labelKey: "password.confirm" },
  ];

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
    if (form.newPassword.length < 4) newErrors.newPassword = t("password.minLength");
    if (form.newPassword !== form.confirm) newErrors.confirm = t("password.mismatch");
    if (Object.keys(newErrors).length) { setErrors(newErrors); return; }

    setLoading(true);
    setErrors({});
    try {
      await changePassword({ currentPassword: form.currentPassword, newPassword: form.newPassword });
      toast.success(t("password.success"));
      setForm({ currentPassword: "", newPassword: "", confirm: "" });
    } catch (err) {
      setErrors({ currentPassword: err.response?.data?.message || t("password.wrong") });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-card">
      <CollapsibleHeader icon={Lock} title={t("password.title")} collapsed={collapsed} onToggle={toggleCollapsed} />
      {!collapsed && (
      <form onSubmit={handleSubmit} className="space-y-4 mt-5">
        {FIELDS.map(({ field, labelKey }) => (
          <div key={field}>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">{t(labelKey)}</label>
            <div className="relative">
              <input
                type={visible[field] ? "text" : "password"}
                value={form[field]}
                onChange={update(field)}
                placeholder={t("password.placeholder")}
                required
                className={`w-full px-4 py-2.5 pr-10 rounded-xl border text-sm focus:outline-none focus:ring-2 focus:border-transparent transition
                  bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500
                  ${errors[field]
                    ? "border-danger focus:ring-danger/50"
                    : "border-slate-200 dark:border-slate-600 focus:ring-brand/50"
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
            {errors[field] && <p className="text-danger text-xs mt-1.5">{errors[field]}</p>}
          </div>
        ))}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 px-4 rounded-xl bg-brand hover:brightness-110 active:scale-[0.98] text-white font-medium text-sm disabled:opacity-50 transition mt-2"
        >
          {loading ? t("password.saving") : t("password.submit")}
        </button>
      </form>
      )}
    </div>
  );
}
