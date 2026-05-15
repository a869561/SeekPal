import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Search, Bot, FileText, Image, Music, Film, File,
  ChevronLeft, ChevronRight, Sparkles,
} from "lucide-react";
import { search as searchApi } from "../api/search.js";
import { getSources } from "../api/sources.js";
import { useSearch } from "../context/SearchContext.jsx";

function formatSize(b) {
  if (b == null) return "";
  if (b < 1024) return `${b} B`;
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(1)} MB`;
  return `${(b / 1024 ** 3).toFixed(2)} GB`;
}

const CAT_STYLE = {
  text:     { icon: FileText, iconCls: "text-indigo-500", bg: "bg-indigo-50 dark:bg-indigo-950",  badge: "bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400"  },
  document: { icon: FileText, iconCls: "text-amber-500",  bg: "bg-amber-50 dark:bg-amber-950",   badge: "bg-amber-50 dark:bg-amber-950 text-amber-600 dark:text-amber-400"     },
  image:    { icon: Image,    iconCls: "text-emerald-500",bg: "bg-emerald-50 dark:bg-emerald-950",badge: "bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400"},
  audio:    { icon: Music,    iconCls: "text-pink-500",   bg: "bg-pink-50 dark:bg-pink-950",     badge: "bg-pink-50 dark:bg-pink-950 text-pink-600 dark:text-pink-400"          },
  video:    { icon: Film,     iconCls: "text-blue-500",   bg: "bg-blue-50 dark:bg-blue-950",     badge: "bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400"          },
  other:    { icon: File,     iconCls: "text-slate-400",  bg: "bg-slate-100 dark:bg-slate-800",  badge: "bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400"     },
};

function MetaSnippet({ file }) {
  const m = file.metadata || {};
  const parts = [];

  if (file.category === "text" || file.category === "document") {
    if (m.wordCount != null) parts.push(`${m.wordCount.toLocaleString()} palabras`);
  } else if (file.category === "image") {
    if (m.width && m.height) parts.push(`${m.width}×${m.height}${m.ppi ? ` · ${m.ppi} ppi` : ""}`);
  } else if (file.category === "audio") {
    if (m.duration != null) {
      const min = Math.floor(m.duration / 60);
      const sec = m.duration % 60;
      parts.push(`${min}:${String(sec).padStart(2, "0")}${m.bitrate ? ` · ${m.bitrate} kbps` : ""}`);
    }
  } else if (file.category === "video") {
    if (m.duration != null) {
      const min = Math.floor(m.duration / 60);
      const sec = m.duration % 60;
      parts.push(`${min}:${String(sec).padStart(2, "0")}${m.width ? ` · ${m.width}×${m.height}` : ""}`);
    }
  }

  if (!parts.length) return null;
  return <span>{parts.join(" · ")}</span>;
}

function FileResultCard({ file, t }) {
  const s = CAT_STYLE[file.category] || CAT_STYLE.other;
  const Icon = s.icon;
  const size = formatSize(file.size);

  return (
    <div className="flex items-start gap-4 p-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl hover:border-indigo-300 dark:hover:border-indigo-600 transition-colors">
      <div className={`flex-shrink-0 p-2.5 rounded-lg ${s.bg}`}>
        <Icon size={20} className={s.iconCls} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-medium text-slate-800 dark:text-slate-100 truncate">{file.name}</span>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${s.badge}`}>
            {t(`files.categories.${file.category}`, { defaultValue: file.category })}
          </span>
        </div>
        <div className="text-xs text-slate-400 dark:text-slate-500 font-mono truncate mt-0.5">{file.path}</div>
        <div className="flex items-center gap-2 mt-1 text-xs text-slate-500 dark:text-slate-400">
          {size && <span>{size}</span>}
          <MetaSnippet file={file} />
        </div>
      </div>
    </div>
  );
}

function AnswerCard({ t }) {
  const features = t("search.answer.features", { returnObjects: true });
  return (
    <div className="rounded-xl border-2 border-dashed border-indigo-200 dark:border-indigo-800 bg-indigo-50/40 dark:bg-indigo-950/30 p-5">
      <div className="flex items-center gap-2 mb-3">
        <div className="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-900">
          <Bot size={18} className="text-indigo-400 dark:text-indigo-500" />
        </div>
        <span className="font-semibold text-slate-700 dark:text-slate-200 text-sm">{t("search.answer.title")}</span>
        <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900 text-amber-600 dark:text-amber-400 font-medium">
          <Sparkles size={10} /> {t("search.answer.soon")}
        </span>
      </div>
      <ul className="space-y-1.5 mb-3">
        {Array.isArray(features) && features.map((f, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-slate-500 dark:text-slate-400">
            <span className="mt-1 w-1.5 h-1.5 rounded-full bg-indigo-400 dark:bg-indigo-500 flex-shrink-0" />
            {f}
          </li>
        ))}
      </ul>
      <Link to="/settings"
        className="text-xs text-indigo-500 hover:text-indigo-600 dark:hover:text-indigo-300 font-medium transition-colors">
        {t("search.answer.configure")} &rarr;
      </Link>
    </div>
  );
}

const selectCls = "text-sm border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-600 dark:text-slate-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-400";
const CAT_KEYS = ["", "text", "document", "image", "audio", "video", "other"];

export default function SearchPage() {
  const { t } = useTranslation();
  const {
    query, setQuery,
    submitted, setSubmitted,
    results, setResults,
    loading, setLoading,
    page, setPage,
    category, setCategory,
    sourceId, setSourceId,
    recent, setRecent,
  } = useSearch();

  const [sources, setSources] = useState([]);
  const inputRef = useRef(null);

  useEffect(() => {
    getSources().then((r) => setSources(r.data.data || []));
  }, []);

  useEffect(() => {
    if (!submitted) return;
    setLoading(true);
    searchApi({ q: submitted, page, category, sourceId, limit: 15 })
      .then((r) => setResults(r.data.data))
      .finally(() => setLoading(false));
  }, [submitted, page, category, sourceId]);

  function runSearch(q) {
    setQuery(q);
    setPage(1);
    setResults(null);
    setSubmitted(q);
    setRecent((prev) => [q, ...prev.filter((r) => r !== q)].slice(0, 6));
  }

  function handleSubmit(e) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    runSearch(q);
  }

  // ── Landing ──────────────────────────────────────────────────────────────
  if (!submitted) {
    return (
      <div className="min-h-full flex flex-col items-center px-6 pt-20">
        <div className="text-center mb-8">
          <div className="inline-flex p-4 rounded-2xl bg-indigo-50 dark:bg-indigo-950 mb-4">
            <Search size={32} className="text-indigo-600 dark:text-indigo-400" />
          </div>
          <h1 className="text-3xl font-bold text-slate-800 dark:text-slate-100 mb-2">{t("search.landing.title")}</h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm">{t("search.landing.subtitle")}</p>
        </div>

        <form onSubmit={handleSubmit} className="w-full max-w-2xl mb-6">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search size={17} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("search.placeholder")}
                autoFocus
                className="w-full pl-11 pr-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent transition text-sm shadow-sm"
              />
            </div>
            <button type="submit"
              className="px-5 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition shadow-sm flex-shrink-0">
              {t("search.submit")}
            </button>
          </div>
        </form>

        {recent.length > 0 && (
          <div className="w-full max-w-2xl">
            <p className="text-xs text-slate-400 dark:text-slate-500 mb-2">{t("search.recent")}</p>
            <div className="flex flex-wrap gap-2">
              {recent.map((r) => (
                <button key={r} onClick={() => runSearch(r)}
                  className="text-sm px-4 py-2 rounded-full border border-slate-200 dark:border-slate-600 text-slate-500 dark:text-slate-400 hover:border-indigo-400 hover:text-indigo-600 dark:hover:text-indigo-400 bg-white dark:bg-slate-800 transition truncate max-w-xs">
                  {r}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── Results ───────────────────────────────────────────────────────────────
  return (
    <div className="p-8 max-w-3xl mx-auto w-full">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">{t("search.title")}</h1>
        <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
          {loading
            ? t("search.searching")
            : t("search.subtitle", { count: results?.total ?? 0, query: submitted })}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="mb-6">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search size={17} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("search.placeholder")}
              autoFocus
              className="w-full pl-11 pr-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent transition text-sm shadow-sm"
            />
          </div>
          <button type="submit"
            className="px-5 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition shadow-sm flex-shrink-0">
            {t("search.submit")}
          </button>
        </div>
        <div className="flex gap-2 mt-3 flex-wrap">
          <select value={sourceId} onChange={(e) => { setSourceId(e.target.value); setPage(1); }} className={selectCls}>
            <option value="">{t("files.allSources")}</option>
            {sources.map((s) => <option key={s._id} value={s._id}>{s.name}</option>)}
          </select>
          <select value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }} className={selectCls}>
            {CAT_KEYS.map((c) => (
              <option key={c} value={c}>{t(`files.categories.${c || "all"}`)}</option>
            ))}
          </select>
        </div>
      </form>

      <div className="space-y-5">
        <AnswerCard t={t} />

        <div className={`space-y-2 transition-opacity duration-150 ${loading ? "opacity-50" : "opacity-100"}`}>
          {results?.files?.length === 0 ? (
            <div className="text-center py-12 text-slate-400 dark:text-slate-500 text-sm">
              {t("search.empty", { query: submitted })}
            </div>
          ) : (
            results?.files?.map((f) => <FileResultCard key={f._id} file={f} t={t} />)
          )}
        </div>

        {results && results.pages > 1 && (
          <div className="flex items-center justify-center gap-2">
            <button onClick={() => setPage((p) => p - 1)} disabled={page === 1}
              className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-30 transition">
              <ChevronLeft size={16} className="text-slate-600 dark:text-slate-300" />
            </button>
            <span className="text-sm text-slate-500 dark:text-slate-400">
              {t("files.page", { page, pages: results.pages })}
            </span>
            <button onClick={() => setPage((p) => p + 1)} disabled={page === results.pages}
              className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-30 transition">
              <ChevronRight size={16} className="text-slate-600 dark:text-slate-300" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
