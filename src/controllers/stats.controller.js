import { ok } from "../utils/api-response.js";
import { statsService } from "../services/stats.service.js";

export const statsController = {
  async summary(_req, res, next) {
    try {
      const data = await statsService.getSummary();
      return ok(res, data);
    } catch (error) {
      return next(error);
    }
  },

  async files(req, res, next) {
    try {
      const { sourceId, category, page, limit } = req.query;
      const data = await statsService.getFiles({
        sourceId,
        category,
        page: page ? Number(page) : 1,
        limit: limit ? Number(limit) : 50,
      });
      return ok(res, data);
    } catch (error) {
      return next(error);
    }
  },
};
