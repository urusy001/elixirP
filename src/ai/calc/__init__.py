from __future__ import annotations

import math
import uuid
import matplotlib.pyplot as plt

from typing import Union
from pathlib import Path
from matplotlib.patches import FancyBboxPatch

from config import DATA_DIR
from src.ai.calc.drugparams import PEPTIDE_DATA, DrugName


# ============================================================
# Helpers (robust param access)
# ============================================================

def _get(drug, name: str, default=None):
    return getattr(drug, name, default)


def _require_float(drug, *names: str) -> float:
    for n in names:
        v = getattr(drug, n, None)
        if v is not None:
            v = float(v)
            if v > 0:
                return v
    raise ValueError(f"Missing required positive float field in drugparams: one of {names}")


# ============================================================
# 2-compartment + depot (SC) math
# Amount (mg): systemic amount = A_c + A_p; depot not counted.
# ============================================================

def beta_from_micro(k10: float, k12: float, k21: float) -> float:
    # Two-comp eigenvalues: alpha, beta for IV bolus in central; beta = terminal slope
    S = k10 + k12 + k21
    disc = S * S - 4.0 * k10 * k21
    if disc < 0:
        disc = 0.0
    return 0.5 * (S - math.sqrt(disc))


def k10_from_terminal_half_life(t_half_days: float, k12: float, k21: float) -> float:
    """
    Choose k10 so that terminal beta == ln(2)/t_half_days, given k12,k21.
    Closed-form inversion:
      beta = 0.5*(S - sqrt(S^2 - 4*k10*k21)), S=k10+k12+k21
      => k10 = [beta*(k12+k21) - beta^2] / (k21 - beta)
    """
    if t_half_days <= 0:
        raise ValueError("t_half_days must be > 0")

    beta_target = math.log(2) / t_half_days

    # Ensure k21 > beta_target to keep denominator positive/stable
    if k21 <= beta_target * 1.000001:
        k21 = beta_target * 1.5

    num = beta_target * (k12 + k21) - beta_target * beta_target
    den = (k21 - beta_target)
    k10 = num / den

    if not math.isfinite(k10) or k10 <= 0:
        # numeric fallback (monotonic in k10)
        lo, hi = 1e-6, 100.0
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            b = beta_from_micro(mid, k12, k21)
            if b > beta_target:
                hi = mid
            else:
                lo = mid
        k10 = 0.5 * (lo + hi)

    return float(k10)


def rk4_step(Adep: float, Ac: float, Ap: float, dt: float, ka: float, k10: float, k12: float, k21: float) -> tuple[float, float, float]:
    """
    ODE:
      dAdep/dt = -ka*Adep
      dAc/dt   =  ka*Adep - (k10+k12)*Ac + k21*Ap
      dAp/dt   =  k12*Ac - k21*Ap
    """

    def deriv(dep: float, c: float, p: float):
        ddep = -ka * dep
        dc   =  ka * dep - (k10 + k12) * c + k21 * p
        dp   =  k12 * c - k21 * p
        return ddep, dc, dp

    k1 = deriv(Adep, Ac, Ap)
    k2 = deriv(Adep + 0.5*dt*k1[0], Ac + 0.5*dt*k1[1], Ap + 0.5*dt*k1[2])
    k3 = deriv(Adep + 0.5*dt*k2[0], Ac + 0.5*dt*k2[1], Ap + 0.5*dt*k2[2])
    k4 = deriv(Adep + dt*k3[0],     Ac + dt*k3[1],     Ap + dt*k3[2])

    Adep_n = Adep + (dt/6.0)*(k1[0] + 2*k2[0] + 2*k3[0] + k4[0])
    Ac_n   = Ac   + (dt/6.0)*(k1[1] + 2*k2[1] + 2*k3[1] + k4[1])
    Ap_n   = Ap   + (dt/6.0)*(k1[2] + 2*k2[2] + 2*k3[2] + k4[2])

    # avoid tiny negatives
    if Adep_n < 0: Adep_n = 0.0
    if Ac_n < 0:   Ac_n = 0.0
    if Ap_n < 0:   Ap_n = 0.0

    return Adep_n, Ac_n, Ap_n


def _t_peak_for_ka(
    ka: float,
    dose_mg_systemic_to_depot: float,
    k10: float, k12: float, k21: float,
    dt: float,
    t_end: float
) -> float:
    # single dose at t=0 into depot; return time of max systemic (Ac+Ap)
    Adep = dose_mg_systemic_to_depot
    Ac = 0.0
    Ap = 0.0

    best_t = 0.0
    best_val = -1.0
    t = 0.0

    while t <= t_end + 1e-12:
        val = Ac + Ap
        if val > best_val:
            best_val = val
            best_t = t
        Adep, Ac, Ap = rk4_step(Adep, Ac, Ap, dt, ka, k10, k12, k21)
        t += dt

    return best_t


def solve_ka_by_target_tmax_two_comp(
    target_tmax_days: float,
    dose_mg_systemic_to_depot: float,  # already F*dose
    k10: float, k12: float, k21: float,
    dt: float = 0.005
) -> float:
    """
    Choose ka so that the peak time of systemic amount (Ac+Ap) matches target_tmax_days.
    We do bisection on ka using numeric peak detection.
    """
    if target_tmax_days <= 0:
        raise ValueError("target_tmax_days must be > 0")
    if dose_mg_systemic_to_depot <= 0:
        raise ValueError("dose_mg_systemic_to_depot must be > 0")

    # simulate long enough to capture peak
    t_end = max(10.0, 6.0 * target_tmax_days)

    lo = 1e-4
    hi = 50.0

    t_lo = _t_peak_for_ka(lo, dose_mg_systemic_to_depot, k10, k12, k21, dt, t_end)
    t_hi = _t_peak_for_ka(hi, dose_mg_systemic_to_depot, k10, k12, k21, dt, t_end)

    # If even hi peaks later than target => can't reach target; return hi
    if t_hi > target_tmax_days:
        return hi
    # If even lo peaks earlier than target => already too fast; return lo
    if t_lo < target_tmax_days:
        return lo

    for _ in range(40):
        mid = 0.5 * (lo + hi)
        tm = _t_peak_for_ka(mid, dose_mg_systemic_to_depot, k10, k12, k21, dt, t_end)

        # if peak too late => need faster absorption => increase ka
        if tm > target_tmax_days:
            lo = mid
        else:
            hi = mid

    return 0.5 * (lo + hi)


# ============================================================
# Course logic
# ============================================================

def n_doses_from_course(weeks: float, interval_days: float) -> int:
    """
    FIX #9: doses at times 0, d, 2d, ... strictly < total_days.
    N = ceil(total_days / d)
    Example: weeks=5 => 35d, d=7 => N=5 (0..28)
    Example: weeks=4 => 28d, d=7 => N=4 (0..21)
    """
    if weeks <= 0:
        raise ValueError("weeks должно быть > 0")
    if interval_days <= 0:
        raise ValueError("interval_days должно быть > 0")
    total_days = weeks * 7.0
    return max(1, int(math.ceil(total_days / interval_days)))


def simulate_course_amount_only(
    drug_name_key: Union[DrugName, str],
    dose_mg: float,
    weeks: float,
    interval_days: float,
    dt_base: float = 0.1,          # ~2.4h
    dt_dense: float = 0.02,        # ~0.48h
    dense_window_days: float = 3.0 # around injections
):
    """
    Amount-only (mg), 2-comp + depot, F applied (variant A), lag supported.
    Faster integration: single ODE solve with dosing events (no superposition loop).
    """
    if dose_mg <= 0:
        raise ValueError("dose_mg должно быть > 0")

    drug = PEPTIDE_DATA[drug_name_key]

    # REQUIRED: half-life from drugparams (you said it will always exist)
    t_half_days = _require_float(drug, "t_half_days", "t_half_days_fallback")

    # Variant A: apply bioavailability
    F = float(_get(drug, "F", 1.0))
    if not (0 < F <= 1.0):
        raise ValueError(f"Invalid F for {drug_name_key}: {F}")

    # Lag time (hours) optional
    tlag_h = float(_get(drug, "tlag_h", 0.0))
    if tlag_h < 0:
        tlag_h = 0.0
    tlag_days = tlag_h / 24.0

    # 2-comp distribution defaults (can be added to drugparams later)
    k12 = float(_get(drug, "k12_per_day", _get(drug, "k12_per_day_fallback", 1.2)))
    k21 = float(_get(drug, "k21_per_day", _get(drug, "k21_per_day_fallback", 0.8)))
    if k12 <= 0: k12 = 1.2
    if k21 <= 0: k21 = 0.8

    # Calibrate k10 to match terminal half-life
    k10 = k10_from_terminal_half_life(t_half_days, k12, k21)
    beta = beta_from_micro(k10, k12, k21)  # should ~= ln2/t_half
    t_half_check = math.log(2) / beta if beta > 0 else float("nan")

    # ka from Tmax if provided; else fallback to something faster than terminal
    tmax_h = _get(drug, "tmax_h", None)
    dose_to_depot = F * dose_mg  # apply F here (variant A)

    if tmax_h is not None and float(tmax_h) > 0:
        target_tmax_days = float(tmax_h) / 24.0
        ka = solve_ka_by_target_tmax_two_comp(
            target_tmax_days=target_tmax_days,
            dose_mg_systemic_to_depot=dose_to_depot,
            k10=k10, k12=k12, k21=k21,
            dt=0.005
        )
    else:
        # reasonable fallback: absorption faster than terminal
        ka = max(0.3, 3.0 * beta)

    # Dosing schedule
    n_doses = n_doses_from_course(weeks, interval_days)
    total_days = weeks * 7.0
    inj_times = [i * interval_days for i in range(n_doses)]               # 0, d, 2d...
    dose_event_times = [t + tlag_days for t in inj_times]                 # apply lag

    # Simulation end: last event + 5 half-lives (washout)
    t_end = dose_event_times[-1] + 5.0 * t_half_days

    # Integrate ODE with event dosing
    times: list[float] = []
    amounts_mg: list[float] = []

    Adep = 0.0
    Ac = 0.0
    Ap = 0.0

    event_idx = 0
    t = 0.0

    while t <= t_end + 1e-12:
        # apply all due dose events
        while event_idx < len(dose_event_times) and t >= dose_event_times[event_idx] - 1e-12:
            Adep += dose_to_depot
            event_idx += 1

        A_sys = Ac + Ap
        times.append(t)
        amounts_mg.append(A_sys)

        # adaptive dt near injections
        dt = dt_base
        if event_idx < len(dose_event_times):
            if abs(dose_event_times[event_idx] - t) < dense_window_days:
                dt = min(dt, dt_dense)
        if event_idx > 0:
            if (t - dose_event_times[event_idx - 1]) < dense_window_days:
                dt = min(dt, dt_dense)

        # don't jump over the next event
        if event_idx < len(dose_event_times):
            next_event = dose_event_times[event_idx]
            if t < next_event and t + dt > next_event:
                dt = max(1e-6, next_event - t)

        # clamp last step
        if t + dt > t_end:
            dt = t_end - t
            if dt <= 1e-12:
                break

        Adep, Ac, Ap = rk4_step(Adep, Ac, Ap, dt, ka, k10, k12, k21)
        t += dt

    base_label = (
        f"{_get(drug, 'name', str(drug_name_key))}: {dose_mg:g}мг каждые {interval_days:g}д"
    )

    # короткий инфо-блок для подписи на графике
    info = {
        "F": F,
        "t_half_days": t_half_days,
        "t_half_check": t_half_check,
        "tmax_h": float(tmax_h) if (tmax_h is not None) else None,
        "ka": ka,
        "k10": k10,
        "k12": k12,
        "k21": k21,
        "tlag_h": tlag_h,
        "weeks": weeks,
        "interval_days": interval_days,
        "dose_mg": dose_mg,
    }

    return times, amounts_mg, base_label, info


# ============================================================
# Plotting
# ============================================================

def save_single_plot(x_data, y_data, title, y_label, legend_label, filename, info: dict | None = None):
    plt.figure(figsize=(12, 6))

    plt.plot(x_data, y_data, linewidth=2.2, label=legend_label)
    plt.fill_between(x_data, y_data, 0, alpha=0.18)

    ax = plt.gca()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_alpha(0.30)
    ax.spines["bottom"].set_alpha(0.30)

    # ---- X ticks: every 2 days
    x_min = float(x_data[0]) if x_data else 0.0
    x_max = float(x_data[-1]) if x_data else 0.0
    start_tick = math.floor(x_min / 2.0) * 2.0
    end_tick = math.ceil(x_max / 2.0) * 2.0
    ax.set_xticks([start_tick + 2.0 * i for i in range(int((end_tick - start_tick) / 2.0) + 1)])

    # ---- Y flexible: 2x max
    y_max = max(y_data) if y_data else 0.0
    y_top = max(1e-9, 2.0 * float(y_max))
    ax.set_ylim(0.0, y_top)

    # ---- Titles/labels (EVEN smaller)
    ax.set_title(title, fontsize=11, pad=8)
    ax.set_xlabel("Дни от начала", fontsize=7)
    ax.set_ylabel(y_label, fontsize=7)

    # tick label sizes
    ax.tick_params(axis="x", labelsize=6, pad=2)
    ax.tick_params(axis="y", labelsize=6, pad=2)

    # grid
    ax.grid(True, which="major", linestyle="-", alpha=0.18)
    ax.grid(True, which="minor", linestyle="--", alpha=0.10)
    ax.minorticks_on()

    # legend smaller
    ax.legend(fontsize=7, loc="upper right", frameon=True, fancybox=True, framealpha=0.85)

    # ---- Friendly info box (smaller)
    if info:
        text = (
            f"Доза: {info.get('dose_mg', 0):g}мг\n"
            f"Интервал: {info.get('interval_days', 0):g}д\n"
            f"Курс: {info.get('weeks', 0):g}нед\n"
            f"Усвоение: {info.get('F', 1.0)*100:.2f}%\n"
            f"t½: {info.get('t_half_days', 0):.2f}д"
        )
        ax.text(
            0.02, 0.98, text,
            transform=ax.transAxes,
            va="top", ha="left",
            fontsize=7,
            bbox=dict(
                boxstyle="round,pad=0.35",
                facecolor="white",
                alpha=0.82,
                edgecolor="#cccccc",
                linewidth=0.8
            )
        )

    plt.tight_layout()
    out_path = DATA_DIR / filename
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()

def generate_drug_graphs(drug_key: DrugName, weeks: float, dose_mg: float, interval_days: float) -> str:
    times, amounts, base_label, info = simulate_course_amount_only(
        drug_key, dose_mg=dose_mg, weeks=weeks, interval_days=interval_days
    )

    sanitized_name = str(drug_key).lower().replace(" ", "_")
    param_suffix = f"{dose_mg:g}mg_{weeks:g}wks_{interval_days:g}d.png"
    fname_amount = f"plot_{sanitized_name}_amount_{param_suffix}"

    save_single_plot(
        x_data=times,
        y_data=amounts,
        title=f"Содержание вещества в организме (мг) — {PEPTIDE_DATA[drug_key].name}",
        y_label="Содержание, мг",
        legend_label=base_label,
        filename=fname_amount,
        info=info
    )

    print(f"Successfully generated graph: {fname_amount}")
    return fname_amount

# ============================================================
# Scale image helper (оставил как у тебя)
# ============================================================

def _nice_max(x: float) -> float:
    if x <= 100:
        return 100.0
    if not math.isfinite(x):
        return 100.0
    exp = 10 ** int(math.floor(math.log10(x)))
    mant = x / exp
    if mant <= 1:   nice = 1
    elif mant <= 2: nice = 2
    elif mant <= 5: nice = 5
    else:           nice = 10
    return float(nice * exp)


def plot_filled_scale(
    value: float,
    max_value: float | None = 100,
    major_step: int = 5,
    minor_step: int = 1,
    figsize=(12, 2.0),
    fill_color="#62b25f",
    bg_color="#e9eef2",
    tick_color="#6b6f76",
    label_color="#3b3f45",
) -> Path:
    if value < 0:
        raise ValueError("value must be >= 0")

    is_inf = math.isinf(value)
    if max_value is None:
        max_value = _nice_max(value if math.isfinite(value) else 100.0)
    if max_value <= 0:
        raise ValueError("max_value must be > 0")

    v_draw = max_value if is_inf else min(value, max_value)

    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(-0.5, max_value + 0.5)
    ax.set_ylim(0.0, 1.8)
    ax.axis("off")

    bar_y = 1.05
    bar_h = 0.55
    r = bar_h / 2.0

    # background bar
    ax.add_patch(FancyBboxPatch(
        (0, bar_y), max_value, bar_h,
        boxstyle=f"round,pad=0,rounding_size={r}",
        linewidth=0, facecolor=bg_color
    ))

    # filled bar
    ax.add_patch(FancyBboxPatch(
        (0, bar_y), v_draw, bar_h,
        boxstyle=f"round,pad=0,rounding_size={r}",
        linewidth=0, facecolor=fill_color
    ))

    # -----------------------------
    # SCALE INSIDE THE BAR (FULL LENGTH)
    # -----------------------------
    inner_left = 0.0
    inner_right = float(max_value)  # <-- FULL BAR END (not v_draw)

    baseline_y = bar_y + bar_h * 0.62
    tick_top = baseline_y
    tick_bottom_major = bar_y + bar_h * 0.18
    tick_bottom_mid   = bar_y + bar_h * 0.26
    tick_bottom_minor = bar_y + bar_h * 0.33
    label_y = bar_y + bar_h * 0.08

    ax.plot([inner_left, inner_right], [baseline_y, baseline_y],
            color=tick_color, linewidth=1)

    label_step = major_step
    if max_value > 200: label_step = major_step * 2
    if max_value > 500: label_step = major_step * 4

    i = 0.0
    while i <= inner_right + 1e-9:
        if (major_step > 0) and (abs(i % (major_step * 2)) < 1e-9):
            y0, lw = tick_bottom_major, 1.2
        elif (major_step > 0) and (abs(i % major_step) < 1e-9):
            y0, lw = tick_bottom_mid, 1.1
        else:
            y0, lw = tick_bottom_minor, 0.9

        ax.plot([i, i], [tick_top, y0], color=tick_color, linewidth=lw)

        if label_step > 0 and abs(i % label_step) < 1e-9:
            ax.text(i, label_y, f"{int(round(i))}",
                    ha="center", va="bottom",
                    fontsize=10, color=label_color)

        i += float(minor_step)

    if is_inf:
        ax.text(max_value, bar_y + bar_h + 0.05, "∞",
                ha="right", va="bottom", fontsize=12, color=label_color)

    fig.tight_layout(pad=0.6)
    out_path = DATA_DIR / f"{uuid.uuid4().hex}.png"
    fig.savefig(out_path, dpi=200, bbox_inches="tight", transparent=True)
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    plot_filled_scale(25)
