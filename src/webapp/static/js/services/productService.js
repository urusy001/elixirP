import { apiGet } from "./api.js";

// Supports:
// - tg_category_ids as array [1,2] OR csv "1,2"
// - tg_category_mode: "any" | "all"
// - sort_by: "default" | "alpha" | "price"
// - sort_dir: "asc" | "desc"
export async function searchProducts({
                                         q = "",
                                         page = 0,
                                         limit,

                                         tg_category_ids,
                                         tg_category_mode = "any",

                                         sort_by = "default",
                                         sort_dir = "asc",
                                     } = {}) {
    const url = new URL("/search", location.origin);

    url.searchParams.set("q", q ?? "");
    url.searchParams.set("page", String(page ?? 0));
    if (limit != null) url.searchParams.set("limit", String(limit));

    // ✅ categories: send as repeatable params (FastAPI List[int] friendly)
    if (tg_category_ids != null) {
        let ids = [];
        if (Array.isArray(tg_category_ids)) {
            ids = tg_category_ids;
        } else {
            // allow "1,2,3" or "1 2 3"
            ids = String(tg_category_ids)
                .split(/[, ]+/g)
                .map(s => s.trim())
                .filter(Boolean);
        }

        for (const id of ids) {
            url.searchParams.append("tg_category_ids", String(id));
        }
    }

    if (tg_category_mode === "all" || tg_category_mode === "any") {
        url.searchParams.set("tg_category_mode", tg_category_mode);
    }

    if (sort_by === "default" || sort_by === "alpha" || sort_by === "price") {
        url.searchParams.set("sort_by", sort_by);
    }

    if (sort_dir === "asc" || sort_dir === "desc") {
        url.searchParams.set("sort_dir", sort_dir);
    }

    return apiGet(url.toString());
}

export async function getProductDetail(onec_id) {
    return apiGet(`/product/${onec_id}/json`);
}