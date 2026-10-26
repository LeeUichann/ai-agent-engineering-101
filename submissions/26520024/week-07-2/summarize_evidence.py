"""Recalculate assignment metrics from preserved snapshots; never invent live results."""
import csv
import json
from pathlib import Path

from collect_evidence import write_json

ROOT = Path(__file__).resolve().parent


def main():
    history = ROOT / 'logs/historical-verified'
    analysis = json.loads((history / 'analysis.json').read_text())
    before = json.loads((ROOT / 'logs/challenge-1/before-deployment-snapshot.json').read_text())
    boards = json.loads((history / 'own-board-summary.json').read_text())
    pre, post = before['round1_board'][0], boards['2']['shops'][0]
    comparison = dict(
        before=dict(scope='Round 1 cumulative at the saved pre-change snapshot', observed_at=before['observed_at'],
                    deals=pre['deals'], share=pre['share'], revenue=pre['revenue'], mean_price=pre['revenue']/pre['deals']),
        after=dict(scope='Round 2 cumulative, different rules and duration; not an A/B estimate',
                   observed_at=json.loads((history/'board-round-2.json').read_text())['observed_at'],
                   deals=post['deals'], share=post['share'], revenue=post['revenue'], mean_price=post['revenue']/post['deals']),
        local_decisions=analysis['seller_stats'],
        interpretation='Lower mean price, no observed rounded share increase (0.4% to 0.4%). '
                       'Round, signatures, reviews, item mix and duration changed together. No causal performance claim.')
    write_json(ROOT / 'logs/challenge-1/comparison.json', comparison)
    rows=[]
    for phase in ('before','after'):
        data=comparison[phase]
        rows.append(dict(scope='market_counted', phase=phase,item='all',deals=data['deals'],
                         mean_price=data['mean_price'],share=data['share']))
        for item,data in analysis['seller_stats'][phase]['by_item'].items():
            rows.append(dict(scope='local_seller_acceptance_not_market_counted',phase=phase,item=item,
                             deals=data['accepts'],mean_price=data['mean_accepted'],share=''))
    with (ROOT/'logs/challenge-1/comparison.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=('scope','phase','item','deals','mean_price','share'))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(comparison,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
