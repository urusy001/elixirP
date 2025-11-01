import {apiGet} from "./api.js";

export async function searchProducts({q = "", page = 0, limit} = {}) {
    const url = new URL("/search", location.origin);
    url.searchParams.set("q", q);
    if (page) url.searchParams.set("page", page);
    if (limit) url.searchParams.set("limit", limit);
    return apiGet(url.toString());
}

export async function getProductDetail(onec_id) {
    return apiGet(`/product/${onec_id}/json`);
}