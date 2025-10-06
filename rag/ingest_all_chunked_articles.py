import os
import sys
import csv
import time
import json
import argparse
import subprocess
from typing import Dict, List, Set

from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

CSV_PATH = os.path.join(PROJECT_ROOT, 'SB_publication_PMC.csv')
CHECKPOINT_PATH = os.path.join(PROJECT_ROOT, 'ingest_checkpoint.jsonl')
PYTHON = os.getenv('PYTHON', sys.executable)

DEFAULT_SLEEP_MS = int(os.getenv('ARTICLE_SLEEP_MS', '300'))
DEFAULT_TIMEOUT_SEC = int(os.getenv('ARTICLE_TIMEOUT_SEC', '300'))


def read_checkpoint() -> Set[str]:
    done: Set[str] = set()
    if not os.path.exists(CHECKPOINT_PATH):
        return done
    with open(CHECKPOINT_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                rec = json.loads(line)
                if rec.get('url'):
                    done.add(rec['url'])
            except Exception:
                continue
    return done


def append_checkpoint(url: str, status: str):
    with open(CHECKPOINT_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'url': url, 'status': status, 'ts': int(time.time())}) + '\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Drive per-article ingestion as separate processes with checkpointing.')
    ap.add_argument('--start', type=int, default=0, help='Start row index (inclusive)')
    ap.add_argument('--end', type=int, default=-1, help='End row index (exclusive), -1 = to end')
    ap.add_argument('--sleep-ms', type=int, default=DEFAULT_SLEEP_MS, help='Sleep between articles (ms)')
    ap.add_argument('--timeout-sec', type=int, default=DEFAULT_TIMEOUT_SEC, help='Per-article timeout; skip on timeout')
    ap.add_argument('--pipeline', action='store_true', help='Use ingest_single_article_pipeline.py (ES-side embeddings)')
    args = ap.parse_args()

    # Load CSV
    rows: List[Dict[str, str]] = []
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            print('No header row in CSV')
            sys.exit(2)
        reader.fieldnames = [name.strip().lower() for name in reader.fieldnames if name]
        for row in reader:
            title = (row.get('title') or '').strip()
            url = (row.get('link') or '').strip()
            if title and url:
                rows.append({'title': title, 'url': url})

    if args.end == -1 or args.end > len(rows):
        args.end = len(rows)
    rows = rows[args.start:args.end]

    done = read_checkpoint()
    print(f"📄 Articles queued: {len(rows)}; already done: {len(done)}")

    sleep_sec = max(0, args.sleep_ms) / 1000.0
    script_name = 'ingest_single_article_pipeline.py' if args.pipeline else 'ingest_single_article_chunked.py'

    for i, row in enumerate(rows, 1):
        url = row['url']
        if url in done:
            continue
        print(f"\n▶️  [{i}/{len(rows)}] {row['title'][:80]} …")
        cmd = [PYTHON, os.path.join(os.path.dirname(__file__), script_name), '--url', url, '--title', row['title']]
        try:
            result = subprocess.run(cmd, timeout=args.timeout_sec)
            rc = result.returncode
            if rc == 0:
                append_checkpoint(url, 'ok')
            else:
                append_checkpoint(url, f'rc={rc}')
        except subprocess.TimeoutExpired:
            print(f"   • Timeout after {args.timeout_sec}s. Skipping.")
            append_checkpoint(url, 'timeout')
        except Exception as e:
            print(f"   • Subprocess failed: {e}")
            append_checkpoint(url, 'exception')
        time.sleep(sleep_sec)

    print("\n✅ Driver finished. Checkpoint at:", CHECKPOINT_PATH)
