"""Verify genuine log excerpts before importing old observations into new memory."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from collect_evidence import ORDER, SHOP, completed_receipts, parse_event, write_json
from trade_memory import TradeMemory

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / 'logs/historical-verified'


def verified_observations(history=HISTORY, root=ROOT):
    analysis = json.loads((history / 'analysis.json').read_text())
    provenance = json.loads((history / 'provenance.json').read_text())
    if analysis['source_sha256'] != provenance['source_sha256']:
        raise ValueError('Source hash disagreement')
    observations = []
    for index, expected in enumerate(analysis['incidents'], 1):
        relative = 'logs/challenge-2/%s-incident-%02d.log' % (history.name, index)
        export = next(row for row in provenance['exports'] if row['path'] == relative)
        raw = (root / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != export['sha256']:
            raise ValueError('Changed source excerpt: ' + relative)
        order, shop, offer, offer_task, found = None, None, None, None, False
        for text in raw.decode('utf-8').splitlines():
            match = ORDER.search(text)
            if match:
                order = dict(id=match[1], item=match[2], budget=int(match[3]))
            match = SHOP.search(text)
            if match:
                shop = match[1]
            role, event = parse_event(text)
            if role != 'buyer' or not isinstance(event, dict):
                continue
            if event.get('event') == 'market_choice':
                shop = event['shop_name']
            if event.get('event') == 'buyer_action' and event['action']['action'] == 'offer':
                offer, offer_task = event['action']['price'], event.get('task_id')
            for task, receipt in completed_receipts(event):
                if task.get('id') != expected['task']:
                    continue
                if (not order or order['id'] != expected['order'] or shop != expected['shop_name'] or
                        offer_task != task['id'] or offer != expected['offered'] or
                        receipt != expected['receipt'] or order['item'] != expected['item'] or
                        order['budget'] != expected['budget'] or event.get('time') != expected['time']):
                    raise ValueError('Incident does not match its raw evidence')
                if receipt['price'] == offer and receipt['price'] <= order['budget'] and receipt['item'] == order['item']:
                    raise ValueError('Cannot import a normal receipt as a mismatch')
                found = True
        if not found:
            raise ValueError('Incident task absent from evidence')
        observations.append(dict(id=hashlib.sha256((analysis['source_sha256'] + expected['task']).encode()).hexdigest(),
            time=expected['time'], shop_name=expected['shop_name'], evidence=dict(
                kind='receipt_mismatch', item=expected['item'], budget=expected['budget'],
                agreed_offer=expected['offered'], receipt_price=expected['receipt']['price'],
                task=expected['task'], source=relative, source_line=expected['response_line'],
                excerpt_sha256=export['sha256'], original_log_sha256=analysis['source_sha256'])))
    return observations


def prepare():
    analysis = json.loads((HISTORY / 'analysis.json').read_text())
    catalog = {row['id']: row for row in json.loads((ROOT / 'catalog.json').read_text())}
    targets = {}
    for item, summary in analysis['seller_stats']['after']['by_item'].items():
        if summary['accepts']:
            reserve = catalog[item]['reserve']
            targets[item] = min(reserve * 110 // 100, max(reserve, math.ceil(summary['mean_accepted'])))
    policy = dict(version=1, targets=targets, basis='ceil of own historical mean accepted price, clamped to reserve..110%',
                  source='logs/historical-verified/analysis.json', source_sha256=analysis['source_sha256'],
                  note='Targets for the new version, not proof of a new public deployment')
    if (ROOT / 'pricing_policy.json').exists():
        if json.loads((ROOT / 'pricing_policy.json').read_text()) != policy:
            raise ValueError('Do not overwrite a different pricing experiment')
    else:
        write_json(ROOT / 'pricing_policy.json', policy)
    write_json(ROOT / 'logs/challenge-1/pricing-policy.json', policy)
    database = ROOT / '.market/buyer-memory.sqlite3'
    database.parent.mkdir(exist_ok=True)
    if not database.exists():
        old = (ROOT.parent / 'week-07/.market/buyer-memory.sqlite3').resolve()
        with sqlite3.connect(old.as_uri() + '?mode=ro', uri=True) as source, sqlite3.connect(database) as target:
            source.backup(target)
    observations = verified_observations()
    with TradeMemory(database) as memory:
        for row in observations:
            memory.record_observation(row['id'], row['time'], row['shop_name'], row['evidence'])
        result = dict(prepared_at=datetime.now(timezone.utc).isoformat(), observations=observations,
                      existing_trade_rows=memory.db.execute('SELECT COUNT(*) FROM trades').fetchone()[0],
                      targets=targets, original_memory_modified=False)
    write_json(ROOT / 'logs/challenge-2/imported-observations.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    prepare()
