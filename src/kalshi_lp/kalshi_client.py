# src/kalshi_lp/kalshi_client.py
import os
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from dotenv import load_dotenv
from kalshi_python_async import Configuration, KalshiClient

from .lp_math import LPOrder, Side
from .money import Money

load_dotenv()


@dataclass
class IncentiveProgram:
    """Represents a Kalshi liquidity incentive program."""

    id: str
    market_ticker: str
    start_date: datetime
    end_date: datetime
    period_reward: Money  # Total reward pool for the program
    discount_factor: float  # Converted from discount_factor_bps (9000 bps = 0.9)
    target_size: int  # contracts
    days_remaining: float

    @property
    def total_days(self) -> float:
        """Total days in the program period."""
        return (self.end_date - self.start_date).total_seconds() / 86400

    @property
    def daily_reward_pool(self) -> Money:
        """Average daily reward pool (constant throughout program)."""
        if self.total_days <= 0:
            return Money.zero()
        result: Money = self.period_reward / self.total_days
        return result

    @property
    def remaining_rewards(self) -> Money:
        """Total remaining rewards to be earned."""
        return self.daily_reward_pool * self.days_remaining


def get_client() -> KalshiClient:
    api_key_id = os.environ["KALSHI_API_KEY_ID"]
    key_path = os.environ["KALSHI_PRIVATE_KEY_PATH"]

    with open(key_path, "r") as f:
        private_key = f.read()

    config = Configuration(
        host="https://api.elections.kalshi.com/trade-api/v2",
    )
    config.api_key_id = api_key_id
    config.private_key_pem = private_key

    return KalshiClient(config)


async def verify_market_exists(client: KalshiClient, ticker: str) -> bool:
    """Check if a market exists and return basic info."""
    try:
        response = await client.get_market(ticker=ticker)
        market = response.market
        print(f"Found market: {market.ticker}")
        print(f"  Title: {market.title}")
        print(f"  Status: {market.status}")
        return True
    except Exception as e:
        print(f"Error: Could not find market '{ticker}'")
        print(f"Details: {e}")
        return False


async def fetch_orderbook(
    client: KalshiClient,
    ticker: str,
) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    ob_resp = await client.get_market_orderbook(ticker=ticker)

    # Convert price from dollars (string) to cents (int), quantity is already int
    # Price comes as string like '0.0100' representing $0.01 (1 cent)
    yes_levels = [
        (int(float(p) * 100), int(q)) for p, q in ob_resp.orderbook.yes_dollars
    ]
    no_levels = [(int(float(p) * 100), int(q)) for p, q in ob_resp.orderbook.no_dollars]
    return yes_levels, no_levels


async def fetch_my_resting_bids(
    client: KalshiClient,
    ticker: str,
) -> List[LPOrder]:
    resp = await client.get_orders(
        ticker=ticker,
        status="resting",
        limit=500,
    )

    orders: List[LPOrder] = []
    for o in resp.orders:
        if o.ticker != ticker or o.status != "resting":
            continue
        if o.action != "buy" or o.type != "limit":
            continue

        if o.side == "yes":
            side: Side = "yes"
            price = Money.from_cents(o.yes_price)  # API returns cents
        elif o.side == "no":
            side = "no"
            price = Money.from_cents(o.no_price)  # API returns cents
        else:
            continue

        if o.remaining_count <= 0:
            continue

        orders.append(
            LPOrder(
                side=side,
                price=price,
                quantity=o.remaining_count,
            ),
        )

    return orders


async def fetch_incentive_programs(
    client: KalshiClient,
    status: str = "active",
    incentive_type: str = "liquidity",
) -> List[IncentiveProgram]:
    """
    Fetch liquidity incentive programs from Kalshi API.

    Args:
        client: Authenticated Kalshi client
        status: Filter by program status (active, upcoming, closed, paid_out, all)
        incentive_type: Filter by type (liquidity, volume, all)

    Returns:
        List of IncentiveProgram objects
    """
    programs: List[IncentiveProgram] = []
    cursor: Optional[str] = None

    # Handle pagination
    while True:
        try:
            # Call SDK method - filtering by type happens after fetching
            if cursor:
                response = await client.get_incentive_programs(
                    status=status,
                    limit=100,
                    cursor=cursor,
                )
            else:
                response = await client.get_incentive_programs(status=status, limit=100)
        except Exception as e:
            print(f"Error fetching incentive programs: {e}")
            import traceback

            traceback.print_exc()
            break

        if not response.incentive_programs:
            break

        # Parse and convert each program
        for prog in response.incentive_programs:
            try:
                # Skip if not a liquidity program
                if prog.incentive_type != incentive_type and incentive_type != "all":
                    continue

                # Parse dates (they might already be datetime objects)
                if isinstance(prog.start_date, datetime):
                    start_date = prog.start_date
                else:
                    start_date = datetime.fromisoformat(
                        prog.start_date.replace("Z", "+00:00"),
                    )

                if isinstance(prog.end_date, datetime):
                    end_date = prog.end_date
                else:
                    end_date = datetime.fromisoformat(
                        prog.end_date.replace("Z", "+00:00"),
                    )

                # Calculate days remaining
                now = datetime.now(start_date.tzinfo)
                days_remaining = max(0, (end_date - now).total_seconds() / 86400)

                # Convert discount_factor from bps to decimal (9000 bps = 0.9)
                discount_factor = 0.9  # Default
                if prog.discount_factor_bps is not None:
                    discount_factor = prog.discount_factor_bps / 10000.0

                # Use target_size or default
                target_size = prog.target_size if prog.target_size is not None else 1000

                programs.append(
                    IncentiveProgram(
                        id=prog.id,
                        market_ticker=prog.market_ticker,
                        start_date=start_date,
                        end_date=end_date,
                        period_reward=Money.from_centicents(
                            prog.period_reward
                        ),  # API returns centicents
                        discount_factor=discount_factor,
                        target_size=target_size,
                        days_remaining=days_remaining,
                    ),
                )
            except Exception as e:
                print(f"Error parsing program {getattr(prog, 'id', 'unknown')}: {e}")
                import traceback

                traceback.print_exc()
                continue

        # Check for next page
        cursor = getattr(response, "next_cursor", None)
        if not cursor:
            break

    return programs


async def get_incentive_program_for_ticker(
    client: KalshiClient,
    ticker: str,
    status: str = "active",
    incentive_type: str = "liquidity",
) -> IncentiveProgram:
    """
    Fetch incentive program for a specific ticker.

    This is a convenience function that wraps fetch_incentive_programs() and
    finds the incentive program for a specific market ticker. Eliminates duplicate
    program-fetching patterns across CLI modules.

    Args:
        client: Authenticated Kalshi client
        ticker: Market ticker (e.g., "PRES-2024")
        status: Incentive program status filter (default: "active")
        incentive_type: Type of incentive (default: "liquidity")

    Returns:
        IncentiveProgram for the specified ticker

    Raises:
        ValueError: If no matching incentive program is found
    """
    programs = await fetch_incentive_programs(
        client, status=status, incentive_type=incentive_type
    )
    incentive_program = next((p for p in programs if p.market_ticker == ticker), None)

    if incentive_program is None:
        raise ValueError(
            f"No {status} {incentive_type} incentive program found for ticker: {ticker}"
        )

    return incentive_program
