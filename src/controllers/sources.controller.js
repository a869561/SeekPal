import { ok, created } from "../utils/api-response.js";
import { sourcesService } from "../services/sources.service.js";
import { ingestSource } from "../services/scanner.service.js";
import { startWatcher, stopWatcher } from "../services/watcher.service.js";
import { Source } from "../models/Source.js";

export const sourcesController = {
  async list(_req, res, next) {
    try {
      const sources = await sourcesService.list();
      return ok(res, sources);
    } catch (error) {
      return next(error);
    }
  },

  async add(req, res, next) {
    try {
      const source = await sourcesService.add(req.body);
      return created(res, source, "Fuente añadida");
    } catch (error) {
      return next(error);
    }
  },

  async remove(req, res, next) {
    try {
      await sourcesService.remove(req.params.id);
      return ok(res, null, "Fuente eliminada");
    } catch (error) {
      return next(error);
    }
  },

  async toggleAutoIndex(req, res, next) {
    try {
      const source = await Source.findById(req.params.id);
      if (!source) return res.status(404).json({ success: false, message: "Fuente no encontrada" });

      source.autoIndex = !source.autoIndex;
      await source.save();

      if (source.autoIndex) startWatcher(String(source._id), source.path);
      else                  stopWatcher(String(source._id));

      return ok(res, source);
    } catch (error) {
      return next(error);
    }
  },

  async ingest(req, res, next) {
    try {
      res.setHeader("Content-Type", "text/event-stream");
      res.setHeader("Cache-Control", "no-cache");
      res.setHeader("Connection", "keep-alive");
      res.flushHeaders();

      const send = (data) => res.write(`data: ${JSON.stringify(data)}\n\n`);

      send({ type: "scanning" });
      await ingestSource(req.params.id, ({ current, total, file }) => {
        send({ type: "progress", current, total, file });
      });

      send({ type: "done" });
      res.end();
    } catch (error) {
      res.write(`data: ${JSON.stringify({ type: "error", message: error.message })}\n\n`);
      res.end();
    }
  },
};
