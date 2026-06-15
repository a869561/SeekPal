import { useTranslation } from "react-i18next";
import { Bot, Loader2 } from "lucide-react";
import CitationCard from "./CitationCard.jsx";
import LoadingSpinner from "../ui/LoadingSpinner.jsx";

function renderWithCitations(text, citations) {
  const map = {};
  citations.forEach((c, i) => { map[c.chunk_id] = i + 1; });

  // split on [anything] markers
  const parts = text.split(/(\[[^\]]+\])/g);
  return parts.map((part, i) => {
    const m = part.match(/^\[(.+)\]$/);
    if (m && map[m[1]] != null) {
      return (
        <sup key={i}>
          <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-brand-soft text-brand text-[9px] font-bold cursor-default mx-0.5">
            {map[m[1]]}
          </span>
        </sup>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

export default function ChatResponse({ citations, text, loading }) {
  const { t } = useTranslation();

  // Carga inicial (antes de que llegue el primer token): mismo círculo limpio
  // que el modo búsqueda, en vez de la caja vacía con texto.
  if (loading && !text) {
    return <LoadingSpinner label={t("ask.loading")} />;
  }

  return (
    <div className="space-y-4">
      {/* Primero la respuesta del modelo */}
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="p-1.5 rounded-lg bg-brand-soft">
            <Bot size={16} className="text-brand" />
          </div>
          <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            {t("ask.aiAnswer")}
          </span>
          {loading && <Loader2 size={14} className="text-brand animate-spin ml-1" />}
        </div>
        <div className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap min-h-[2rem]">
          {text ? renderWithCitations(text, citations) : null}
        </div>
      </div>

      {/* Después las fuentes consultadas (solo nombre/página/score, sin descripción) */}
      {citations.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-2">
            {t("ask.citations.title")}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {citations.map((c, i) => (
              <CitationCard key={c.chunk_id} citation={c} index={i} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
