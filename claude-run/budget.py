"""The shared spending ledger (edu-visualization/ai-cad-set-BUDGET.tsv, a TSV: run, cost_usd, kind, lab).

The 25 Oct 2026 GO set a $50 cap for everything logged below the line that starts with "# --- GO 25 Oct 2026",
and asked for a stop before $45; rows above that line are earlier sets and don't count against it.

    python budget.py check  LEDGER RUN_CAP [STOP_AT]      exit 0 = may start, 2 = stop
    python budget.py record LEDGER RUN COST_OR_EMPTY RUN_CAP LAB   (empty cost = a killed run, counted at RUN_CAP)
    python budget.py total  LEDGER
"""
import os
import sys

MARK = '# --- GO 25 Oct 2026'
STOP_AT = 45.0


def total(path):
    if not os.path.exists(path):
        return 0.0
    s, on = 0.0, False
    with open(path, encoding='utf-8') as f:
        for line in f:
            if line.startswith(MARK):
                on = True
                continue
            if not on or line.startswith('#') or not line.strip():
                continue
            s += float(line.split('\t')[1])
    return round(s, 4)


def allowed(spent, run_cap, stop_at=STOP_AT):
    return spent + run_cap <= stop_at + 1e-9


def record(path, run, cost, run_cap, lab):
    kind = 'logged' if cost is not None else 'killed-floor'
    value = float(cost) if cost is not None else float(run_cap)
    with open(path, 'a', encoding='utf-8', newline='\n') as f:
        f.write(f'{run}\t{value:.4f}\t{kind}\t{lab}\n')
    return total(path)


if __name__ == '__main__':
    cmd, ledger = sys.argv[1], sys.argv[2]
    if cmd == 'check':
        stop = float(sys.argv[4]) if len(sys.argv) > 4 else STOP_AT
        t = total(ledger)
        ok = allowed(t, float(sys.argv[3]), stop)
        print(f'GO-25-Oct spend ${t:.4f}; this run may cost up to ${float(sys.argv[3]):.2f}; stop at ${stop:.2f}: '
              f'{"GO" if ok else "STOP"}')
        sys.exit(0 if ok else 2)
    if cmd == 'record':
        c = sys.argv[4]
        print(f'GO-25-Oct total now ${record(ledger, sys.argv[3], float(c) if c else None, float(sys.argv[5]), sys.argv[6]):.4f}')
    if cmd == 'total':
        print(f'{total(ledger):.4f}')
