import argparse
import asyncio
import random
import time
from collections import Counter

import httpx


PRIORITIES = ["LOW", "MEDIUM", "HIGH"]


def _make_payload(i: int) -> dict:
    p = random.choice(PRIORITIES)
    return {
        "title": f"load-{i}",
        "description": f"generated-{i}",
        "priority": p,
    }


async def _post_one(client: httpx.AsyncClient, url: str, i: int) -> tuple[int, str | None]:
    try:
        r = await client.post(url, json=_make_payload(i))
        if r.status_code >= 400:
            return r.status_code, None
        data = r.json()
        return r.status_code, data.get("id")
    except Exception:
        return 0, None


async def _get_status_one(client: httpx.AsyncClient, url: str, task_id: str) -> str | None:
    try:
        r = await client.get(url)
        if r.status_code >= 400:
            return None
        data = r.json()
        return data.get("status")
    except Exception:
        return None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    ap.add_argument("--n", type=int, default=1000, help="Number of tasks")
    ap.add_argument("--c", type=int, default=50, help="Concurrency")
    ap.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout seconds")
    ap.add_argument("--check", action="store_true", help="Poll statuses after creation")
    ap.add_argument("--check-interval", type=float, default=0.5, help="Seconds between polls")
    ap.add_argument("--check-timeout", type=float, default=30.0, help="Max seconds to wait for completion")
    args = ap.parse_args()

    create_url = f"{args.base_url}/api/v1/tasks"
    status_url_tpl = f"{args.base_url}/api/v1/tasks/{{task_id}}/status"

    limits = httpx.Limits(max_connections=args.c * 2, max_keepalive_connections=args.c)
    timeout = httpx.Timeout(args.timeout)

    sem = asyncio.Semaphore(args.c)
    ids: list[str] = []
    codes = Counter()

    t0 = time.perf_counter()
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:

        async def run_one(i: int) -> None:
            async with sem:
                code, tid = await _post_one(client, create_url, i)
                codes[code] += 1
                if tid:
                    ids.append(tid)

        await asyncio.gather(*(run_one(i) for i in range(args.n)))

    dt = time.perf_counter() - t0
    ok = sum(v for k, v in codes.items() if k and k < 400)
    rps = ok / dt if dt > 0 else 0.0

    print(f"created: {len(ids)}/{args.n} ok={ok} in {dt:.2f}s rps={rps:.1f}")
    print("codes:", dict(codes))

    if not args.check or not ids:
        return

    t1 = time.perf_counter()
    pending = set(ids)
    final = Counter()

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        while pending and (time.perf_counter() - t1) < args.check_timeout:
            batch = list(pending)
            sem2 = asyncio.Semaphore(args.c)

            async def check_one(tid: str) -> None:
                async with sem2:
                    s = await _get_status_one(client, status_url_tpl.format(task_id=tid), tid)
                    if s in ("COMPLETED", "FAILED", "CANCELLED"):
                        pending.discard(tid)
                        final[s] += 1

            await asyncio.gather(*(check_one(tid) for tid in batch))
            print(f"final={dict(final)} pending={len(pending)}")
            if pending:
                await asyncio.sleep(args.check_interval)

    if pending:
        final["NOT_FINISHED"] = len(pending)
    print("result:", dict(final))


if __name__ == "__main__":
    asyncio.run(main())