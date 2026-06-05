import json
import os
import datetime

HISTORY_FILE = 'assembly_history.json'

def save_assembly_result(item_count, duration_seconds):
    now = datetime.datetime.now()
    entry = {
        'timestamp': now.isoformat(),
        'item_count': item_count,
        'duration_seconds': duration_seconds
    }

    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except:
            history = []

    history.append(entry)

    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def get_statistics():
    if not os.path.exists(HISTORY_FILE):
        return None

    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)
    except:
        return None

    now = datetime.datetime.now()
    week_ago = now - datetime.timedelta(days=7)
    month_ago = now - datetime.timedelta(days=30)

    stats = {
        'week': {'count': 0, 'items': 0, 'time': 0},
        'month': {'count': 0, 'items': 0, 'time': 0},
        'total': {'count': 0, 'items': 0, 'time': 0}
    }

    for entry in history:
        dt = datetime.datetime.fromisoformat(entry['timestamp'])
        items = entry['item_count']
        time = entry['duration_seconds']

        # Total
        stats['total']['count'] += 1
        stats['total']['items'] += items
        stats['total']['time'] += time

        # Week
        if dt >= week_ago:
            stats['week']['count'] += 1
            stats['week']['items'] += items
            stats['week']['time'] += time

        # Month
        if dt >= month_ago:
            stats['month']['count'] += 1
            stats['month']['items'] += items
            stats['month']['time'] += time

    return stats

def format_duration(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}ч {m}м {s}с"
    return f"{m}м {s}с"
