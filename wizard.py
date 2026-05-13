import json

from cisco_pkt import generate_from_config


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


def _prompt_bool(text: str, default: bool = False) -> bool:
    default_str = "y" if default else "n"
    raw = _prompt(f"{text} (y/n)", default_str).lower()
    return raw in {"y", "yes"}


def _collect_routers() -> list[dict]:
    routers = []
    count = _prompt_int("How many routers", 2)
    for idx in range(count):
        print(f"\nRouter {idx + 1}:")
        name = _prompt("Name")
        fast = _prompt_int("FastEthernet count", 0)
        gigabit = _prompt_int("GigabitEthernet count", 1)
        serial = _prompt_int("Serial count", 1)
        is_isp = _prompt_bool("Is this the ISP router", False)
        router_cfg = {
            "name": name,
            "interfaces": {"fast": fast, "gigabit": gigabit, "serial": serial},
        }
        if is_isp:
            router_cfg["is_isp"] = True
        routers.append(router_cfg)
    return routers


def _collect_switches() -> list[dict]:
    switches = []
    count = _prompt_int("How many switches", 0)
    for idx in range(count):
        print(f"\nSwitch {idx + 1}:")
        name = _prompt("Name")
        vlans = []
        vlan_count = _prompt_int("How many VLANs", 0)
        for v_idx in range(vlan_count):
            print(f"  VLAN {v_idx + 1}:")
            vlan_id = _prompt_int("  VLAN ID")
            hosts = _prompt_int("  Host count", 0)
            vlan_name = _prompt("  VLAN name")
            vlans.append({"id": vlan_id, "hosts": hosts, "name": vlan_name})
        switch_cfg = {"name": name, "vlans": vlans}
        if _prompt_bool("  Configure management SVI", False):
            mgmt_vlan = _prompt_int("  Management VLAN", 1)
            mgmt_ip = _prompt("  Management IP")
            mgmt_mask = _prompt("  Management mask")
            mgmt_gw = _prompt("  Default gateway")
            switch_cfg["management"] = {
                "vlan": mgmt_vlan,
                "ip": mgmt_ip,
                "mask": mgmt_mask,
                "default_gateway": mgmt_gw,
            }
        if _prompt_bool("  Configure access ranges", False):
            ranges = []
            range_count = _prompt_int("  Number of access ranges", 0)
            for r_idx in range(range_count):
                print(f"  Access range {r_idx + 1}:")
                vlan_id = _prompt_int("  VLAN ID")
                range_str = _prompt("  Interface range (e.g., FastEthernet0/2-6)")
                ranges.append({"vlan_id": vlan_id, "range": range_str})
            switch_cfg["access_ranges"] = ranges
        if _prompt_bool("  Skip VLAN 1 in VLAN database", False):
            switch_cfg["skip_vlan_1"] = True
        if _prompt_bool("  Configure trunk ports", False):
            trunks = []
            trunk_count = _prompt_int("  Number of trunk ports", 0)
            for t_idx in range(trunk_count):
                trunks.append(_prompt(f"  Trunk port {t_idx + 1}"))
            switch_cfg["trunk_ports"] = trunks
        switches.append(switch_cfg)
    return switches


def _collect_links() -> list[dict]:
    links = []
    print("\nDefine links. Leave type empty to finish.")
    while True:
        link_type = _prompt("Link type (serial/trunk/switch)").strip().lower()
        if not link_type:
            break
        if link_type == "serial":
            a = _prompt("  Router A")
            a_port = _prompt("  Router A port (e.g., Serial0/0/0)")
            b = _prompt("  Router B")
            b_port = _prompt("  Router B port (e.g., Serial0/0/0)")
            network_ip = _prompt("  Link network (optional CIDR, blank to auto)", "")
            link = {"type": "serial", "a": a, "a_port": a_port, "b": b, "b_port": b_port}
            if network_ip:
                link["network_ip"] = network_ip
            links.append(link)
        elif link_type == "trunk":
            router = _prompt("  Router")
            router_port = _prompt("  Router port")
            switch = _prompt("  Switch")
            switch_port = _prompt("  Switch port", "GigabitEthernet0/1")
            links.append({
                "type": "trunk",
                "router": router,
                "router_port": router_port,
                "switch": switch,
                "switch_port": switch_port,
            })
        elif link_type == "switch":
            a = _prompt("  Switch A")
            a_port = _prompt("  Switch A port")
            b = _prompt("  Switch B")
            b_port = _prompt("  Switch B port")
            links.append({
                "type": "switch",
                "a": a,
                "a_port": a_port,
                "b": b,
                "b_port": b_port,
            })
        else:
            print("Unknown link type. Use serial, trunk, or switch.")
    return links


def _collect_subnets() -> list[dict]:
    subnets = []
    if not _prompt_bool("Add LAN subnets", False):
        return subnets
    count = _prompt_int("How many subnets", 0)
    for idx in range(count):
        print(f"Subnet {idx + 1}:")
        router = _prompt("  Router name")
        hosts = _prompt_int("  Host count")
        name = _prompt("  Subnet name")
        port = _prompt("  Router port (non-serial)")
        subnets.append({"router": router, "hosts": hosts, "name": name, "port": port})
    return subnets


def build_config() -> dict:
    print("Packet Tracer Config Wizard")
    base_ip = _prompt("Base IP (e.g., 192.168.1.0)")
    routers = _collect_routers()
    switches = _collect_switches()
    subnets = _collect_subnets()
    links = _collect_links()

    routing = {
        "auto_static": _prompt_bool("Compute auto static routes", True),
        "auto_static_out_interface": _prompt_bool("Use out-interface for auto static routes", True),
        "ospf": _prompt_bool("Enable OSPF", False),
    }

    dhcp = {
        "enabled": _prompt_bool("Enable DHCP", False),
        "dns_enabled": _prompt_bool("Enable DNS", False),
        "dns_server": _prompt("DNS server", "8.8.8.8"),
    }

    output = {
        "commands": _prompt("Commands output file", "packet_tracer_commands.txt"),
        "answers": _prompt("Answers CSV file", "answers.csv"),
        "banner": _prompt("Banner text", "Unauthorized access is strictly prohibited."),
    }

    return {
        "base_ip": base_ip,
        "routers": routers,
        "switches": switches,
        "subnets": subnets,
        "links": links,
        "routing": routing,
        "dhcp": dhcp,
        "output": output,
    }


def main() -> None:
    config = build_config()
    output_path = _prompt("Save config to (json)", "config.json")
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
    print(f"Saved config to {output_path}")

    if _prompt_bool("Generate outputs now", True):
        generate_from_config(config)
        print("Generation complete.")


if __name__ == "__main__":
    main()
