"""Execute: python experiment.py --samples 300 --seed 42."""

import argparse
import json

if __package__:
    from .simulation import experiment
else:
    from simulation import experiment


def main():
    parser = argparse.ArgumentParser(description="Saltos médios × N, sem navegador.")
    parser.add_argument("--samples", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bases", type=int, nargs="+", default=[2, 4, 16])
    parser.add_argument("--sizes", type=int, nargs="+", default=[10, 20, 50, 100, 200, 500, 1000])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = experiment(args.sizes, args.bases, args.samples, args.seed)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Semente: {args.seed} | {args.samples} buscas por ponto")
        print("Base     N     Média   Máximo   log_b(N)")
        for series in result["series"]:
            for point in series["points"]:
                print(f"{series['base']:4} {point['n']:5} {point['mean']:9.3f}"
                      f" {point['max']:8} {point['theoretical']:10.3f}")


if __name__ == "__main__":
    main()
