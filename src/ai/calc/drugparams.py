from dataclasses import dataclass
from typing import Literal, Optional, Dict, Tuple

DrugName = Literal[
    "semaglutide",
    "tirzepatide",
    "retatrutide",
    "cagrilintide",
    "survodutide",
    "mazdutide",
]

Route = Literal["sc", "oral"]

@dataclass(frozen=True)
class DrugParams:
    key: DrugName
    name: str
    route: Route
    t_half_days: float
    F: float
    tmax_h: Optional[float]
    targets: str = ""
    refs: Tuple[str, ...] = ()
    V_L: Optional[float] = None
    CL_L_per_h: Optional[float] = None
    note: str = ""


PEPTIDE_DATA: Dict[DrugName, DrugParams] = {
    "semaglutide": DrugParams(
        key="semaglutide",
        name="Семаглутид",
        route="sc",
        t_half_days=7.0,
        F=0.89,
        tmax_h=48.0,
        targets="GLP-1",
        V_L=12.5,
        CL_L_per_h=0.05,
        refs=(
            "https://www.accessdata.fda.gov/drugsatfda_docs/label/2025/209637s025lbl.pdf",
        ),
        note="П/к: Tmax 1–3 дня; абсолютная биодоступность 89%; t½ ~1 неделя; V ~12.5 л; CL/F ~0.05 л/ч.",
    ),

    "tirzepatide": DrugParams(
        key="tirzepatide",
        name="Тирзепатид",
        route="sc",
        t_half_days=5.5,
        F=0.80,
        tmax_h=36.0,
        targets="GLP-1/GIP",
        V_L=10.3,
        CL_L_per_h=0.061,
        refs=(
            "https://www.accessdata.fda.gov/drugsatfda_docs/label/2022/215866s000lbl.pdf",
        ),
        note="П/к: t½ ~5 дней; Vss/F ~10.3 л; CL/F ~0.061 л/ч; связывание с альбумином ~99%.",
    ),

    "retatrutide": DrugParams(
        key="retatrutide",
        name="Ретатрутид",
        route="sc",
        t_half_days=6.0,
        F=0.80,
        tmax_h=24.0,
        targets="GLP-1/GIP/GCGR",
        V_L=11.0,
        CL_L_per_h=None,
        refs=(
            "https://sio-obesita.org/wp-content/uploads/2022/12/Urva-S-Lancet-Nov-2022-SCamastra.pdf",
        ),
        note="Данные фазовых исследований: медианный Tmax ~12–48 ч; терминальный t½ ~6 дней; PK дозопропорциональна.",
    ),

    "cagrilintide": DrugParams(
        key="cagrilintide",
        name="Кагрилинтид",
        route="sc",
        t_half_days=8,
        F=0.8,
        tmax_h=48.0,
        targets="Амилин (агонист амиллиновых рецепторов)",
        V_L=7.6,
        CL_L_per_h=None,
        refs=(
            "https://pubmed.ncbi.nlm.nih.gov/33894838/",
        ),
        note="Сообщалось: t½ 159–195 ч и медианный Tmax 24–72 ч. Абсолютная биодоступность у человека публикуется непоследовательно; 0.30 — грубая константа.",
    ),

    "survodutide": DrugParams(
        key="survodutide",
        name="Сурводутид",
        route="sc",
        t_half_days=6,
        F=0.80,
        tmax_h=30.0,
        targets="GLP-1/GCGR",
        V_L=None,
        CL_L_per_h=None,
        refs=(
            "https://dom-pubs.onlinelibrary.wiley.com/doi/full/10.1111/dom.14948",
            "https://www.journal-of-hepatology.eu/cms/10.1016/j.jhep.2024.06.003/attachment/969afc96-1bba-46f8-97d9-56b9ea46cc16/mmc4.pdf",
        ),
        note="Клинические данные: терминальный t½ >100 ч; в обзорах часто встречается ~109–115 ч. По умолчанию оставлено ~4.6 дня.",
    ),

    "mazdutide": DrugParams(
        key="mazdutide",
        name="Маздутид",
        route="sc",
        t_half_days=8,
        F=0.8,
        tmax_h=72.0,
        targets="GLP-1/GCGR",
        V_L=None,
        CL_L_per_h=None,
        refs=(
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC9561728/",
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC8374649/",
        ),
        note="По публикациям: медианный Tmax ~72 ч; t½ сообщается от ~6–17 дней (в отдельных когортах) до ~45 дней (в некоторых режимах/дозах).",
    ),
}