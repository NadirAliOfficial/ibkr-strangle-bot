from ib_insync import *
import numpy as np
import json
import math
import os
import time
from datetime import datetime, timedelta, time as dtime

EARNINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'earnings.json')


def valid_price(x):
    return x is not None and not math.isnan(x) and x > 0


def mid_price(bid, ask):
    if not (valid_price(bid) and valid_price(ask)):
        return None
    return (bid + ask) / 2


def round_to_tick(price):
    tick = 0.05 if price >= 3 else 0.01
    return round(round(price / tick) * tick, 2)


def nearest_strike(strikes, target, right):
    """Closest listed strike at or below target for puts, at or above for calls."""
    if right == 'P':
        candidates = [s for s in strikes if s <= target]
        return max(candidates) if candidates else None
    candidates = [s for s in strikes if s >= target]
    return min(candidates) if candidates else None


class HybridStrangleTrader:
    def __init__(self):
        self.ib = IB()

        # Parameters
        self.account_value = 4900
        self.max_strangles = 2
        self.min_premium = 0.30
        self.profit_target_high_iv = 0.50
        self.profit_target_low_iv = 0.25
        self.stop_loss = 2.0
        self.sell_time = dtime(15, 45)
        self.fill_timeout = 30
        self.blacklist = set()
        self.positions = {}  # ticker -> open strangle
        self.earnings_dates = self.load_earnings_dates()
        self.stocks = ['AMC', 'PLTR', 'F', 'SNAP']

    def connect(self):
        try:
            self.ib.connect('127.0.0.1', 7497, clientId=1)
            print("✅ Connected to IBKR")
            return True
        except Exception as e:
            print(f"❌ Error connecting to IBKR: {e}")
            return False

    def load_earnings_dates(self, path=EARNINGS_FILE):
        if not os.path.exists(path):
            print(f"⚠️ {os.path.basename(path)} not found, earnings filter is off (see earnings.example.json)")
            return {}
        with open(path) as f:
            return json.load(f)

    def get_iv_rank(self, ticker):
        try:
            stock = Stock(ticker, 'SMART', 'USD')
            self.ib.qualifyContracts(stock)
            hv = self.ib.reqHistoricalData(
                stock, endDateTime='', durationStr='1 Y',
                barSizeSetting='1 day', whatToShow='HISTORICAL_VOLATILITY', useRTH=True
            )
            ticker_data = self.ib.reqMktData(stock, '', False, False)
            self.ib.sleep(1)
            iv = ticker_data.impliedVolatility
            self.ib.cancelMktData(stock)
            if not hv or not valid_price(iv):
                return 50
            hv_20 = np.mean([h.close for h in hv[-20:]])
            iv_rank = min(100, max(0, (iv / hv_20 - 0.8) * 100))
            return iv_rank
        except Exception as e:
            print(f"⚠️ Error calculating IV rank for {ticker}: {e}")
            return 50

    def is_earnings_soon(self, ticker, days=5, today=None):
        today = today or datetime.now()
        start = today.strftime('%Y-%m-%d')
        end = (today + timedelta(days=days)).strftime('%Y-%m-%d')
        return any(start <= d <= end for d in self.earnings_dates.get(ticker, []))

    def option_chain(self, stock):
        """Listed expiry (first on/after next_expiry) and strikes for the stock."""
        chains = self.ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
        chain = next((c for c in chains if c.exchange == 'SMART'), None)
        if not chain:
            return None, []
        target = self.next_expiry()
        expiries = sorted(e for e in chain.expirations if e >= target)
        if not expiries:
            return None, []
        return expiries[0], sorted(chain.strikes)

    def sell_strangle(self, ticker):
        if ticker in self.positions:
            return False
        if ticker in self.blacklist or self.is_earnings_soon(ticker):
            print(f"⚠️ Skipping {ticker} (blacklist/earnings soon)")
            return False

        stock = Stock(ticker, 'SMART', 'USD')
        try:
            self.ib.qualifyContracts(stock)
            ticker_data = self.ib.reqMktData(stock, '', False, False)
            self.ib.sleep(1)
            price = ticker_data.marketPrice()
            self.ib.cancelMktData(stock)
            if not valid_price(price):
                print(f"❌ No valid market price for {ticker}")
                return False
            print(f"📈 {ticker} market price: {price:.2f}")
        except Exception as e:
            print(f"❌ Error getting {ticker} market price: {e}")
            return False

        iv_rank = self.get_iv_rank(ticker)
        expiry, strikes = self.option_chain(stock)
        if not expiry:
            print(f"❌ No option chain for {ticker}")
            return False

        width = 0.10 if iv_rank > 70 else 0.06
        put_strike = nearest_strike(strikes, price * (1 - width), 'P')
        call_strike = nearest_strike(strikes, price * (1 + width), 'C')
        if put_strike is None or call_strike is None:
            print(f"❌ No listed strikes near target for {ticker}")
            return False

        put = Option(ticker, expiry, put_strike, 'P', 'SMART')
        call = Option(ticker, expiry, call_strike, 'C', 'SMART')

        try:
            self.ib.qualifyContracts(put, call)
            put_data = self.ib.reqMktData(put, '', False, False)
            call_data = self.ib.reqMktData(call, '', False, False)
            self.ib.sleep(1)
            put_mid = mid_price(put_data.bid, put_data.ask)
            call_mid = mid_price(call_data.bid, call_data.ask)
            self.ib.cancelMktData(put)
            self.ib.cancelMktData(call)

            if put_mid is None or call_mid is None:
                print(f"❌ Missing option prices for {ticker}")
                return False
            if put_mid < self.min_premium or call_mid < self.min_premium:
                print(f"⚠️ Premium too low for {ticker}: P={put_mid:.2f}, C={call_mid:.2f}")
                return False

            put_trade = self.ib.placeOrder(put, LimitOrder('SELL', 1, round_to_tick(put_mid)))
            call_trade = self.ib.placeOrder(call, LimitOrder('SELL', 1, round_to_tick(call_mid)))
            if not self.wait_for_fills([put_trade, call_trade]):
                self.unwind(ticker, [(put, put_trade), (call, call_trade)])
                return False

            credit = put_trade.orderStatus.avgFillPrice + call_trade.orderStatus.avgFillPrice
            self.positions[ticker] = {
                'put': put, 'call': call, 'open_time': datetime.now(),
                'credit': credit, 'iv_rank': iv_rank,
            }
            print(f"✅ Sold {ticker} {put_strike}P/{call_strike}C @ ${credit:.2f} (IV Rank: {iv_rank:.0f})")
            return True
        except Exception as e:
            print(f"❌ Error placing order for {ticker}: {e}")
            return False

    def wait_for_fills(self, trades):
        deadline = time.time() + self.fill_timeout
        while time.time() < deadline:
            if all(t.orderStatus.status == 'Filled' for t in trades):
                return True
            self.ib.sleep(1)
        return all(t.orderStatus.status == 'Filled' for t in trades)

    def unwind(self, ticker, legs):
        """Cancel unfilled legs and buy back any leg that filled, so no naked option is left."""
        for contract, trade in legs:
            if trade.orderStatus.status == 'Filled':
                self.ib.placeOrder(contract, MarketOrder('BUY', 1))
                print(f"↩️ Bought back filled {contract.right} leg for {ticker}")
            else:
                self.ib.cancelOrder(trade.order)
        print(f"⚠️ {ticker} strangle not filled within {self.fill_timeout}s, cancelled")

    def manage_positions(self):
        for ticker, pos in list(self.positions.items()):
            try:
                put, call, credit, iv_rank = pos['put'], pos['call'], pos['credit'], pos['iv_rank']
                put_data = self.ib.reqMktData(put, '', False, False)
                call_data = self.ib.reqMktData(call, '', False, False)
                self.ib.sleep(1)

                put_price = put_data.midpoint() if valid_price(put_data.midpoint()) else put_data.last
                call_price = call_data.midpoint() if valid_price(call_data.midpoint()) else call_data.last
                self.ib.cancelMktData(put)
                self.ib.cancelMktData(call)
                if not (valid_price(put_price) and valid_price(call_price)):
                    continue

                value = put_price + call_price
                profit_pct = (credit - value) / credit
                reason = None
                if iv_rank > 50 and profit_pct >= self.profit_target_high_iv:
                    reason = "🔓 Hit 50% target"
                elif iv_rank < 30 and profit_pct >= self.profit_target_low_iv:
                    reason = "🔓 Hit 25% target (low IV)"
                elif value >= credit * self.stop_loss:
                    reason = "🛑 Stop loss hit"
                    self.blacklist.add(ticker)

                if reason:
                    self.ib.placeOrder(put, MarketOrder('BUY', 1))
                    self.ib.placeOrder(call, MarketOrder('BUY', 1))
                    del self.positions[ticker]
                    print(f"🔁 Closing {ticker} strangle: {reason}")
            except Exception as e:
                print(f"❌ Error managing {ticker} position: {e}")

    def next_expiry(self, today=None):
        today = today or datetime.now()
        days_until_friday = (4 - today.weekday()) % 7
        friday = today + timedelta(days=days_until_friday or 7)
        return friday.strftime('%Y%m%d')

    def open_new_strangles(self):
        for ticker in self.stocks:
            if len(self.positions) >= self.max_strangles:
                break
            self.sell_strangle(ticker)
            time.sleep(1)

    def run(self):
        if not self.connect():
            return
        print(f"🚀 Hybrid Strangle Trader Running | Account: ${self.account_value}")
        try:
            while True:
                now = datetime.now()
                if now.weekday() >= 5:
                    time.sleep(600)
                    continue

                if not dtime(9, 30) <= now.time() <= dtime(16, 0):
                    time.sleep(60)
                    continue

                if now.time() >= self.sell_time:
                    self.open_new_strangles()

                self.manage_positions()
                time.sleep(60)
        except KeyboardInterrupt:
            print("🛑 Trader manually stopped.")
        finally:
            self.ib.disconnect()
            print("🔌 Disconnected from IBKR")


if __name__ == '__main__':
    trader = HybridStrangleTrader()
    trader.run()
