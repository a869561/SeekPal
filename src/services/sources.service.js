import fs from "fs/promises";
import { Source } from "../models/Source.js";
import { File } from "../models/File.js";

export const sourcesService = {
  async list() {
    return Source.find().sort({ createdAt: -1 });
  },

  async add({ name, path: dirPath }) {
    try {
      const stat = await fs.stat(dirPath);
      if (!stat.isDirectory()) {
        const err = new Error("La ruta no es un directorio");
        err.statusCode = 400;
        throw err;
      }
    } catch (e) {
      if (e.statusCode) throw e;
      const err = new Error("Directorio no encontrado o sin acceso");
      err.statusCode = 400;
      throw err;
    }
    return Source.create({ name, path: dirPath });
  },

  async remove(id) {
    const source = await Source.findByIdAndDelete(id);
    if (!source) {
      const err = new Error("Fuente no encontrada");
      err.statusCode = 404;
      throw err;
    }
    await File.deleteMany({ sourceId: id });
    return source;
  },
};
