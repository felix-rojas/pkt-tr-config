import json
from pathlib import Path

import pandas as pd
from router import Router, Switch
from vlsm import calculate_vlsm_from_routers
from pkt_tr_utils import normalize_interface_name, normalize_port_type


SUPPORTED_LINK_TYPES = {"serial", "trunk", "switch"}


def load_config(source):
    if isinstance(source, dict):
        return source

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Config path not found: {source}")

    if path.suffix.lower() == ".csv":
        from csv_config import load_config_from_csv

        return load_config_from_csv(source)

    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise ImportError("PyYAML is required to load YAML configs.") from exc
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _get_interface_counts(router_cfg: dict) -> tuple[int, int, int]:
    interfaces = router_cfg.get("interfaces", {})
    fast = interfaces.get("fast", router_cfg.get("fast_count", 0))
    gigabit = interfaces.get("gigabit", router_cfg.get("gigabit_count", 0))
    serial = interfaces.get("serial", router_cfg.get("serial_count", 0))
    return int(fast), int(gigabit), int(serial)


def _apply_router_defaults(router: Router, router_cfg: dict, config: dict) -> None:
    routing_cfg = config.get("routing", {})
    dhcp_cfg = config.get("dhcp", {})

    ospf_enabled = routing_cfg.get("ospf", True)
    dhcp_enabled = dhcp_cfg.get("enabled", True)
    dns_enabled = dhcp_cfg.get("dns_enabled", True)
    dns_server = dhcp_cfg.get("dns_server", "8.8.8.8")

    router.disable_ospf = not router_cfg.get("ospf", ospf_enabled)
    router.disable_dhcp = not router_cfg.get("dhcp", dhcp_enabled)
    router.disable_dns = not router_cfg.get("dns_enabled", dns_enabled)
    router.dns_server = router_cfg.get("dns_server", dns_server)

    custom_commands = router_cfg.get("custom_commands")
    if custom_commands:
        router.custom_commands = custom_commands

    for route in router_cfg.get("static_routes", []):
        router.add_static_route(
            route["dest"],
            route["mask"],
            next_hop=route.get("next_hop"),
            out_interface=route.get("out_interface"),
            next_hop_router=route.get("next_hop_router"),
        )


def build_topology(config: dict) -> tuple[list[Router], list[Switch], pd.DataFrame]:
    routers = []
    switches = []
    routers_by_name = {}
    switches_by_name = {}

    isp_router_names = set()
    for router_cfg in config.get("routers", []):
        fast, gigabit, serial = _get_interface_counts(router_cfg)
        router = Router(router_cfg["name"], fast, gigabit, serial)
        if router_cfg.get("is_isp") or router.router_name.lower() == "isp":
            isp_router_names.add(router.router_name)
        _apply_router_defaults(router, router_cfg, config)
        routers.append(router)
        routers_by_name[router.router_name] = router

    for switch_cfg in config.get("switches", []):
        switch = Switch(switch_cfg["name"])
        trunk_ports = switch_cfg.get("trunk_ports")
        if trunk_ports:
            switch.trunk_ports = [normalize_interface_name(p) for p in trunk_ports]
        if "management" in switch_cfg:
            switch.management = switch_cfg.get("management")
        if "access_ranges" in switch_cfg:
            switch.access_ranges = switch_cfg.get("access_ranges", [])
        if "skip_vlan_1" in switch_cfg:
            switch.skip_vlan_1 = bool(switch_cfg.get("skip_vlan_1"))
        for vlan in switch_cfg.get("vlans", []):
            switch.add_vlan(
                vlan_id=vlan["id"],
                hosts=vlan["hosts"],
                name=vlan.get("name"),
                ports=vlan.get("ports"),
            )
        switches.append(switch)
        switches_by_name[switch.name] = switch

    for subnet in config.get("subnets", []):
        router = routers_by_name[subnet["router"]]
        port = subnet.get("port")
        if port:
            normalized_port = normalize_interface_name(port)
            if normalized_port.startswith("Serial"):
                raise ValueError("Serial interfaces are reserved for router links; use a serial link in 'links' instead.")
        router.add_subnet(
            hosts=subnet["hosts"],
            name=subnet.get("name"),
            port_type=normalize_port_type(subnet.get("port_type", "FastEthernet")),
            port=port,
        )

    link_overrides = {}
    for link in config.get("links", []):
        link_type = link.get("type")
        if link_type not in SUPPORTED_LINK_TYPES:
            raise ValueError(f"Unsupported link type: {link_type}")

        if link_type == "serial":
            router_a = routers_by_name[link["a"]]
            router_b = routers_by_name[link["b"]]
            router_a.connect_router(
                router_b,
                local_port=link.get("a_port"),
                remote_port=link.get("b_port"),
            )
            link_network = link.get("network_ip")
            if link_network:
                link_key = frozenset([router_a.router_name, router_b.router_name])
                link_overrides[link_key] = link_network
            elif isp_router_names and (router_a.router_name in isp_router_names or router_b.router_name in isp_router_names):
                # No override provided; this ISP link will be allocated from base IP.
                pass
        elif link_type == "trunk":
            router = routers_by_name[link["router"]]
            switch = switches_by_name[link["switch"]]
            router.connect_switch(
                switch,
                port=link.get("router_port"),
                port_type=normalize_port_type(link.get("router_port_type", "GigabitEthernet")),
                switch_port=link.get("switch_port", "GigabitEthernet0/1"),
            )
        elif link_type == "switch":
            switch_a = switches_by_name[link["a"]]
            switch_b = switches_by_name[link["b"]]
            switch_a.connect_switch(
                switch_b,
                port=link.get("a_port", "GigabitEthernet0/1"),
                other_port=link.get("b_port", "GigabitEthernet0/1"),
            )

    base_ip = config.get("base_ip") or config.get("addressing", {}).get("base_ip")
    if not base_ip:
        raise ValueError("Missing base_ip in config.")

    vlsm_df = calculate_vlsm_from_routers(base_ip, routers, link_overrides=link_overrides)

    routing_cfg = config.get("routing", {})
    if routing_cfg.get("auto_static", False):
        from cisco_pkt import compute_auto_static_routes

        use_out_interface = routing_cfg.get("auto_static_out_interface", False)
        auto_routes = compute_auto_static_routes(routers, vlsm_df, use_out_interface=use_out_interface)
        for router in routers:
            for route in auto_routes.get(router.router_name, []):
                router.add_static_route(
                    route["dest"],
                    route["mask"],
                    next_hop=route.get("next_hop"),
                    out_interface=route.get("out_interface"),
                )

    return routers, switches, vlsm_df


def get_output_paths(config: dict) -> tuple[str, str]:
    output_cfg = config.get("output", {})
    commands_path = output_cfg.get("commands", "packet_tracer_commands.txt")
    answers_path = output_cfg.get("answers", "answers.csv")
    return commands_path, answers_path
