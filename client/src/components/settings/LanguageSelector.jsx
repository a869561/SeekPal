import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Languages } from "lucide-react";
import { saveSettings } from "../../api/settings.js";
import CollapsibleHeader from "../ui/CollapsibleHeader.jsx";
import useCollapsed from "../../hooks/useCollapsed.js";

const OPTIONS = [
  { value: "es", label: "Español", flag: "🇪🇸" },
  { value: "en", label: "English", flag: "🇬🇧" },
];

export default function LanguageSelector() {
  const { t, i18n } = useTranslation();
  const [selected, setSelected] = useState(() => localStorage.getItem("seekpal_lang") || "es");
  const [collapsed, toggleCollapsed] = useCollapsed("language");

  function handleSelect(value) {
    setSelected(value);
    localStorage.setItem("seekpal_lang", value);
    i18n.changeLanguage(value);
    saveSettings({ language: value }).catch(() => {});
  }

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-card">
      <CollapsibleHeader icon={Languages} title={t("language.title")} collapsed={collapsed} onToggle={toggleCollapsed} />
      {!collapsed && (
      <div className="flex gap-3 mt-5">
        {OPTIONS.map(({ value, label, flag }) => (
          <button
            key={value}
            onClick={() => handleSelect(value)}
            className={`flex-1 flex flex-col items-center gap-2 py-3 px-2 rounded-xl border-2 transition font-medium
              ${selected === value
                ? "border-brand bg-brand-soft text-brand"
                : "border-slate-200 dark:border-slate-600 text-slate-500 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-500 hover:bg-slate-50 dark:hover:bg-slate-700"
              }`}
          >
            <span className="text-2xl leading-none">{flag}</span>
            <span className="text-xs">{label}</span>
          </button>
        ))}
      </div>
      )}
    </div>
  );
}
