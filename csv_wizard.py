from csv_config import write_csv_template


def _prompt(text: str, default: str | None = None) -> str:
    if default is not None:
        value = input(f"{text} [{default}]: ").strip()
        return value or default
    return input(f"{text}: ").strip()


def _prompt_int(text: str, default: int | None = None) -> int:
    while True:
        raw = _prompt(text, str(default) if default is not None else None)
        try:
            return int(raw)
        except ValueError:
            print("Please enter a number.")


def main() -> None:
    print("Packet Tracer CSV Template Wizard")
    base_ip = _prompt("Base IP (e.g., 192.168.1.0)", "192.168.1.0")
    router_count = _prompt_int("How many routers", 2)
    switch_count = _prompt_int("How many switches", 0)
    vlan_count = _prompt_int("How many VLANs", 0)
    output_path = _prompt("CSV template output file", "config_template.csv")

    write_csv_template(
        output_path=output_path,
        router_count=router_count,
        switch_count=switch_count,
        vlan_count=vlan_count,
        base_ip=base_ip,
    )

    print(f"CSV template saved to {output_path}")


if __name__ == "__main__":
    main()
