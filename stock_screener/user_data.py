from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_USER_DATA_PATH = Path.home() / ".stock-screener" / "user_data.json"
DEFAULT_USER_DATA: dict[str, Any] = {
    "watchlist": [],
    "portfolio": [],
    "theme": "Dark",
}


def load_user_data(
    path: Path | None = None,
) -> tuple[dict[str, Any], str | None]:
    data_path = path or DEFAULT_USER_DATA_PATH
    try:
        with data_path.open("r", encoding="utf-8") as file:
            loaded = json.load(file)
    except FileNotFoundError:
        return DEFAULT_USER_DATA.copy(), None
    except (OSError, json.JSONDecodeError) as exc:
        return DEFAULT_USER_DATA.copy(), f"Could not read local preferences: {exc}"

    if not isinstance(loaded, dict):
        return DEFAULT_USER_DATA.copy(), "Local preferences must be a JSON object."

    watchlist = loaded.get("watchlist", [])
    portfolio = loaded.get("portfolio", [])
    theme = loaded.get("theme", "Dark")
    if not isinstance(watchlist, list) or not all(
        isinstance(ticker, str) for ticker in watchlist
    ):
        return DEFAULT_USER_DATA.copy(), "Local watchlist data has an invalid format."
    if not isinstance(portfolio, list) or not all(
        isinstance(position, dict) for position in portfolio
    ):
        return DEFAULT_USER_DATA.copy(), "Local portfolio data has an invalid format."
    normalized_portfolio = []
    for position in portfolio:
        ticker = position.get("ticker")
        quantity = position.get("quantity")
        average_cost = position.get("average_cost")
        if (
            not isinstance(ticker, str)
            or isinstance(quantity, bool)
            or not isinstance(quantity, (int, float))
            or isinstance(average_cost, bool)
            or not isinstance(average_cost, (int, float))
            or not math.isfinite(quantity)
            or not math.isfinite(average_cost)
            or quantity <= 0
            or average_cost < 0
        ):
            return DEFAULT_USER_DATA.copy(), "Local portfolio data has an invalid position."
        normalized_portfolio.append({
            "ticker": ticker.upper(),
            "quantity": float(quantity),
            "average_cost": float(average_cost),
        })
    if theme not in {"Dark", "Light"}:
        theme = "Dark"

    return {
        "watchlist": list(dict.fromkeys(ticker.upper() for ticker in watchlist)),
        "portfolio": normalized_portfolio,
        "theme": theme,
    }, None


def save_user_data(data: dict[str, Any], path: Path | None = None) -> None:
    data_path = path or DEFAULT_USER_DATA_PATH
    data_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=data_path.parent,
            prefix=f".{data_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            json.dump(data, file, indent=2, ensure_ascii=True)
            file.write("\n")
            temporary_path = Path(file.name)
        os.replace(temporary_path, data_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
