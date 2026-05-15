import { File } from "../models/File.js";

export const searchService = {
  async search({ q, category, sourceId, page = 1, limit = 20 }) {
    const filter = {};

    if (q?.trim()) {
      const escaped = q.trim()
        .split(/\s+/)
        .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
        .join("|");
      const regex = new RegExp(escaped, "i");
      filter.$or = [{ name: regex }, { path: regex }];
    }

    if (category) filter.category = category;
    if (sourceId)  filter.sourceId = sourceId;

    const skip = (page - 1) * limit;
    const [files, total] = await Promise.all([
      File.find(filter).sort({ name: 1 }).skip(skip).limit(limit).lean(),
      File.countDocuments(filter),
    ]);

    return { files, total, page, pages: Math.ceil(total / limit) || 1 };
  },
};
