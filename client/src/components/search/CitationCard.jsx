import { FileText, BookOpen } from "lucide-react";
import { useTranslation } from "react-i18next";

export default function CitationCard({ citation, index }) {
  const { t } = useTranslation();
  return (
    <div className="flex items-start gap-2.5 p-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg">
      <div className="flex-shrink-0 w-5 h-5 rounded-full bg-brand-soft flex items-center justify-center mt-0.5">
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
          <span className="text-xs text-slate-300 dark:text-slate-600 ml-auto flex-shrink-0">
            {(citation.score * 100).toFixed(0)}%
          </span>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 line-clamp-2 leading-relaxed">
          {citation.snippet}
        </p>
      </div>
    </div>
  );
}
