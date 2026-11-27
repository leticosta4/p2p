"""Execute: python experiment.py --samples 300 --seed 42."""

import argparse
import json

if __package__:
    from .flooding import compare
    from .simulation import experiment
else:
    from flooding import compare
    from simulation import experiment


def main():
    parser = argparse.ArgumentParser(description="Saltos médios × N, sem navegador.")
    parser.add_argument("--samples", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bases", type=int, nargs="+", default=[2, 4, 16])
    parser.add_argument("--sizes", type=int, nargs="+", default=[10, 20, 50, 100, 200, 500, 1000])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--inundacao", action="store_true",
                        help="Compara o Pastry (base 16) com busca por inundação.")
    parser.add_argument("--ttls", type=int, nargs="+", default=[2, 4, 7])
    parser.add_argument("--grau", type=int, default=4,
                        help="Vizinhos por nó na rede não estruturada.")
    args = parser.parse_args()
    if args.inundacao:
        return print_flooding(args)
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


def print_flooding(args):
    result = compare(args.sizes, args.ttls, args.grau, args.samples, args.seed)
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(f"Semente: {args.seed} | {args.samples} buscas por ponto | grau ~{args.grau}")
    print("    N  Método              Mensagens  Sucesso  Nós alcançados")
    for row in result["rows"]:
        print(f"{row['n']:5}  {'Pastry (base 16)':18} {row['pastry_messages']:10.1f}"
              f"  {row['pastry_success']:6.0%}  {'—':>14}")
        for item in row["flooding"]:
            print(f"{'':5}  {'Inundação TTL ' + str(item['ttl']):18} {item['messages']:10.1f}"
                  f"  {item['success']:6.0%}  {item['reached']:14.1f}")


if __name__ == "__main__":
    main()
