import { ok, created } from "../utils/api-response.js";
import { sourcesService } from "../services/sources.service.js";
import { ingestSource } from "../services/scanner.service.js";

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

  async ingest(req, res, next) {
    try {
      res.setHeader("Content-Type", "text/event-stream");
      res.setHeader("Cache-Control", "no-cache");
      res.setHeader("Connection", "keep-alive");
      res.flushHeaders();

      const send = (data) => res.write(`data: ${JSON.stringify(data)}\n\n`);

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
