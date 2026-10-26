"""Read original market evidence without changing it; export attributable excerpts."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
import urllib.request

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'week-07'
ORDER = re.compile(r'\[order ([^]]+)\] (.+), budget (\d+), round (\d+)')
SHOP = re.compile(r'\[kit\] shop for this order: (.+) (https?://\S+)')
EVENT = re.compile(r'^\d\d:\d\d:\d\d \[(buyer|seller)\] (\{.*)$')


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def parse_event(line):
    match = EVENT.match(line)
    if not match:
        return None, None
    try:
        return match[1], json.loads(match[2])
    except json.JSONDecodeError:
        return match[1], None


def completed_receipts(event):
    if event.get('event') != 'http_response':
        return []
    try:
        task = json.loads(event['raw']).get('result', {}).get('task', {})
    except (KeyError, ValueError, AttributeError):
        return []
    if task.get('status', {}).get('state') != 'TASK_STATE_COMPLETED':
        return []
    return [(task, part['data']) for artifact in task.get('artifacts', [])
            for part in artifact.get('parts', []) if isinstance(part.get('data'), dict)]


def scan(source):
    orders, incidents, avoidance, registrations, uncorrelated = [], [], [], [], []
    sellers, bad_names = {}, set()
    digest, offset, first_promotion = hashlib.sha256(), 0, None
    current, last_state = None, None
    with source.open('rb') as stream:
        for number, raw in enumerate(stream, 1):
            digest.update(raw)
            start, offset = offset, offset + len(raw)
            text = raw.decode('utf-8', errors='replace').rstrip('\n')
            order = ORDER.search(text)
            if order:
                current = dict(order=order[1], item=order[2], budget=int(order[3]),
                               round=int(order[4]), line=number, byte_start=start)
                orders.append(current)
                last_state = None
            if '[market]' in text and ' registered as ' in text:
                registrations.append(dict(line=number, text=text))
            chosen = SHOP.search(text)
            if chosen and current is not None:
                current.update(shop_name=chosen[1], url=chosen[2])
            if current is not None:
                current['end_line'], current['byte_end'] = number, offset
                if '[sign]' in text:
                    current.setdefault('sign_checks', []).append(dict(line=number, text=text))
                if '[market] ledger #' in text:
                    current['ledger'] = dict(line=number, text=text)
            role, event = parse_event(text)
            if not isinstance(event, dict):
                continue
            kind = event.get('event')
            if event.get('time') and current is not None:
                current.setdefault('time', event['time'])
            if role == 'seller':
                task_id = event.get('task_id')
                if kind == 'decision_input' and task_id:
                    state = event.get('state', {})
                    sellers.setdefault(task_id, dict(task=task_id, phase='after' if 'pricing_policy' in state else 'before',
                                                    first_line=number, time=event.get('time')))
                if kind == 'seller_action' and task_id:
                    task = sellers.setdefault(task_id, dict(task=task_id, phase='unknown', first_line=number))
                    action = event['action']
                    task['item'] = action['item_id']
                    if action['action'] == 'ask':
                        task.setdefault('opening', action['price'])
                    task['last_action'], task['last_line'] = action['action'], number
                    if action['action'] == 'accept':
                        task['accepted_price'] = action['price']
                        task['accept_line'] = number
                if kind == 'seller_promotion_offered' and first_promotion is None:
                    first_promotion = dict(line=number, time=event['time'])
                continue
            if current is None:
                continue
            if event.get('item') and event['item'] != current['item']:
                if kind in ('buyer_action', 'http_response'):
                    uncorrelated.append(dict(line=number, event=kind, event_item=event['item'],
                                             order_item=current['item'], run_id=event.get('run_id')))
                continue
            if kind == 'decision_input' and 'shops' in event.get('state', {}):
                last_state = dict(line=number, state=event['state'], time=event.get('time'))
            if kind == 'market_choice':
                current.update(shop_name=event['shop_name'], url=event['url'], choice_line=number,
                               reason=event['reason'], run_id=event['run_id'])
                if last_state and len(avoidance) < 12:
                    candidates = {s['name'] for s in last_state['state']['shops']}
                    available_bad = candidates & bad_names
                    if available_bad and event['shop_name'] not in available_bad:
                        avoidance.append(dict(order=current['order'], time=event.get('time'),
                            known_mismatch_shops=sorted(available_bad), selected=event['shop_name'],
                            reason=event['reason'], decision_line=last_state['line'], choice_line=number,
                            state=last_state['state']))
            if kind == 'buyer_action' and event.get('action', {}).get('action') == 'offer':
                current['last_offer'] = event['action']['price']
                current['last_offer_task'] = event.get('task_id')
            if kind == 'buyer_final':
                current['outcome'] = event['outcome']
            for task, receipt in completed_receipts(event):
                price = receipt.get('price')
                if type(price) not in (int, float) or current.get('last_offer') is None:
                    continue
                if task.get('id') != current.get('last_offer_task') or not current.get('shop_name'):
                    uncorrelated.append(dict(line=number, event='completed_receipt', reason='ambiguous task or shop'))
                    continue
                if price != current['last_offer'] or price > current['budget'] or receipt.get('item') != current['item']:
                    incident = dict(order=current['order'], shop_name=current.get('shop_name'),
                        url=current.get('url'), time=event.get('time'), item=current['item'], budget=current['budget'],
                        offered=current['last_offer'], receipt=receipt, task=task.get('id'),
                        response_line=number, start_line=current['line'], byte_start=current['byte_start'],
                        byte_end=offset, status_text=task.get('status', {}).get('message'))
                    incidents.append(incident)
                    if incident['shop_name']:
                        bad_names.add(incident['shop_name'])
    stats = {}
    for phase in ('before', 'after', 'unknown'):
        rows = [r for r in sellers.values() if r['phase'] == phase]
        bought = [r for r in rows if 'accepted_price' in r]
        by_item = {}
        for item in sorted({r.get('item') for r in rows if r.get('item')}):
            matching = [r for r in rows if r.get('item') == item]
            accepted = [r['accepted_price'] for r in matching if 'accepted_price' in r]
            by_item[item] = dict(tasks=len(matching), accepts=len(accepted),
                mean_accepted=statistics.mean(accepted) if accepted else None,
                openings=dict(Counter(str(r['opening']) for r in matching if 'opening' in r)))
        stats[phase] = dict(tasks=len(rows), accepts=len(bought),
            mean_accepted=statistics.mean(r['accepted_price'] for r in bought) if bought else None,
            by_item=by_item)
    return dict(source=str(source), source_sha256=digest.hexdigest(), bytes=offset, lines=number,
                registrations=registrations, orders=orders, incidents=incidents, avoidance=avoidance,
                seller_tasks=list(sellers.values()), seller_stats=stats, first_promotion=first_promotion,
                uncorrelated_events=uncorrelated)


def excerpt(source, destination, start, end):
    with source.open('rb') as stream:
        stream.seek(start)
        raw = stream.read(end - start)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_bytes() != raw:
            raise FileExistsError('Refusing to overwrite different evidence: ' + str(destination))
    else:
        destination.write_bytes(raw)
    return dict(path=str(destination.relative_to(ROOT)), byte_start=start, byte_end=end,
                sha256=hashlib.sha256(raw).hexdigest())


def collect(source, label='historical'):
    if re.fullmatch(r'[a-z0-9-]+', label) is None:
        raise ValueError('Use a simple new evidence label')
    out = ROOT / 'logs' / label
    if (out / 'analysis.json').exists():
        raise FileExistsError('Evidence already exists; do not overwrite an analysis')
    before = source.stat()
    data = scan(source)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError('Source changed during scan; retry when stable')
    exports = []
    # A complete chronological prefix, not stitched-together log lines.
    with source.open('rb') as stream:
        prefix = stream.read(1024 * 1024)
    prefix_end = prefix.rfind(b'\n') + 1
    prefix_path = ROOT / 'logs/market-kit.log'
    if prefix_path.exists() and prefix_path.read_bytes() != prefix[:prefix_end]:
        prefix_path = out / 'source-prefix.log'
    exports.append(excerpt(source, prefix_path, 0, prefix_end))
    for index, incident in enumerate(data['incidents'][:5], 1):
        order = next(o for o in data['orders'] if o['order'] == incident['order'])
        exports.append(excerpt(source, ROOT / 'logs/challenge-2' / ('%s-incident-%02d.log' % (label, index)),
                               order['byte_start'], order['byte_end']))
    wanted = {n for a in data['avoidance'][:3] for n in (a['decision_line'], a['choice_line'])}
    for phase in ('before', 'after'):
        rows = [t for t in data['seller_tasks'] if t['phase'] == phase and 'accept_line' in t][:3]
        wanted.update(n for t in rows for n in (t['first_line'], t['accept_line']))
    offset = 0
    with source.open('rb') as stream:
        for number, raw in enumerate(stream, 1):
            if number in wanted:
                exports.append(excerpt(source, out / ('line-%06d.log' % number), offset, offset + len(raw)))
            offset += len(raw)
    write_json(out / 'analysis.json', data)
    write_json(out / 'provenance.json', dict(source=str(source), source_sha256=data['source_sha256'],
        source_bytes=data['bytes'], source_mtime_ns=after.st_mtime_ns,
        note='Unmodified contiguous byte excerpts of week-07; not new week-07-2 market runs.', exports=exports))
    boards = {}
    for rnd in (0, 1, 2):
        snapshot = dict(observed_at=datetime.now(timezone.utc).isoformat(), round=rnd)
        try:
            with urllib.request.urlopen('https://market.ourolabs.ai/api/board?round=%d' % rnd, timeout=20) as response:
                board = json.load(response)
            snapshot['board'] = board
            boards[str(rnd)] = {role: [r for r in board.get(role, []) if r.get('name') == 'leeuichann']
                                for role in ('shops', 'buyers')}
        except Exception as exc:
            snapshot['error'] = type(exc).__name__ + ': ' + str(exc)
            boards[str(rnd)] = {'error': snapshot['error']}
        write_json(out / ('board-round-%d.json' % rnd), snapshot)
    write_json(out / 'own-board-summary.json', boards)
    print(json.dumps(dict(source_sha256=data['source_sha256'], orders=len(data['orders']),
        incidents=[{k:i[k] for k in ('shop_name','offered','budget','response_line')} for i in data['incidents']],
        avoidance=[{k:a[k] for k in ('selected','known_mismatch_shops','choice_line')} for a in data['avoidance'][:3]],
        seller_stats=data['seller_stats'], boards=boards), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=OLD / 'logs/market-kit.log')
    parser.add_argument('--label', default='historical')
    args = parser.parse_args()
    collect(args.source, args.label)
