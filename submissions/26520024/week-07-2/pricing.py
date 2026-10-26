"""Frozen historical targets; live reserves and price guards remain authoritative."""
import json
from pathlib import Path


def load_policy(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('version') != 1 or not isinstance(data.get('targets'), dict):
        raise ValueError('Unsupported pricing policy')
    for item, price in data['targets'].items():
        if not isinstance(item, str) or type(price) is not int or price < 0:
            raise ValueError('Targets require item IDs and nonnegative integer prices')
    return data


def target_asks(candidates, policy):
    targets = {}
    for product in candidates:
        reserve = product['reserve']
        ceiling = reserve * 110 // 100
        target = policy['targets'].get(product['id'], ceiling)
        if type(target) is not int or not reserve <= target <= ceiling:
            raise ValueError('Historical target violates the current reserve or markup cap')
        targets[product['id']] = target
    return targets
