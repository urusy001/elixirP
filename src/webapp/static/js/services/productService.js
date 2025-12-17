import { apiGet } from "./api.js";

// tgCategoryIds: array of numbers/strings OR csv string "1,2,3"
// tgCategoryMode: "any" | "all"
export async function searchProducts({
                                         q = "",
                                         page = 0,
                                         limit,
                                         tgCategoryIds,
                                         tgCategoryMode = "any",
                                     } = {}) {
    const url = new URL("/search", location.origin);

    url.searchParams.set("q", q ?? "");
    url.searchParams.set("page", String(page ?? 0));
    if (limit != null) url.searchParams.set("limit", String(limit));

    // ✅ categories filter
    if (tgCategoryIds != null) {
        const csv = Array.isArray(tgCategoryIds)
            ? tgCategoryIds.map((x) => String(x).trim()).filter(Boolean).join(",")
            : String(tgCategoryIds).trim();

        if (csv) url.searchParams.set("tg_category_ids", csv);
    }

    if (tgCategoryMode === "all" || tgCategoryMode === "any") {
        url.searchParams.set("tg_category_mode", tgCategoryMode);
    }

    return apiGet(url.toString());
}

export async function getProductDetail(onec_id) {
    return apiGet(`/product/${onec_id}/json`);
}