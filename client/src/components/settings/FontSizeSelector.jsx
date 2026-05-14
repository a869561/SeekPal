import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ALargeSmall } from "lucide-react";
import { saveSettings } from "../../api/settings.js";

const OPTIONS = [
  { value: "sm", size: "15px" },
  { value: "md", size: "18px" },
  { value: "lg", size: "21px" },
];

export function applyFontSize(value) {
  const opt = OPTIONS.find((o) => o.value === value) ?? OPTIONS[1];
  document.documentElement.style.fontSize = opt.size;
}

export default function FontSizeSelector() {
  const { t } = useTranslation();
  const [selected, setSelected] = useState(() => localStorage.getItem("seekpal_fontsize") || "md");

  const LABELS = {
    sm: t("fontSize.small"),
    md: t("fontSize.normal"),
    lg: t("fontSize.large"),
  };

  function handleSelect(value) {
    setSelected(value);
    localStorage.setItem("seekpal_fontsize", value);
    applyFontSize(value);
    saveSettings({ fontSize: value }).catch(() => {});
  }

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-sm">
      <div className="flex items-center gap-2 mb-5">
        <ALargeSmall size={18} className="text-indigo-500" />
        <h2 className="font-semibold text-slate-800 dark:text-slate-100">{t("fontSize.title")}</h2>
      </div>
      <div className="flex gap-3">
        {OPTIONS.map(({ value, size }) => (
          <button
            key={value}
            onClick={() => handleSelect(value)}
            className={`flex-1 flex flex-col items-center gap-2 py-3 px-2 rounded-xl border-2 transition font-medium
              ${selected === value
                ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400"
                : "border-slate-200 dark:border-slate-600 text-slate-500 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-500 hover:bg-slate-50 dark:hover:bg-slate-700"
              }`}
          >
            <span style={{ fontSize: size, lineHeight: 1 }}>Aa</span>
            <span className="text-xs">{LABELS[value]}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
