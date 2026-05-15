import { searchService } from "../services/search.service.js";
import { ok } from "../utils/api-response.js";

export const searchController = {
  async search(req, res, next) {
    try {
      const { q, category, sourceId, page = 1, limit = 15 } = req.query;
      const result = await searchService.search({
        q,
        category,
        sourceId,
        page:  parseInt(page),
        limit: parseInt(limit),
      });
      return ok(res, result);
    } catch (err) {
      next(err);
    }
  },
};
