# IBKR Strangle Bot

This is an automated strangle trading bot for Interactive Brokers using `ib_insync`.

To run:

1. Start IBKR TWS or Gateway with API enabled (port 7497).
2. Install requirements:
   ```bash
   pip install ib_insync numpy
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
- Places limit orders to sell put and call options as a strangle.
- Tracks current positions with timestamps and credit information.

## Requirements

- Python 3.x
- `ib_insync`
- `numpy`

## Installation

Install the required Python packages directly:

```bash
pip install ib_insync numpy
```

## Configuration

The script does not rely on external environment variables; all parameters are defined within `bot.py`.

## Usage

Run the bot after starting IBKR TWS or Gateway:

```bash
python3 bot.py
```

## Project Structure

- `bot.py` – Main trading script implementing the strangle strategy.
- `README.md` – Documentation.
- `LICENSE` – MIT license file.

## License

This project is licensed under the MIT License (see `LICENSE`).
