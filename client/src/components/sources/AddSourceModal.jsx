import { useState } from "react";
import { useTranslation } from "react-i18next";
import { X, FolderOpen, FolderSearch } from "lucide-react";
import client from "../../api/client.js";

export default function AddSourceModal({ onClose, onAdd }) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [dirPath, setDirPath] = useState("");
  const [loading, setLoading] = useState(false);
  const [picking, setPicking] = useState(false);
  const [nameEdited, setNameEdited] = useState(false);

  async function pickFolder() {
    setPicking(true);
    try {
      const res = await client.get("/system/folder-picker");
      const path = res.data.data.path;
      if (!path) return;
      setDirPath(path);
      if (!nameEdited) setName(path.split(/[\\/]/).filter(Boolean).pop() || "");
    } catch {
      // user cancelled or error — do nothing
    } finally {
      setPicking(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      await onAdd({ name: name.trim(), path: dirPath.trim() });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100 dark:border-slate-700">
          <div className="flex items-center gap-2">
            <FolderOpen size={20} className="text-indigo-500" />
            <h2 className="font-semibold text-slate-800 dark:text-slate-100">{t("addSource.title")}</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">{t("addSource.nameLabel")}</label>
            <input
              type="text"
              value={name}
              onChange={(e) => { setName(e.target.value); setNameEdited(true); }}
              placeholder={t("addSource.namePlaceholder")}
              required
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm transition"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">{t("addSource.dirLabel")}</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={dirPath}
                onChange={(e) => setDirPath(e.target.value)}
                placeholder={t("addSource.dirPlaceholder")}
                required
                className="flex-1 px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
              />
              <button
                type="button"
                onClick={pickFolder}
                disabled={picking}
                title={t("addSource.browseTooltip")}
                className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 dark:hover:bg-indigo-900 disabled:opacity-50 transition text-sm font-medium whitespace-nowrap"
              >
                <FolderSearch size={16} />
                {picking ? t("addSource.browseOpening") : t("addSource.browse")}
              </button>
            </div>
          </div>

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 px-4 rounded-xl border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 font-medium text-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition"
            >
              {t("addSource.cancel")}
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm disabled:opacity-50 transition"
            >
              {loading ? t("addSource.submitting") : t("addSource.submit")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
