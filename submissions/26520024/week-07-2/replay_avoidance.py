"""Real model selection on historical candidates, without contacting any shop."""
import contextlib
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from collect_evidence import write_json
from core import decide
from market_buyer import SELECT_PROMPT, validate_choice
from prepare_history import HISTORY, ROOT, verified_observations
from trade_memory import TradeMemory


def main():
    out = ROOT / 'logs/challenge-2' / ('replay-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir(parents=True)
    analysis = json.loads((HISTORY / 'analysis.json').read_text())
    observations = verified_observations()
    bad_names = {r['shop_name'] for r in observations}
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
              for name in ('market_buyer.py','trade_memory.py','core.py','codex_backend.py','replay_avoidance.py')}
    write_json(out / 'source-hashes.json', hashes)
    results = []
    with TradeMemory(out / 'isolated-memory.sqlite3') as memory:
        for row in observations:
            memory.record_observation(row['id'], row['time'], row['shop_name'], row['evidence'])
        for index, historical in enumerate(analysis['avoidance'][:3], 1):
            state = copy.deepcopy(historical['state'])
            for shop in state['shops']:
                shop['personal_memory'] = memory.view(shop['name'], state['item'])
            record = dict(case=index, scope='real_model_replay_not_a_new_market_trade',
                          original_order=historical['order'], original_decision_line=historical['decision_line'],
                          known_mismatches=sorted(bad_names), state=state)
            with (out / ('model-%02d.log' % index)).open('w') as log, contextlib.redirect_stdout(log):
                try:
                    choice = decide(SELECT_PROMPT, state, lambda value: validate_choice(value,state['shops']),
                                    'buyer', time.monotonic()+90, dict(replay_case=index))
                    record.update(choice=choice, avoided=choice['shop_name'] not in bad_names)
                except Exception as exc:
                    record.update(error=type(exc).__name__ + ': ' + str(exc), avoided=False)
            results.append(record)
            write_json(out / ('case-%02d.json' % index), record)
            print(json.dumps({k:v for k,v in record.items() if k!='state'},ensure_ascii=False),flush=True)
    summary = dict(scope='Three recorded candidate sets plus verified historical observations; no network trades.',
                   cases=len(results), avoided=sum(r['avoided'] for r in results),
                   model='gpt-6-astra', reasoning='low', results=results)
    write_json(out / 'summary.json', summary)
    print('REPLAY_EVIDENCE=' + str(out))
    return 0 if len(results)==3 and all(r['avoided'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
