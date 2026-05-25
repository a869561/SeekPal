import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Search } from "lucide-react";
import { search as searchApi } from "../api/search.js";
import { getSources } from "../api/sources.js";
import { askStream } from "../api/ask.js";
import { useSearch } from "../context/SearchContext.jsx";
import { classifyQuery } from "../hooks/useAutoMode.js";
import ModeSelector from "../components/search/ModeSelector.jsx";
import ClassicResults from "../components/search/ClassicResults.jsx";
import ChatResponse from "../components/search/ChatResponse.jsx";

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

  const [mode, setMode] = useState("auto");
  const [sources, setSources] = useState([]);
  const [topK, setTopK] = useState(10); // valor por defecto hasta que cargue del backend

  // Ask-mode state (ephemeral, not persisted in context)
  const [citations, setCitations] = useState([]);
  const [responseText, setResponseText] = useState("");
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState(null);
  const [activeMode, setActiveMode] = useState("search"); // resolved mode for last submit

  const abortRef = useRef(null);

  useEffect(() => {
    getSources().then((r) => setSources(r.data.data || []));
  }, []);

  // Cargar top_k real del backend (evita hardcodear el valor aquí)
  useEffect(() => {
    import("../api/client.js").then(({ default: api }) => {
      api.get("/ask/config")
        .then((r) => { if (r.data?.data?.top_k) setTopK(r.data.data.top_k); })
        .catch(() => {}); // usa el valor por defecto si falla
    });
  }, []);

  // Classic search effect
  useEffect(() => {
    if (!submitted || activeMode !== "search") return;
    setLoading(true);
    searchApi({ q: submitted, page, category, sourceId, limit: 15 })
      .then((r) => setResults(r.data.data))
      .finally(() => setLoading(false));
  }, [submitted, page, category, sourceId, activeMode]);

  const runSearch = useCallback((q) => {
    setQuery(q);
    setPage(1);
    setResults(null);
    setSubmitted(q);
    setActiveMode("search");
    setRecent((prev) => [q, ...prev.filter((r) => r !== q)].slice(0, 6));
  }, [setQuery, setPage, setResults, setSubmitted, setRecent]);

  const runAsk = useCallback((q) => {
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setQuery(q);
    setSubmitted(q);
    setActiveMode("ask");
    setCitations([]);
    setResponseText("");
    setAskError(null);
    setAsking(true);
    setRecent((prev) => [q, ...prev.filter((r) => r !== q)].slice(0, 6));

    askStream(
      { question: q, top_k: topK, source_id: sourceId || undefined, categories: category ? [category] : undefined },
      {
        signal: controller.signal,
        onCitations: (c) => setCitations(c),
        onToken: (tok) => setResponseText((prev) => prev + tok),
        onDone: () => setAsking(false),
        onError: (err) => {
          setAskError(err);
          setAsking(false);
        },
      },
    );
  }, [setQuery, setSubmitted, setRecent, sourceId, category, topK]);

  function handleSubmit(e) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;

    const resolved = mode === "auto" ? classifyQuery(q) : mode;
    if (resolved === "ask") {
      runAsk(q);
    } else {
      runSearch(q);
    }
  }

  // Landing state
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

        <div className="w-full max-w-2xl mb-4">
          <ModeSelector mode={mode} onChange={setMode} />
        </div>

        <form onSubmit={handleSubmit} className="w-full max-w-2xl mb-6">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search size={17} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={mode === "ask" ? t("ask.placeholder") : t("search.placeholder")}
                autoFocus
                className="w-full pl-11 pr-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent transition text-sm shadow-sm"
              />
            </div>
            <button type="submit"
              className="px-5 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition shadow-sm flex-shrink-0">
              {mode === "ask" ? t("ask.submit") : t("search.submit")}
            </button>
          </div>
        </form>

        {recent.length > 0 && (
          <div className="w-full max-w-2xl">
            <p className="text-xs text-slate-400 dark:text-slate-500 mb-2">{t("search.recent")}</p>
            <div className="flex flex-wrap gap-2">
              {recent.map((r) => (
                <button key={r} onClick={() => {
                  const resolved = mode === "auto" ? classifyQuery(r) : mode;
                  if (resolved === "ask") runAsk(r); else runSearch(r);
                }}
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

  // Results state
  return (
    <div className="p-8 max-w-3xl mx-auto w-full">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
          {activeMode === "ask" ? t("ask.title") : t("search.title")}
        </h1>
        <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
          {activeMode === "ask"
            ? (asking ? t("ask.loading") : submitted)
            : (loading ? t("search.searching") : t("search.subtitle", { count: results?.total ?? 0, query: submitted }))}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="mb-6">
        <div className="flex flex-col gap-3">
          <ModeSelector mode={mode} onChange={setMode} />
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search size={17} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={mode === "ask" ? t("ask.placeholder") : t("search.placeholder")}
                autoFocus
                className="w-full pl-11 pr-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent transition text-sm shadow-sm"
              />
            </div>
            <button type="submit"
              className="px-5 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition shadow-sm flex-shrink-0">
              {mode === "ask" ? t("ask.submit") : t("search.submit")}
            </button>
          </div>
          {activeMode === "search" && (
            <div className="flex gap-2 flex-wrap">
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
          )}
        </div>
      </form>

      <div className="space-y-5">
        {activeMode === "ask" ? (
          <>
            {askError && (
              <div className="p-3 rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 text-sm text-red-600 dark:text-red-400">
                {t("ask.error.generic")} — {askError.message}
              </div>
            )}
            <ChatResponse citations={citations} text={responseText} loading={asking} />
          </>
        ) : (
          <ClassicResults
            results={results}
            loading={loading}
            submitted={submitted}
            page={page}
            setPage={setPage}
          />
        )}
      </div>
    </div>
  );
}
