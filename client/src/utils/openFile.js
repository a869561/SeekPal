import toast from "react-hot-toast";
import { openFile } from "../api/system.js";

// Abre un fichero indexado en la app por defecto del SO (búsqueda y citas).
// Muestra un toast de error claro si el fichero ya no existe o falla la apertura.
export async function openIndexedFile(fileId, t) {
  try {
    await openFile(fileId);
  } catch (err) {
    const status = err?.response?.status;
    toast.error(status === 404 ? t("files.notFound") : t("files.openError"));
  }
}
