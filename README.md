# IBKR Strangle Bot

This is an automated strangle trading bot for Interactive Brokers using `ib_insync`.

To run:

1. Start IBKR TWS or Gateway with API enabled (port 7497).
2. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the bot:
   ```bash
   python3 bot.py
   ```

If you face any issues, message me on Telegram: [@NAKBlockDev](https://t.me/NAKBlockDev)
<!-- updated: 2026-05-30 -->

## Description

The project provides an automated trading bot that connects to Interactive Brokers, evaluates implied volatility ranks, and sells strangle option positions for a predefined list of stocks while respecting blacklist and earnings‑date constraints.

## Features

- Connects to IBKR TWS/Gateway using `ib_insync`.
- Calculates IV rank based on historical volatility.
- Skips stocks on a blacklist or with upcoming earnings.
- Determines strike prices based on IV rank and market price.
- Picks listed strikes and expiries from the option chain.
- Sells both legs at the mid price and records the actual fill credit; unfilled orders are cancelled.
- Tracks current positions with timestamps and credit information.

## Requirements

- Python 3.x
- `ib_insync`
- `numpy`

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Strategy parameters are defined in `bot.py`.

Earnings dates are read from `earnings.json` (same format as `earnings.example.json`). Without it the bot still runs but does not skip stocks ahead of earnings, and prints a warning.

## Usage

Run the bot after starting IBKR TWS or Gateway:

```bash
python3 bot.py
```

## Tests

```bash
python3 -m unittest
```

## Project Structure

- `bot.py` – Main trading script implementing the strangle strategy.
- `tests/` – Unit tests.
- `earnings.example.json` – Example earnings calendar.
- `README.md` – Documentation.
- `LICENSE` – MIT license file.

## License

This project is licensed under the MIT License (see `LICENSE`).
