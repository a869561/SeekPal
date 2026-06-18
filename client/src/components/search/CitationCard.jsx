import { useState } from "react";
import { FileText, BookOpen, ExternalLink, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { relevancePct } from "../../utils/relevance.js";
import { openIndexedFile } from "../../utils/openFile.js";

export default function CitationCard({ citation, index }) {
  const { t } = useTranslation();
  const [opening, setOpening] = useState(false);

  const handleOpen = async () => {
    if (opening) return;
    setOpening(true);
    try {
      await openIndexedFile(citation.file_id, t);
    } finally {
      setOpening(false);
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleOpen}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleOpen(); } }}
      title={t("files.open")}
      className="group flex items-center gap-2.5 p-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg hover:border-brand/40 hover:bg-slate-50/50 dark:hover:bg-slate-700/30 cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
    >
      <div className="flex-shrink-0 w-5 h-5 rounded-full bg-brand-soft flex items-center justify-center">
        <span className="text-[10px] font-bold text-brand">{index + 1}</span>
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 flex-wrap">
          <FileText size={13} className="text-slate-400 flex-shrink-0" />
          <span className="text-sm font-medium text-slate-700 dark:text-slate-200 truncate">{citation.file_name}</span>
          {citation.page != null && (
            <span className="flex items-center gap-0.5 text-xs text-slate-400 dark:text-slate-500 flex-shrink-0">
              <BookOpen size={10} />
              {t("ask.citations.page", { page: citation.page })}
            </span>
          )}
          <span className="ml-auto flex items-center gap-2 flex-shrink-0">
            <span className="text-xs text-slate-300 dark:text-slate-600">
              {relevancePct(citation.score)}%
            </span>
            {opening ? (
              <Loader2 size={13} className="text-brand animate-spin" />
            ) : (
              <ExternalLink
                size={13}
                className="text-slate-300 dark:text-slate-600 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 transition-opacity"
              />
            )}
          </span>
        </div>
      </div>
    </div>
  );
}
