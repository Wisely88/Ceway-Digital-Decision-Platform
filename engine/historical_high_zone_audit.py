"""Read-only DLT historical high-zone audit. No prediction weights or ticket generation."""
import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

def validate(rows):
    seen = set()
    clean = []
    for row in rows:
        issue = str(row["issue"]).strip()
        if issue in seen:
            raise ValueError(f"duplicate issue {issue}")
        seen.add(issue)
        front = [int(row[f"f{i}"]) for i in range(1, 6)]
        back = [int(row[f"b{i}"]) for i in range(1, 3)]
        if len(set(front)) != 5 or any(not 1 <= n <= 35 for n in front):
            raise ValueError(f"invalid front area {issue}")
        if len(set(back)) != 2 or any(not 1 <= n <= 12 for n in back):
            raise ValueError(f"invalid back area {issue}")
        clean.append((issue, front))
    return sorted(clean, key=lambda item: int(item[0]))

def distribution(high_count):
    denom = math.comb(35, 5)
    return [math.comb(high_count, k) * math.comb(35-high_count, 5-k) / denom
            if k <= high_count and 5-k <= 35-high_count else 0.0 for k in range(6)]

def binomial_upper(n, k, p):
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    # scipy-free exact tail via logsumexp, stable for small p
    logs = [math.lgamma(n+1)-math.lgamma(j+1)-math.lgamma(n-j+1)
            +j*math.log(p)+(n-j)*math.log1p(-p) for j in range(k,n+1)]
    peak = max(logs)
    return math.exp(peak)*math.fsum(math.exp(x-peak) for x in logs)

def audit(rows, lower=29, upper=35, start=7001, end=13153):
    if not 1 <= lower <= upper <= 35:
        raise ValueError("invalid high zone")
    selected = [(issue, front) for issue, front in validate(rows)
                if start <= int(issue) <= end]
    if not selected:
        raise ValueError("no rows in range")
    counts = Counter(sum(lower <= x <= upper for x in front) for _, front in selected)
    n = len(selected)
    probs = distribution(upper-lower+1)
    threshold = 3
    observed = sum(counts[k] for k in range(threshold, 6))
    p0 = sum(probs[threshold:])
    return dict(zone=[lower,upper], issue_range=[start,end], draws=n,
                observed_total=sum(k*counts[k] for k in range(6)),
                expected_total=n*5*(upper-lower+1)/35,
                count_histogram={str(k):counts[k] for k in range(6)},
                expected_histogram={str(k):n*probs[k] for k in range(6)},
                observed_at_least_three=observed,
                expected_at_least_three=n*p0,
                fixed_hypothesis_upper_tail_p=binomial_upper(n,observed,p0),
                warning="Post-hoc zone, window and threshold searches require multiplicity correction. No forecasting implication.")

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("csv_path",type=Path)
    parser.add_argument("--lower",type=int,default=29)
    parser.add_argument("--upper",type=int,default=35)
    parser.add_argument("--start",type=int,default=7001)
    parser.add_argument("--end",type=int,default=13153)
    args=parser.parse_args()
    with args.csv_path.open(encoding="utf-8-sig",newline="") as handle:
        result=audit(csv.DictReader(handle),args.lower,args.upper,args.start,args.end)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
