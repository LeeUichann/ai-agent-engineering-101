"""Offline regressions for provenance, persistent observations and price targets."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from collect_evidence import excerpt, scan
from market_buyer import selection_state
from prepare_history import HISTORY, ROOT, verified_observations
from pricing import load_policy, target_asks
from trade_memory import TradeMemory


class HistoricalEvidence(unittest.TestCase):
    def test_excerpts_never_overwrite_a_different_log(self):
        with tempfile.TemporaryDirectory() as temp:
            source, target = Path(temp)/'source.log', Path(temp)/'target.log'
            source.write_bytes(b'original\n')
            target.write_bytes(b'live new log\n')
            with self.assertRaises(FileExistsError):
                excerpt(source, target, 0, 9)
            self.assertEqual(target.read_bytes(), b'live new log\n')

    def test_actual_incidents_match_unmodified_excerpts(self):
        observations = verified_observations()
        self.assertEqual([r['shop_name'] for r in observations], ['elm-street', 'maple-home'])
        self.assertEqual([(r['evidence']['agreed_offer'], r['evidence']['receipt_price'])
                          for r in observations], [(300, 345.0), (270, 310.0)])

    def copy_evidence(self, directory):
        root = Path(directory)
        history = root / 'logs' / HISTORY.name
        history.mkdir(parents=True)
        for name in ('analysis.json', 'provenance.json'):
            shutil.copy2(HISTORY / name, history / name)
        destination = root / 'logs/challenge-2'
        destination.mkdir()
        for file in (ROOT / 'logs/challenge-2').glob('historical-verified-incident-*.log'):
            shutil.copy2(file, destination / file.name)
        return root, history

    def test_changed_excerpt_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root, history = self.copy_evidence(temp)
            file = root / 'logs/challenge-2/historical-verified-incident-01.log'
            file.write_bytes(file.read_bytes() + b'changed')
            with self.assertRaisesRegex(ValueError, 'Changed source excerpt'):
                verified_observations(history, root)

    def test_false_claim_with_intact_excerpt_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root, history = self.copy_evidence(temp)
            file = history / 'analysis.json'
            data = json.loads(file.read_text())
            data['incidents'][0]['offered'] = 301
            file.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'does not match'):
                verified_observations(history, root)

    def test_interleaved_other_item_is_not_an_incident(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'fixture.log'
            receipt = dict(item='lamp', price=105, shop='Fixture', task='t1')
            task = dict(id='t1', status=dict(state='TASK_STATE_COMPLETED'),
                        artifacts=[dict(parts=[dict(data=receipt)])])
            events = [dict(event='buyer_action', item='lamp', task_id='t1', action=dict(action='offer',price=105)),
                      dict(event='http_response', item='lamp', raw=json.dumps(dict(result=dict(task=task))))]
            source.write_text('00:00:00 [order fixture] bookshelf, budget 230, round 2\n' +
                              '\n'.join('00:00:00 [buyer] ' + json.dumps(e) for e in events) + '\n')
            result = scan(source)
            self.assertEqual(result['incidents'], [])
            self.assertEqual(len(result['uncorrelated_events']), 2)


class MemoryAndPricing(unittest.TestCase):
    def test_import_is_idempotent_and_not_a_fresh_trade(self):
        row = verified_observations()[0]
        with tempfile.TemporaryDirectory() as temp, TradeMemory(Path(temp) / 'memory.sqlite3') as memory:
            for unused in range(2):
                memory.record_observation(row['id'], row['time'], row['shop_name'], row['evidence'])
            self.assertEqual(memory.db.execute('SELECT COUNT(*) FROM observations').fetchone()[0], 1)
            self.assertEqual(memory.db.execute('SELECT COUNT(*) FROM trades').fetchone()[0], 0)
            observed = memory.view(row['shop_name'], 'bookshelf')['verified_historical_observations']
            self.assertEqual(observed[0]['time'], row['time'])
            self.assertEqual(observed[0]['receipt_price'], 345)
            with self.assertRaises(ValueError):
                memory.record_observation(row['id'], row['time'], row['shop_name'], dict(row['evidence'], receipt_price=1))

    def test_model_receives_named_observation_not_url_memory(self):
        row = verified_observations()[0]
        with tempfile.TemporaryDirectory() as temp, TradeMemory(Path(temp) / 'memory.sqlite3') as memory:
            memory.record_observation(row['id'], row['time'], row['shop_name'], row['evidence'])
            for url in ('https://example.test/old', 'https://example.test/new'):
                state = selection_state([dict(name=row['shop_name'],url=url,reviews=[])], 'bookshelf', 325, memory)
                self.assertEqual(state['shops'][0]['personal_memory']['verified_historical_observations'][0]['agreed_offer'],300)

    def test_history_is_bounded_but_not_deleted(self):
        with tempfile.TemporaryDirectory() as temp, TradeMemory(Path(temp) / 'memory.sqlite3') as memory:
            for n in range(5):
                memory.record_observation(str(n), '2026-10-20T11:00:0%d+00:00' % n, 'fixture', dict(kind='fixture', sample=n))
            self.assertEqual(len(memory.view('fixture','lamp')['verified_historical_observations']),3)
            self.assertEqual(memory.db.execute('SELECT COUNT(*) FROM observations').fetchone()[0],5)

    def test_policy_matches_observed_mean_without_lowering_reserves(self):
        policy = load_policy(ROOT / 'pricing_policy.json')
        products = [dict(id='lamp', reserve=100),dict(id='chair',reserve=180),dict(id='bookshelf',reserve=260)]
        self.assertEqual(target_asks(products, policy), dict(lamp=103,chair=184,bookshelf=269))
        self.assertEqual([p['reserve'] for p in products],[100,180,260])

    def test_bad_targets_rejected(self):
        for price in (True,99,111,100.5):
            with self.subTest(price=price), self.assertRaises(ValueError):
                target_asks([dict(id='lamp',reserve=100)], dict(targets=dict(lamp=price)))

    def test_unknown_item_keeps_existing_cap(self):
        self.assertEqual(target_asks([dict(id='other',reserve=101)],dict(targets={})),dict(other=111))


if __name__ == '__main__':
    unittest.main(verbosity=2)
