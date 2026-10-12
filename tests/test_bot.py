import math
import unittest
from datetime import datetime
from unittest import mock

import bot
from bot import HybridStrangleTrader, mid_price, nearest_strike, round_to_tick


def make_trader(earnings=None):
    with mock.patch.object(HybridStrangleTrader, 'load_earnings_dates', return_value=earnings or {}):
        return HybridStrangleTrader()


class HelperTests(unittest.TestCase):
    def test_nearest_strike_put_rounds_down(self):
        self.assertEqual(nearest_strike([15, 16, 17, 18], 17.3, 'P'), 17)

    def test_nearest_strike_call_rounds_up(self):
        self.assertEqual(nearest_strike([15, 16, 17, 18], 17.3, 'C'), 18)

    def test_nearest_strike_out_of_range(self):
        self.assertIsNone(nearest_strike([15, 16], 14, 'P'))
        self.assertIsNone(nearest_strike([15, 16], 17, 'C'))

    def test_mid_price(self):
        self.assertAlmostEqual(mid_price(0.40, 0.50), 0.45)

    def test_mid_price_rejects_missing_quotes(self):
        self.assertIsNone(mid_price(math.nan, 0.50))
        self.assertIsNone(mid_price(None, 0.50))
        self.assertIsNone(mid_price(0.0, 0.50))

    def test_round_to_tick(self):
        self.assertEqual(round_to_tick(0.456), 0.46)
        self.assertEqual(round_to_tick(3.12), 3.10)


class TraderTests(unittest.TestCase):
    def test_init_does_not_crash_or_connect(self):
        with mock.patch.object(bot.IB, 'connect') as connect:
            trader = make_trader()
        connect.assert_not_called()
        self.assertEqual(trader.sell_time.hour, 15)

    def test_next_expiry_midweek(self):
        self.assertEqual(make_trader().next_expiry(datetime(2026, 10, 12)), '20261016')

    def test_next_expiry_on_friday_rolls_a_week(self):
        self.assertEqual(make_trader().next_expiry(datetime(2026, 10, 16)), '20261023')

    def test_is_earnings_soon(self):
        trader = make_trader({'AMC': ['2026-10-15']})
        self.assertTrue(trader.is_earnings_soon('AMC', today=datetime(2026, 10, 12)))
        self.assertFalse(trader.is_earnings_soon('AMC', today=datetime(2026, 10, 1)))
        self.assertFalse(trader.is_earnings_soon('PLTR', today=datetime(2026, 10, 12)))

    def test_open_new_strangles_respects_max(self):
        trader = make_trader()
        sold = []

        def fake_sell(ticker):
            trader.positions[ticker] = {}
            sold.append(ticker)
            return True

        with mock.patch.object(trader, 'sell_strangle', side_effect=fake_sell), mock.patch('bot.time.sleep'):
            trader.open_new_strangles()
        self.assertEqual(sold, ['AMC', 'PLTR'])

    def test_sell_strangle_skips_ticker_with_open_position(self):
        trader = make_trader()
        trader.positions['AMC'] = {}
        with mock.patch.object(trader.ib, 'qualifyContracts') as qualify:
            self.assertFalse(trader.sell_strangle('AMC'))
        qualify.assert_not_called()


if __name__ == '__main__':
    unittest.main()
