import { apiGet } from "./api.js";

export async function searchProducts({
                                         q = "",
                                         page = 0,
                                         limit,
                                         tgCategoryIds,
                                         tgCategoryMode = "any",
                                         sortBy = "name",
                                         sortDir = "asc",
                                     } = {}) {
    const params = new URLSearchParams();
    params.set("q", q ?? "");
    params.set("page", String(page ?? 0));
    if (limit != null) params.set("limit", String(limit));

    // categories
    if (tgCategoryIds != null) {
        const csv = Array.isArray(tgCategoryIds)
            ? tgCategoryIds.map(x => String(x).trim()).filter(Boolean).join(",")
            : String(tgCategoryIds).trim();
        if (csv) params.set("tg_category_ids", csv);
    }
    if (tgCategoryMode === "all" || tgCategoryMode === "any") {params.set("tg_category_mode", tgCategoryMode)}
    if (sortBy === "name" || sortBy === "price") params.set("sort_by", sortBy);
    if (sortDir === "asc" || sortDir === "desc") params.set("sort_dir", sortDir);
    return apiGet(`/search/products?${params.toString()}`);
}

export async function getProductDetail(onec_id) {
    return apiGet(`/product/${onec_id}/json`);
}