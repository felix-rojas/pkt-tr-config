import sys

from cisco_pkt import generate_from_config


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 csv_generate.py <config.csv>")
        raise SystemExit(2)

    generate_from_config(sys.argv[1])


if __name__ == "__main__":
    main()
