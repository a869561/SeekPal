import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { getSources, addSource, deleteSource } from "../api/sources.js";
import SourcesList from "../components/sources/SourcesList.jsx";
import AddSourceModal from "../components/sources/AddSourceModal.jsx";
import toast from "react-hot-toast";
import { FolderPlus } from "lucide-react";

export default function SourcesPage() {
  const { t } = useTranslation();
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  async function load() {
    try {
      const res = await getSources();
      setSources(res.data.data || []);
    } catch {
      toast.error(t("sources.loadError"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleAdd(data) {
    try {
      await addSource(data);
      toast.success(t("sources.added"));
      setShowModal(false);
      load();
    } catch (err) {
      toast.error(err.response?.data?.message || t("sources.addError"));
    }
  }

  async function handleDelete(id) {
    if (!confirm(t("sources.deleteConfirm"))) return;
    try {
      await deleteSource(id);
      toast.success(t("sources.deleted"));
      load();
    } catch {
      toast.error(t("sources.deleteError"));
    }
  }

  function handleSourceUpdate(updated) {
    setSources((prev) => prev.map((s) => s._id === updated._id ? updated : s));
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">{t("sources.title")}</h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">{t("sources.subtitle")}</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition shadow-sm"
        >
          <FolderPlus size={18} />
          {t("sources.addButton")}
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center items-center h-40">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <SourcesList sources={sources} onDelete={handleDelete} onUpdate={handleSourceUpdate} />
      )}

      {showModal && (
        <AddSourceModal onClose={() => setShowModal(false)} onAdd={handleAdd} />
      )}
    </div>
  );
}
