import { useTranslation } from "react-i18next";
import { Search, MessageSquare, Sparkles } from "lucide-react";

const MODES = [
  { key: "search", Icon: Search },
  { key: "ask",    Icon: MessageSquare },
  { key: "auto",   Icon: Sparkles },
];

export default function ModeSelector({ mode, onChange }) {
  const { t } = useTranslation();
  return (
    <div className="inline-flex bg-slate-100 dark:bg-slate-800 rounded-xl p-1 gap-1">
      {MODES.map(({ key, Icon }) => (
        <button
          key={key}
          type="button"
          onClick={() => onChange(key)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            mode === key
              ? "bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-400 shadow-sm"
              : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
          }`}
        >
          <Icon size={14} />
          {t(`search.mode.${key}`)}
        </button>
      ))}
    </div>
  );
}
