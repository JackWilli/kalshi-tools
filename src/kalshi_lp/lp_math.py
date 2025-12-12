from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Sequence, Tuple

Side = Literal["yes", "no"]


@dataclass
class LPOrder:
    side: Side
    price: int  # cents
    quantity: int  # resting size


def _compute_side_score(
    side_levels: Sequence[Tuple[int, int]],  # [(price, qty)], best first
    my_orders: Sequence[LPOrder],
    target_size: int,
    discount_factor: float,
) -> Tuple[float, Optional[int], float, float]:
    if not side_levels:
        return 0.0, None, 0.0, 0.0

    sorted_levels = sorted(side_levels, key=lambda x: x[0], reverse=True)

    qualifying: List[Tuple[int, int]] = []
    total_size = 0

    for price, qty in sorted_levels:
        if total_size >= target_size:
            break
        qualifying.append((price, qty))
        total_size += qty

    if total_size == 0:
        return 0.0, None, 0.0, 0.0

    ref_price = qualifying[0][0]
    min_qual_price = qualifying[-1][0]

    def weight(p: int) -> float:
        ticks = ref_price - p
        return discount_factor ** max(ticks, 0)

    total_score_all = sum(weight(p) * q for p, q in qualifying)

    my_score = 0.0
    for o in my_orders:
        if o.quantity <= 0:
            continue
        if o.price > ref_price or o.price < min_qual_price:
            continue
        my_score += weight(o.price) * o.quantity

    if total_score_all == 0:
        return 0.0, ref_price, 0.0, 0.0

    return my_score / total_score_all, ref_price, total_score_all, my_score


def normalized_side_score_to_rewards(
    normalized_side_score: float,
    total_reward_pool: float,
) -> float:
    """
    Convert a normalized qualifying side score to expected dollar rewards.

    Args:
        normalized_side_score: Your share of one side (YES or NO), between 0-1
        total_reward_pool: Total reward pool for entire market (both sides)

    Returns:
        Expected rewards in dollars

    Note:
        The reward pool is split 50/50 between YES and NO sides.
        If you have a normalized qualifying side score of 0.10 (10% of YES side)
        and the total pool is $100, you get 10% of $50 = $5.
    """
    return normalized_side_score * (total_reward_pool / 2)


def compute_snapshot_lp_score(
    yes_levels: Sequence[Tuple[int, int]],
    no_levels: Sequence[Tuple[int, int]],
    my_orders: Sequence[LPOrder],
    target_size: int,
    discount_factor: float,
) -> Dict[str, float | int | None]:
    my_yes = [o for o in my_orders if o.side == "yes"]
    my_no = [o for o in my_orders if o.side == "no"]

    yes_norm, yes_ref, yes_total, yes_mine = _compute_side_score(
        yes_levels,
        my_yes,
        target_size,
        discount_factor,
    )
    no_norm, no_ref, no_total, no_mine = _compute_side_score(
        no_levels,
        my_no,
        target_size,
        discount_factor,
    )

    if yes_total == 0 and no_total == 0:
        combined = 0.0
    elif yes_total == 0:
        combined = no_norm
    elif no_total == 0:
        combined = yes_norm
    else:
        combined = 0.5 * (yes_norm + no_norm)

    return {
        "yes_normalized": yes_norm,
        "no_normalized": no_norm,
        "combined_score": combined,
        "yes_reference_price": yes_ref,
        "no_reference_price": no_ref,
        "yes_total_weighted": yes_total,
        "no_total_weighted": no_total,
        "yes_my_weighted": yes_mine,
        "no_my_weighted": no_mine,
    }
