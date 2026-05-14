import { useTranslation } from "react-i18next";
import { Monitor, Sun, Moon } from "lucide-react";
import { useTheme } from "../../context/ThemeContext.jsx";
import { saveSettings } from "../../api/settings.js";

export default function ThemeSelector() {
  const { t } = useTranslation();
  const { theme, setTheme } = useTheme();

  const OPTIONS = [
    { value: "auto",  label: t("theme.auto"),  icon: Monitor },
    { value: "light", label: t("theme.light"), icon: Sun },
    { value: "dark",  label: t("theme.dark"),  icon: Moon },
  ];

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-sm">
      <div className="flex items-center gap-2 mb-5">
        <Monitor size={18} className="text-indigo-500" />
        <h2 className="font-semibold text-slate-800 dark:text-slate-100">{t("theme.title")}</h2>
      </div>
      <div className="flex gap-3">
        {OPTIONS.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            onClick={() => { setTheme(value); saveSettings({ theme: value }).catch(() => {}); }}
            className={`flex-1 flex flex-col items-center gap-2 py-3 px-2 rounded-xl border-2 transition text-sm font-medium
              ${theme === value
                ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400"
                : "border-slate-200 dark:border-slate-600 text-slate-500 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-500 hover:bg-slate-50 dark:hover:bg-slate-700"
              }`}
          >
            <Icon size={20} />
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
