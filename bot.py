from __future__ import annotations

"""
Telegram Crypto Futures Signal Bot
===================================
Quét toàn bộ USDT-M Futures trên Binance.
Timeframe chính: 4H | Timeframe xác nhận: M30
Gửi tín hiệu LONG / SHORT tự động qua Telegram.

Author: Triệu Tử Long
"""

import asyncio
import argparse
import logging
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import ccxt.async_support as ccxt
import numpy as np
import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot

from env_loader import load_env_file

# ──────────────────────────────────────────────
# CẤU HÌNH
# ──────────────────────────────────────────────
load_env_file(Path(__file__).resolve().parent / ".env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Tham số kỹ thuật
EMA_4H_PERIOD = 34
EMA_M30_PERIODS = (89, 144, 257)
# Điều kiện nến
BODY_RATIO_MIN = 0.60          # Body > 60% tổng chiều dài nến
WICK_RATIO_MAX = 0.25          # Râu theo hướng không vượt quá 25% tổng chiều dài nến
RANGE_PERCENT_MIN = 0.10       # Range = (High-Low)/Open > 10%
RANGE_PERCENT_MAX = 0.30       # Range = (High-Low)/Open < 30%
VOLUME_SPIKE_MULTIPLIER = 2.0  # Volume >= 2x nến trước
ALT_RANGE_PERCENT_MIN = 0.05   # Nhánh bổ sung: Range từ 5% đến 10%
ALT_VOLUME_SPIKE_MULTIPLIER = 3.0  # Nhánh bổ sung: Volume >= 3x nến trước
ALT_BODY_RATIO_MIN = 0.80      # Nhánh 5-10%: Body >= 80% tổng chiều dài nến
MIN_FUTURES_QUOTE_VOLUME_24H = 5_000_000   # 24h quote volume tối thiểu (USDT)

# Điều kiện tổng hợp D1 lúc 07:00 UTC+7 (tức 00:00 UTC)
D1_BODY_RATIO_MIN = 0.60       # Body > 60% tổng chiều dài nến D1
D1_RANGE_PERCENT_MIN = 0.25    # Range >= 25% giá Open nến D1
D1_VOLUME_SPIKE_MULTIPLIER = 3.0  # Volume D1 >= 3x nến D1 liền trước

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# EXCHANGE & TELEGRAM INIT
# ──────────────────────────────────────────────
exchange: ccxt.binance | None = None
bot: Bot | None = None


def create_exchange() -> ccxt.binance:
    """Khởi tạo Binance Futures (public – không cần API key)."""
    return ccxt.binance({
        "enableRateLimit": True,
        "options": {
            "defaultType": "future",         # USDT-M Futures
            "adjustForTimeDifference": True,
        },
    })


async def init():
    """Khởi tạo exchange và Telegram bot."""
    global exchange, bot
    if not TELEGRAM_TOKEN or not CHAT_ID:
        raise RuntimeError(
            "Thiếu TELEGRAM_TOKEN hoặc TELEGRAM_CHAT_ID trong biến môi trường."
        )
    exchange = create_exchange()
    bot = Bot(token=TELEGRAM_TOKEN)
    log.info("Exchange và Telegram Bot đã khởi tạo.")


async def shutdown():
    """Đóng kết nối exchange."""
    global exchange
    if exchange:
        await exchange.close()
        log.info("Exchange closed.")


# ──────────────────────────────────────────────
# FETCH MARKET DATA
# ──────────────────────────────────────────────
async def fetch_usdt_futures_symbols() -> list[str]:
    """
    Lấy danh sách symbols USDT-M Futures đang active.
    Gọi API động — tự động nhận coin mới.
    """
    ex = exchange
    assert ex is not None
    await ex.load_markets(reload=True)
    markets = ex.markets or {}
    symbols = [
        s for s, m in markets.items()
        if m.get("swap")
        and m.get("linear")                 # USDT-margined
        and m.get("active")
        and m.get("quote") == "USDT"
        and ":USDT" in s
    ]
    log.info(f"Tìm thấy {len(symbols)} cặp USDT-M Futures.")
    return sorted(symbols)


async def filter_symbols_by_24h_volume(symbols: list[str]) -> list[str]:
    """
    Lọc symbol theo 24h futures quote volume (USDT).
    Chỉ giữ các cặp có volume >= MIN_FUTURES_QUOTE_VOLUME_24H.
    """
    if not symbols:
        return []

    ex = exchange
    assert ex is not None

    try:
        tickers = await ex.fetch_tickers(symbols)
    except Exception as e:
        log.warning(f"Không thể fetch ticker 24h volume: {e}")
        return []

    filtered_symbols: list[str] = []
    for symbol in symbols:
        ticker = tickers.get(symbol) or {}

        # quoteVolume từ ccxt hoặc fallback từ raw info của Binance
        raw_quote_volume = ticker.get("quoteVolume")
        if raw_quote_volume is None:
            raw_quote_volume = (ticker.get("info") or {}).get("quoteVolume")

        quote_volume = 0.0
        if raw_quote_volume is not None:
            try:
                quote_volume = float(str(raw_quote_volume))
            except (TypeError, ValueError):
                quote_volume = 0.0

        if quote_volume >= MIN_FUTURES_QUOTE_VOLUME_24H:
            filtered_symbols.append(symbol)

    log.info(
        f"Lọc volume 24h >= ${MIN_FUTURES_QUOTE_VOLUME_24H:,.0f}: "
        f"{len(filtered_symbols)}/{len(symbols)} cặp"
    )
    return filtered_symbols


async def fetch_ohlcv(symbol: str, timeframe: str, limit: int) -> pd.DataFrame | None:
    """Fetch OHLCV từ Binance, trả về DataFrame hoặc None nếu lỗi."""
    try:
        ex = exchange
        assert ex is not None
        data = await ex.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not data or len(data) < 2:
            return None
        df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df
    except Exception as e:
        log.warning(f"Lỗi fetch {symbol} {timeframe}: {e}")
        return None


# ──────────────────────────────────────────────
# TÍNH EMA
# ──────────────────────────────────────────────
def calc_ema(series: pd.Series, period: int) -> pd.Series:
    """Tính EMA chuẩn (giống Binance / TradingView)."""
    return series.ewm(span=period, adjust=False).mean()


def passes_directional_wick_rule(o: float, h: float, l: float, c: float) -> bool:
    """Kiểm tra râu nến theo màu: nến xanh xét râu trên, nến đỏ xét râu dưới."""
    total_range = h - l
    if total_range <= 0 or c == o:
        return False

    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l

    if c > o:
        return (upper_wick / total_range) <= WICK_RATIO_MAX
    return (lower_wick / total_range) <= WICK_RATIO_MAX


# ──────────────────────────────────────────────
# KIỂM TRA ĐIỀU KIỆN NẾN 4H
# ──────────────────────────────────────────────
def check_candle_conditions(df_4h: pd.DataFrame) -> dict | None:
    """
    Kiểm tra điều kiện trên nến 4H vừa đóng (iloc[-2]).
    Range được tính theo chiều dài nến từ thấp nhất đến cao nhất: (High - Low) / Open.
    Trả về dict thông tin nếu hợp lệ, None nếu không.
    """
    if len(df_4h) < 3:
        return None

    # Nến vừa đóng = iloc[-2] (iloc[-1] là nến đang chạy)
    candle = df_4h.iloc[-2]
    prev_candle = df_4h.iloc[-3]

    o, h, l, c, vol = candle["open"], candle["high"], candle["low"], candle["close"], candle["volume"]
    prev_vol = prev_candle["volume"]

    total_range = h - l
    if total_range <= 0:
        return None

    body = abs(c - o)

    body_ratio = body / total_range

    # Condition 2: Range theo 2 nhánh với range_pct = (High-Low)/Open
    # - Nhánh gốc: 10% < range < 30%  và volume >= 2x nến trước
    # - Nhánh bổ sung: 5% <= range <= 10% và volume >= 3x nến trước
    # YÊU CẦU GỐC: (H-L) > 10% Open  VÀ  (H-L) < 30% Open
    # ⚠ Giá trị 10% và 30% là rất lớn cho crypto (e.g. BTC 70000 → range > 7000).
    # Đây rất có thể là ý muốn 1% và 3% (hoặc 0.1% và 0.3%).
    # Tuy nhiên, tôi sẽ TUÂN THỦ ĐÚNG yêu cầu: 10% → 0.10, 30% → 0.30.
    range_pct = total_range / o
    if prev_vol <= 0:
        return None

    if RANGE_PERCENT_MIN < range_pct < RANGE_PERCENT_MAX:
        required_vol_spike = VOLUME_SPIKE_MULTIPLIER
        required_body_ratio = BODY_RATIO_MIN
    elif ALT_RANGE_PERCENT_MIN <= range_pct <= RANGE_PERCENT_MIN:
        required_vol_spike = ALT_VOLUME_SPIKE_MULTIPLIER
        required_body_ratio = ALT_BODY_RATIO_MIN
    else:
        return None

    # Condition 1 theo từng nhánh range
    if body_ratio <= required_body_ratio:
        return None

    if not passes_directional_wick_rule(o, h, l, c):
        return None

    # Condition 3: Volume theo từng nhánh range
    vol_spike = vol / prev_vol
    if vol_spike < required_vol_spike:
        return None

    # Xác định bullish / bearish
    is_bullish = c > o

    return {
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": vol,
        "prev_volume": prev_vol,
        "body_ratio": body_ratio,
        "range_pct": range_pct,
        "vol_spike": vol_spike,
        "is_bullish": is_bullish,
    }


# ──────────────────────────────────────────────
# KIỂM TRA EMA 4H
# ──────────────────────────────────────────────
def check_ema_4h(df_4h: pd.DataFrame, is_bullish: bool, close: float) -> bool:
    """
    LONG : Close > EMA34 (4H)
    SHORT: Close < EMA34 (4H)
    """
    ema34 = calc_ema(df_4h["close"], EMA_4H_PERIOD)
    ema34_val = ema34.iloc[-2]  # ema tại nến vừa đóng

    if is_bullish:
        return close > ema34_val
    else:
        return close < ema34_val


def check_m30_price_vs_emas(
    df_30m: pd.DataFrame,
    is_bullish: bool,
) -> tuple[bool, float, dict[int, float]]:
    """
    Xác nhận đa khung thời gian trên M30.
    Dùng close của cây M30 mới nhất như current price để so với EMA 89/144/257.
    """
    required_bars = max(EMA_M30_PERIODS) + 2
    if len(df_30m) < required_bars:
        return False, float("nan"), {}

    current_price = float(df_30m.iloc[-1]["close"])
    ema_values = {
        period: float(calc_ema(df_30m["close"], period).iloc[-1])
        for period in EMA_M30_PERIODS
    }

    if is_bullish:
        passed = all(current_price > ema for ema in ema_values.values())
    else:
        passed = all(current_price < ema for ema in ema_values.values())

    return passed, current_price, ema_values


# ──────────────────────────────────────────────
# TẠO TIN NHẮN TELEGRAM
# ──────────────────────────────────────────────
def format_signal(symbol: str, candle_info: dict, timeframe_label: str = "4H") -> str:
    """
    Tạo message theo đúng format yêu cầu.
    LONG  → SL = Low  của nến 4H vừa đóng
    SHORT → SL = High của nến 4H vừa đóng
    """
    is_long = candle_info["is_bullish"]
    entry = candle_info["close"]

    # Lấy base coin (bỏ /USDT:USDT)
    base = symbol.split("/")[0]  # e.g. "BNB"

    if is_long:
        sl = candle_info["low"]
        direction = f"LONG 🟢 ({timeframe_label})"
    else:
        sl = candle_info["high"]
        direction = f"SHORT 🔴 ({timeframe_label})"

    sl_pct = abs(entry - sl) / entry * 100
    risk = abs(entry - sl)

    if is_long:
        tp1 = entry + risk        # 1R
        tp2 = entry + 2 * risk    # 2R
    else:
        tp1 = entry - risk
        tp2 = entry - 2 * risk

    tp1_pct = sl_pct              # 1R = cùng % với SL
    tp2_pct = sl_pct * 2          # 2R = 2 lần % SL

    # Format số — tự động chọn decimal phù hợp
    def fmt(price: float) -> str:
        if price >= 1000:
            return f"{price:,.2f}"
        elif price >= 1:
            return f"{price:.4f}"
        elif price >= 0.01:
            return f"{price:.6f}"
        else:
            return f"{price:.8f}"

    msg = (
        f"{direction}\n"
        f"\n"
        f"${base}\n"
        f"\n"
        f"Entry : {fmt(entry)}\n"
        f"\n"
        f"SL : {fmt(sl)} - ({sl_pct:.2f}%)\n"
        f"\n"
        f"TP1 : {fmt(tp1)} - 1R ({tp1_pct:.2f}%)\n"
        f"\n"
        f"TP2 : {fmt(tp2)} - 2R ({tp2_pct:.2f}%)\n"
        f"\n"
        f"Đơn thương độc mã duy ngã độc tôn"
    )
    return msg


def check_daily_candle_conditions(df_1d: pd.DataFrame) -> dict | None:
    """
    Kiểm tra nến D1 vừa đóng (iloc[-2]) với điều kiện:
    - Body > 60% tổng chiều dài nến
    - Nến xanh: râu trên <= 25% tổng chiều dài nến
    - Nến đỏ: râu dưới <= 25% tổng chiều dài nến
    - Range >= 25% giá Open
    - Volume >= 3x nến D1 liền trước
    """
    if df_1d is None or len(df_1d) < 3:
        return None

    candle = df_1d.iloc[-2]
    prev_candle = df_1d.iloc[-3]
    o, h, l, c, vol = candle["open"], candle["high"], candle["low"], candle["close"], candle["volume"]
    prev_vol = prev_candle["volume"]

    total_range = h - l
    if total_range <= 0 or o <= 0:
        return None

    body_ratio = abs(c - o) / total_range
    range_pct = total_range / o

    if body_ratio <= D1_BODY_RATIO_MIN:
        return None
    if not passes_directional_wick_rule(o, h, l, c):
        return None
    if range_pct < D1_RANGE_PERCENT_MIN:
        return None
    if prev_vol <= 0:
        return None
    vol_spike = vol / prev_vol
    if vol_spike < D1_VOLUME_SPIKE_MULTIPLIER:
        return None
    if c == o:
        return None

    return {
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": vol,
        "prev_volume": prev_vol,
        "vol_spike": vol_spike,
        "body_ratio": body_ratio,
        "range_pct": range_pct,
        "is_bullish": c > o,
        "timestamp": candle["timestamp"],
    }


def format_daily_summary(long_coins: list[str], short_coins: list[str]) -> str:
    """Tạo message tổng hợp D1 Long/Short trong 1 tin nhắn."""
    long_text = ", ".join(sorted(long_coins)) if long_coins else "Không có"
    short_text = ", ".join(sorted(short_coins)) if short_coins else "Không có"

    return (
        "Tổng hợp D1 (07:00 UTC+7)\n"
        "\n"
        f"D1 Long : {long_text}\n"
        "\n"
        f"D1 Short : {short_text}"
    )


# ──────────────────────────────────────────────
# GỬI TIN NHẮN TELEGRAM
# ──────────────────────────────────────────────
async def send_telegram(message: str):
    """Gửi tin nhắn đến Telegram chat."""
    try:
        tg_bot = bot
        assert tg_bot is not None
        await tg_bot.send_message(chat_id=CHAT_ID, text=message)
        log.info("✅ Đã gửi tín hiệu Telegram.")
    except Exception as e:
        log.error(f"❌ Lỗi gửi Telegram: {e}")


# ──────────────────────────────────────────────
# QUY TRÌNH QUÉT CHÍNH
# ──────────────────────────────────────────────
async def scan_symbol(symbol: str) -> str | None:
    """
    Quét 1 symbol qua toàn bộ pipeline.
    Trả về message nếu có tín hiệu, None nếu không.
    """
    # 1) Fetch 4H data (cần đủ data cho EMA34 + 2 nến)
    df_4h = await fetch_ohlcv(symbol, "4h", limit=100)
    if df_4h is None:
        return None

    # 2) Kiểm tra điều kiện nến 4H
    candle_info = check_candle_conditions(df_4h)
    if candle_info is None:
        return None

    log.info(
        f"🔍 {symbol} — Nến hợp lệ | "
        f"body={candle_info['body_ratio']:.1%} "
        f"range={candle_info['range_pct']:.2%} "
        f"vol_spike={candle_info['vol_spike']:.1f}x"
    )

    # 3) Kiểm tra EMA 34 (4H)
    if not check_ema_4h(df_4h, candle_info["is_bullish"], candle_info["close"]):
        log.info(f"   ❌ {symbol} — Không qua EMA34 4H")
        return None

    # 4) Kiểm tra current price trên M30 so với EMA 89/144/257
    df_30m = await fetch_ohlcv(symbol, "30m", limit=max(EMA_M30_PERIODS) + 10)
    if df_30m is None:
        log.info(f"   ❌ {symbol} — Không fetch được dữ liệu M30")
        return None

    m30_confirmed, current_price, ema_values = check_m30_price_vs_emas(
        df_30m,
        candle_info["is_bullish"],
    )
    if not m30_confirmed:
        if ema_values:
            log.info(
                f"   ❌ {symbol} — Không qua M30 | "
                f"price={current_price:.6f} "
                f"ema89={ema_values[89]:.6f} "
                f"ema144={ema_values[144]:.6f} "
                f"ema257={ema_values[257]:.6f}"
            )
        else:
            log.info(f"   ❌ {symbol} — Không đủ dữ liệu M30 cho EMA 89/144/257")
        return None

    log.info(
        f"   ✅ {symbol} — Qua M30 | "
        f"price={current_price:.6f} "
        f"ema89={ema_values[89]:.6f} "
        f"ema144={ema_values[144]:.6f} "
        f"ema257={ema_values[257]:.6f}"
    )

    # 5) TÍN HIỆU HỢP LỆ — tạo message
    log.info(f"   ✅ {symbol} — TÍN HIỆU {'LONG' if candle_info['is_bullish'] else 'SHORT'}!")
    return format_signal(symbol, candle_info)


async def run_scan():
    """Quét toàn bộ universe và gửi tín hiệu."""
    log.info("=" * 60)
    log.info("🚀 BẮT ĐẦU QUÉT TÍN HIỆU...")
    log.info("=" * 60)

    start = datetime.now(timezone.utc)

    symbols = await fetch_usdt_futures_symbols()
    symbols = await filter_symbols_by_24h_volume(symbols)
    if not symbols:
        log.info("Không có cặp nào đạt điều kiện volume futures 24h tối thiểu.")
        return
    signals_found = 0

    # Quét theo batch để tránh rate limit
    batch_size = 5
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]
        tasks = [scan_symbol(sym) for sym in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for sym, result in zip(batch, results):
            if isinstance(result, BaseException):
                log.error(f"Lỗi xử lý {sym}: {result}")
            elif isinstance(result, str):
                signals_found += 1
                await send_telegram(result)

        # Pause nhẹ giữa các batch
        if i + batch_size < len(symbols):
            await asyncio.sleep(1)

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    log.info(f"✅ HOÀN TẤT — {signals_found} tín hiệu / {len(symbols)} cặp — {elapsed:.1f}s")

    if signals_found == 0:
        log.info("Không có tín hiệu nào trong phiên quét này.")


async def scan_symbol_daily_direction(symbol: str) -> str | None:
    """
    Kiểm tra hướng nến D1 vừa đóng cho 1 symbol.
    Trả về "LONG" / "SHORT" nếu hợp lệ, None nếu không đạt điều kiện.
    """
    df_1d = await fetch_ohlcv(symbol, "1d", limit=5)
    if df_1d is None:
        return None

    candle_info = check_daily_candle_conditions(df_1d)
    if candle_info is None:
        return None

    return "LONG" if candle_info["is_bullish"] else "SHORT"


async def run_daily_summary_scan():
    """Quét D1 lúc 07:00 UTC+7 và gửi 1 tin nhắn tổng hợp LONG/SHORT."""
    log.info("=" * 60)
    log.info("🗓️ BẮT ĐẦU QUÉT TỔNG HỢP D1...")
    log.info("=" * 60)

    symbols = await fetch_usdt_futures_symbols()
    symbols = await filter_symbols_by_24h_volume(symbols)
    if not symbols:
        log.info("Không có cặp nào đạt điều kiện volume futures 24h tối thiểu cho D1.")
        return

    long_coins: list[str] = []
    short_coins: list[str] = []

    batch_size = 5
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]
        tasks = [scan_symbol_daily_direction(sym) for sym in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for sym, result in zip(batch, results):
            if isinstance(result, Exception):
                log.error(f"Lỗi D1 {sym}: {result}")
                continue

            if result == "LONG":
                long_coins.append(sym.split("/")[0])
            elif result == "SHORT":
                short_coins.append(sym.split("/")[0])

        if i + batch_size < len(symbols):
            await asyncio.sleep(1)

    message = format_daily_summary(long_coins, short_coins)
    await send_telegram(message)
    log.info(
        f"✅ D1 tổng hợp hoàn tất — LONG: {len(long_coins)} | SHORT: {len(short_coins)}"
    )


# ──────────────────────────────────────────────
# SCHEDULER — Chạy đúng khi nến 4H đóng
# ──────────────────────────────────────────────
def get_4h_cron_hours() -> str:
    """
    Nến 4H Binance đóng vào: 00, 04, 08, 12, 16, 20 UTC.
    Quét ngay đầu giờ này (chờ 10s cho nến đóng hoàn toàn).
    """
    return "0,4,8,12,16,20"


async def scheduled_scan():
    """Wrapper cho scheduler — thêm delay nhỏ để nến đóng."""
    log.info("⏰ Scheduler triggered — chờ 15s cho nến 4H đóng...")
    await asyncio.sleep(15)
    await run_scan()


async def scheduled_daily_summary_scan():
    """Chạy tổng hợp D1 sau khi nến ngày vừa đóng tại 00:00 UTC (07:00 UTC+7)."""
    log.info("⏰ Daily D1 scheduler triggered — chờ 20s cho nến ngày đóng...")
    await asyncio.sleep(20)
    await run_daily_summary_scan()


def setup_scheduler() -> AsyncIOScheduler:
    """Cấu hình APScheduler chạy mỗi 4h."""
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        scheduled_scan,
        "cron",
        hour=get_4h_cron_hours(),
        minute=0,
        second=10,
        id="4h_scan",
        name="Quét tín hiệu mỗi nến 4H",
        misfire_grace_time=300,  # cho phép trễ tối đa 5 phút
    )
    scheduler.add_job(
        scheduled_daily_summary_scan,
        "cron",
        hour=0,
        minute=0,
        second=30,
        id="d1_daily_summary_scan",
        name="Tổng hợp D1 mỗi 07:00 UTC+7",
        misfire_grace_time=300,
    )
    return scheduler


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
async def run_service_mode():
    await init()

    # Chạy quét ngay lần đầu để test
    log.info("🔥 Chạy quét lần đầu (test)...")
    await run_scan()

    # Setup scheduler
    scheduler = setup_scheduler()
    scheduler.start()

    next_runs = scheduler.get_jobs()
    for job in next_runs:
        log.info(f"📅 Job: {job.name} — Next run: {job.next_run_time}")

    log.info("🤖 Bot đang chạy... Nhấn Ctrl+C để dừng.")

    # Keep alive
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        log.info("Đang tắt bot...")
    finally:
        scheduler.shutdown()
        await shutdown()


async def run_once_mode():
    """Chạy 1 vòng quét rồi thoát (phù hợp cho job theo lịch)."""
    await init()
    try:
        await run_scan()

        # Nếu job chạy vào 00:00 UTC (07:00 UTC+7), gửi thêm tổng hợp D1.
        now_utc = datetime.now(timezone.utc)
        if now_utc.hour == 0:
            log.info("🗓️ Khung giờ 07:00 UTC+7 — chạy thêm tổng hợp D1.")
            await run_daily_summary_scan()
    finally:
        await shutdown()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telegram Crypto Futures Signal Bot")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Chạy một lần rồi thoát (dùng cho scheduler/job).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.once:
        asyncio.run(run_once_mode())
    else:
        asyncio.run(run_service_mode())
