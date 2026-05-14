import { File } from "../models/File.js";
import { Source } from "../models/Source.js";

export const statsService = {
  async getSummary() {
    const [totalFiles, totalSizeAgg, byCategory, sources] = await Promise.all([
      File.countDocuments(),
      File.aggregate([{ $group: { _id: null, total: { $sum: "$size" } } }]),
      File.aggregate([
        {
          $group: {
            _id: "$category",
            count: { $sum: 1 },
            size: { $sum: "$size" },
            ingestible: { $sum: { $cond: ["$modelIngestible", 1, 0] } },
          },
        },
        { $sort: { count: -1 } },
      ]),
      Source.find({ status: "done" }).countDocuments(),
    ]);

    return {
      totalFiles,
      totalSize: totalSizeAgg[0]?.total || 0,
      activeSources: sources,
      byCategory,
    };
  },

  async getFiles({ sourceId, category, page = 1, limit = 50, sortBy = "size", sortDir = -1 }) {
    const filter = {};
    if (sourceId) filter.sourceId = sourceId;
    if (category) filter.category = category;

    const skip = (page - 1) * limit;
    const [files, total] = await Promise.all([
      File.find(filter)
        .sort({ [sortBy]: sortDir })
        .skip(skip)
        .limit(limit)
        .lean(),
      File.countDocuments(filter),
    ]);

    return { files, total, page, pages: Math.ceil(total / limit) };
  },
};
