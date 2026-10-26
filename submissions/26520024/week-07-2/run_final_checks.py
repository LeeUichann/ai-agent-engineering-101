"""Offline audit plus the unchanged official structural checker; no deployment."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from collect_evidence import excerpt, parse_event, write_json
from prepare_history import HISTORY, ROOT, verified_observations

REPO = ROOT.parents[2]


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    out=ROOT/'logs'/('final-checks-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir()
    provenance=json.loads((HISTORY/'provenance.json').read_text())
    source=Path(provenance['source'])
    assert file_hash(source)==provenance['source_sha256'], 'Original source log changed'
    with source.open('rb') as original:
        for row in provenance['exports']:
            size=row['byte_end']-row['byte_start']
            original.seek(row['byte_start'])
            expected=original.read(size)
            with (ROOT/row['path']).open('rb') as exported:
                actual=exported.read(size)
            assert actual==expected and hashlib.sha256(actual).hexdigest()==row['sha256'], row['path']
    analysis=json.loads((HISTORY/'analysis.json').read_text())
    events, selected_lines, accepted = [], [], {}
    phase_by_task={r['task']:r['phase'] for r in analysis['seller_tasks']}
    with source.open('rb') as original:
        for number, raw in enumerate(original,1):
            if b'[seller]' not in raw or b'"event": "seller_action"' not in raw:
                continue
            role,event=parse_event(raw.decode('utf-8'))
            if role!='seller' or not event or event.get('event')!='seller_action':
                continue
            events.append(raw)
            selected_lines.append(number)
            if event['action']['action']=='accept':
                accepted[event['task_id']]=event['action']['price']
    event_data=b''.join(events)
    event_path=ROOT/'logs/challenge-1/seller-action-lines.log'
    if event_path.exists():
        assert event_path.read_bytes()==event_data, 'Do not replace different extracted evidence'
    else:
        event_path.write_bytes(event_data)
    for phase in ('before','after'):
        prices=[price for task,price in accepted.items() if phase_by_task[task]==phase]
        expected=analysis['seller_stats'][phase]
        assert len(prices)==expected['accepts']
        assert abs(sum(prices)/len(prices)-expected['mean_accepted'])<1e-9
    write_json(out/'seller-action-provenance.json',dict(source_sha256=provenance['source_sha256'],
        path=str(event_path.relative_to(ROOT)),sha256=hashlib.sha256(event_data).hexdigest(),
        original_lines=selected_lines,phase_by_task=phase_by_task,
        note='Selected complete raw seller_action lines, not a contiguous or newly executed market log.'))
    counted=next(order for order in analysis['orders'] if order['round']==2 and
                 'verified True' in order.get('ledger',{}).get('text',''))
    exported=excerpt(source,ROOT/'logs/challenge-2/round2-counted-order.log',counted['byte_start'],counted['byte_end'])
    write_json(out/'round2-order-provenance.json',dict(source_sha256=provenance['source_sha256'],
               order=counted['order'],start_line=counted['line'],end_line=counted['end_line'],export=exported))
    assert len(verified_observations())==2
    for path in ROOT.glob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
    completed=sorted(p for p in (ROOT/'logs').glob('lab2-*') if (p/'exit-status.json').exists())[-1]
    manifest=json.loads((completed/'source-hashes.json').read_text())
    runtime=('seller.py','buyer.py','market_buyer.py','trade_memory.py','core.py','wire.py',
             'codex_backend.py','rps_promotion.py','pricing.py','pricing_policy.json','agent.json','catalog.json')
    for name in runtime:
        path=ROOT/name
        assert file_hash(path)==manifest[str(path.relative_to(REPO))], name
    status={}
    commands={
        'offline':[sys.executable,'-m','unittest','discover','-s',str(ROOT),'-p','test_*.py','-v'],
        'structural':[sys.executable,str(REPO/'scripts/check_week07.py'),str(ROOT),'--github','LeeUichann'],
        'shell_syntax':['bash','-n',str(ROOT/'start_market.sh')],
        'original_tracked_files':['git','diff','--exit-code','--',str(ROOT.parent/'week-07')],
    }
    for name,command in commands.items():
        with (out/(name+'.log')).open('w') as log:
            result=subprocess.run(command,cwd=REPO,stdout=log,stderr=subprocess.STDOUT,timeout=90)
        status[name]=result.returncode
        print(name+': '+str(result.returncode),flush=True)
    keys={name:dict(size=(ROOT/name).stat().st_size,mtime_ns=(ROOT/name).stat().st_mtime_ns)
          for name in ('shop_key.pem','buyer_key.pem')}
    write_json(out/'audit.json',dict(status=status,original_log_hash_matches=True,
        raw_excerpt_hashes_verified=len(provenance['exports']),verified_incidents=2,
        price_statistics_rechecked_from_raw_events=True,
        official_test_runtime_hashes_unchanged=True,official_test_run=str(completed.relative_to(ROOT)),
        original_keys_metadata=keys,public_market_restarted=False,
        note='Structural checker does not require alive=True; offline market status remains an operational gap.'))
    write_json(out/'final-source-hashes.json',{p.name:file_hash(p) for p in ROOT.iterdir()
               if p.is_file() and not p.is_symlink() and p.suffix in ('.py','.json','.sh','.md')})
    print('FINAL_AUDIT='+str(out))
    return int(any(status.values()))


if __name__=='__main__':
    raise SystemExit(main())
