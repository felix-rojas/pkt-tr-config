import csv
from pathlib import Path
from typing import Any


CSV_FIELDS = [
    "type",
    "name",
    "base_ip",
    "fast",
    "gigabit",
    "serial",
    "is_isp",
    "switch",
    "vlan_id",
    "vlan_name",
    "hosts",
    "port",
    "port_type",
    "mgmt_vlan",
    "mgmt_ip",
    "mgmt_mask",
    "mgmt_gw",
    "access_ranges",
    "skip_vlan_1",
    "trunk_ports",
    "link_type",
    "a",
    "a_port",
    "b",
    "b_port",
    "router",
    "router_port",
    "switch_port",
    "network_ip",
    "auto_static",
    "auto_static_out_interface",
    "ospf",
    "dhcp_enabled",
    "dns_enabled",
    "dns_server",
    "commands",
    "answers",
    "banner",
]


def _parse_bool(value: str | None, field: str, line_no: int, errors: list[str]) -> bool | None:
    if value is None:
        return None
    token = str(value).strip().lower()
    if token == "":
        return None
    if token in {"y", "yes", "true", "1", "t"}:
        return True
    if token in {"n", "no", "false", "0", "f"}:
        return False
    errors.append(f"Line {line_no}: invalid boolean for {field} -> '{value}'")
    return None


def _parse_int(value: str | None, field: str, line_no: int, errors: list[str], default: int | None = None) -> int | None:
    if value is None:
        return default
    raw = str(value).strip()
    if raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        errors.append(f"Line {line_no}: invalid integer for {field} -> '{value}'")
        return None


def _split_list(value: str | None) -> list[str]:
    if value is None:
        return []
    raw = str(value).strip()
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    return [p for p in parts if p]


def _parse_access_ranges(value: str | None, line_no: int, errors: list[str]) -> list[dict[str, Any]]:
    ranges = []
    for entry in _split_list(value):
        if ":" not in entry:
            errors.append(
                f"Line {line_no}: access_ranges should be 'VLAN_ID:INTERFACE_RANGE' -> '{entry}'"
            )
            continue
        vlan_id, range_str = entry.split(":", 1)
        vlan_id = vlan_id.strip()
        range_str = range_str.strip()
        if not vlan_id or not range_str:
            errors.append(
                f"Line {line_no}: access_ranges should be 'VLAN_ID:INTERFACE_RANGE' -> '{entry}'"
            )
            continue
        try:
            vlan_id_int = int(vlan_id)
        except ValueError:
            errors.append(f"Line {line_no}: invalid VLAN ID in access_ranges -> '{entry}'")
            continue
        ranges.append({"vlan_id": vlan_id_int, "range": range_str})
    return ranges


def write_csv_template(
    output_path: str,
    router_count: int,
    switch_count: int,
    vlan_count: int,
    base_ip: str = "192.168.1.0",
) -> None:
    rows: list[dict[str, str]] = []

    rows.append({"type": "base", "base_ip": base_ip})

    for idx in range(router_count):
        rows.append(
            {
                "type": "router",
                "name": f"ROUTER_{idx + 1}",
                "fast": "0",
                "gigabit": "1",
                "serial": "1",
            }
        )

    for idx in range(switch_count):
        rows.append(
            {
                "type": "switch",
                "name": f"SWITCH_{idx + 1}",
            }
        )

    default_switch = f"SWITCH_1" if switch_count > 0 else ""
    for idx in range(vlan_count):
        rows.append(
            {
                "type": "vlan",
                "switch": default_switch,
                "vlan_id": str(idx + 1),
                "vlan_name": f"VLAN_{idx + 1}",
            }
        )

    rows.append({"type": "subnet"})
    rows.append({"type": "link"})

    rows.append(
        {
            "type": "routing",
            "auto_static": "true",
            "auto_static_out_interface": "true",
            "ospf": "false",
        }
    )
    rows.append(
        {
            "type": "dhcp",
            "dhcp_enabled": "false",
            "dns_enabled": "false",
            "dns_server": "8.8.8.8",
        }
    )
    rows.append(
        {
            "type": "output",
            "commands": "packet_tracer_commands.txt",
            "answers": "answers.csv",
            "banner": "Unauthorized access is strictly prohibited.",
        }
    )

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            full_row = {key: "" for key in CSV_FIELDS}
            for key, value in row.items():
                full_row[key] = "" if value is None else str(value)
            writer.writerow(full_row)


def load_config_from_csv(source: str) -> dict:
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Config path not found: {source}")

    config: dict[str, Any] = {
        "routers": [],
        "switches": [],
        "subnets": [],
        "links": [],
    }

    routing_cfg: dict[str, Any] = {
        "auto_static": True,
        "auto_static_out_interface": True,
        "ospf": False,
    }
    dhcp_cfg: dict[str, Any] = {
        "enabled": False,
        "dns_enabled": False,
        "dns_server": "8.8.8.8",
    }
    output_cfg: dict[str, Any] = {
        "commands": "packet_tracer_commands.txt",
        "answers": "answers.csv",
        "banner": "Unauthorized access is strictly prohibited.",
    }

    switches_by_name: dict[str, dict[str, Any]] = {}
    pending_vlans: dict[str, list[dict[str, Any]]] = {}

    errors: list[str] = []
    base_ip: str | None = None

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_fields = [field for field in CSV_FIELDS if field not in (reader.fieldnames or [])]
        if missing_fields:
            missing = ", ".join(missing_fields)
            raise ValueError(f"CSV is missing required columns: {missing}")

        for line_no, raw_row in enumerate(reader, start=2):
            row = {key: (value or "").strip() for key, value in raw_row.items()}
            if not any(row.values()):
                continue

            row_type = row.get("type", "").strip().lower()
            if not row_type:
                continue

            if row_type == "base":
                if row.get("base_ip"):
                    base_ip = row["base_ip"]
                else:
                    errors.append(f"Line {line_no}: base row requires base_ip")
                continue

            if row_type == "router":
                name = row.get("name", "")
                if not name:
                    errors.append(f"Line {line_no}: router row requires name")
                    continue
                fast = _parse_int(row.get("fast"), "fast", line_no, errors, default=0)
                gigabit = _parse_int(row.get("gigabit"), "gigabit", line_no, errors, default=0)
                serial = _parse_int(row.get("serial"), "serial", line_no, errors, default=0)
                is_isp = _parse_bool(row.get("is_isp"), "is_isp", line_no, errors)
                router_cfg = {
                    "name": name,
                    "interfaces": {
                        "fast": fast if fast is not None else 0,
                        "gigabit": gigabit if gigabit is not None else 0,
                        "serial": serial if serial is not None else 0,
                    },
                }
                if is_isp:
                    router_cfg["is_isp"] = True
                config["routers"].append(router_cfg)
                continue

            if row_type == "switch":
                name = row.get("name", "")
                if not name:
                    errors.append(f"Line {line_no}: switch row requires name")
                    continue
                switch_cfg: dict[str, Any] = {"name": name, "vlans": []}

                skip_vlan_1 = _parse_bool(row.get("skip_vlan_1"), "skip_vlan_1", line_no, errors)
                if skip_vlan_1 is not None:
                    switch_cfg["skip_vlan_1"] = skip_vlan_1

                trunk_ports = _split_list(row.get("trunk_ports"))
                if trunk_ports:
                    switch_cfg["trunk_ports"] = trunk_ports

                access_ranges = _parse_access_ranges(row.get("access_ranges"), line_no, errors)
                if access_ranges:
                    switch_cfg["access_ranges"] = access_ranges

                mgmt_fields = [row.get("mgmt_vlan"), row.get("mgmt_ip"), row.get("mgmt_mask"), row.get("mgmt_gw")]
                if any(field for field in mgmt_fields):
                    mgmt_vlan = _parse_int(row.get("mgmt_vlan"), "mgmt_vlan", line_no, errors)
                    mgmt_ip = row.get("mgmt_ip") or ""
                    mgmt_mask = row.get("mgmt_mask") or ""
                    mgmt_gw = row.get("mgmt_gw") or ""
                    if mgmt_vlan is None or not mgmt_ip or not mgmt_mask:
                        errors.append(
                            f"Line {line_no}: management requires mgmt_vlan, mgmt_ip, mgmt_mask"
                        )
                    else:
                        switch_cfg["management"] = {
                            "vlan": mgmt_vlan,
                            "ip": mgmt_ip,
                            "mask": mgmt_mask,
                            "default_gateway": mgmt_gw,
                        }

                config["switches"].append(switch_cfg)
                switches_by_name[name] = switch_cfg

                if name in pending_vlans:
                    switch_cfg["vlans"].extend(pending_vlans.pop(name))
                continue

            if row_type == "vlan":
                switch_name = row.get("switch", "")
                vlan_id = _parse_int(row.get("vlan_id"), "vlan_id", line_no, errors)
                vlan_hosts = _parse_int(row.get("hosts"), "hosts", line_no, errors)
                vlan_name = row.get("vlan_name") or row.get("name") or ""

                if not switch_name:
                    errors.append(f"Line {line_no}: vlan row requires switch")
                    continue
                if vlan_id is None:
                    errors.append(f"Line {line_no}: vlan row requires vlan_id")
                    continue
                if vlan_hosts is None:
                    errors.append(f"Line {line_no}: vlan row requires hosts")
                    continue

                vlan_cfg = {"id": vlan_id, "hosts": vlan_hosts, "name": vlan_name or f"VLAN{vlan_id}"}

                if switch_name in switches_by_name:
                    switches_by_name[switch_name]["vlans"].append(vlan_cfg)
                else:
                    pending_vlans.setdefault(switch_name, []).append(vlan_cfg)
                continue

            if row_type == "subnet":
                subnet_router = row.get("router", "")
                subnet_hosts = row.get("hosts", "")
                subnet_port = row.get("port", "")
                subnet_name = row.get("name", "")
                subnet_port_type = row.get("port_type", "")

                if not any([subnet_router, subnet_hosts, subnet_port, subnet_name, subnet_port_type]):
                    continue
                if not subnet_router or not subnet_hosts or not subnet_port:
                    errors.append(
                        f"Line {line_no}: subnet row requires router, hosts, and port when provided"
                    )
                    continue
                subnet_hosts_int = _parse_int(subnet_hosts, "hosts", line_no, errors)
                if subnet_hosts_int is None:
                    continue

                subnet_cfg = {
                    "router": subnet_router,
                    "hosts": subnet_hosts_int,
                    "name": subnet_name,
                    "port": subnet_port,
                }
                if subnet_port_type:
                    subnet_cfg["port_type"] = subnet_port_type
                config["subnets"].append(subnet_cfg)
                continue

            if row_type == "link":
                link_type = row.get("link_type", "")
                if not link_type and not any([row.get("a"), row.get("b"), row.get("router"), row.get("switch")]):
                    continue
                if not link_type:
                    errors.append(f"Line {line_no}: link row requires link_type when provided")
                    continue

                link_type = link_type.lower()
                if link_type not in {"serial", "trunk", "switch"}:
                    errors.append(f"Line {line_no}: link_type must be serial, trunk, or switch")
                    continue

                link_cfg: dict[str, Any] = {"type": link_type}
                if link_type == "serial":
                    link_cfg.update(
                        {
                            "a": row.get("a", ""),
                            "a_port": row.get("a_port", ""),
                            "b": row.get("b", ""),
                            "b_port": row.get("b_port", ""),
                        }
                    )
                    if not link_cfg["a"] or not link_cfg["b"]:
                        errors.append(f"Line {line_no}: serial link requires a and b")
                        continue
                    if row.get("network_ip"):
                        link_cfg["network_ip"] = row.get("network_ip")
                elif link_type == "trunk":
                    link_cfg.update(
                        {
                            "router": row.get("router", ""),
                            "router_port": row.get("router_port", ""),
                            "switch": row.get("switch", ""),
                            "switch_port": row.get("switch_port", ""),
                        }
                    )
                    if not link_cfg["router"] or not link_cfg["switch"]:
                        errors.append(f"Line {line_no}: trunk link requires router and switch")
                        continue
                else:
                    link_cfg.update(
                        {
                            "a": row.get("a", ""),
                            "a_port": row.get("a_port", ""),
                            "b": row.get("b", ""),
                            "b_port": row.get("b_port", ""),
                        }
                    )
                    if not link_cfg["a"] or not link_cfg["b"]:
                        errors.append(f"Line {line_no}: switch link requires a and b")
                        continue

                config["links"].append({k: v for k, v in link_cfg.items() if v != ""})
                continue

            if row_type == "routing":
                auto_static = _parse_bool(row.get("auto_static"), "auto_static", line_no, errors)
                auto_static_out = _parse_bool(
                    row.get("auto_static_out_interface"),
                    "auto_static_out_interface",
                    line_no,
                    errors,
                )
                ospf = _parse_bool(row.get("ospf"), "ospf", line_no, errors)
                if auto_static is not None:
                    routing_cfg["auto_static"] = auto_static
                if auto_static_out is not None:
                    routing_cfg["auto_static_out_interface"] = auto_static_out
                if ospf is not None:
                    routing_cfg["ospf"] = ospf
                continue

            if row_type == "dhcp":
                enabled = _parse_bool(row.get("dhcp_enabled"), "dhcp_enabled", line_no, errors)
                dns_enabled = _parse_bool(row.get("dns_enabled"), "dns_enabled", line_no, errors)
                dns_server = row.get("dns_server") or ""
                if enabled is not None:
                    dhcp_cfg["enabled"] = enabled
                if dns_enabled is not None:
                    dhcp_cfg["dns_enabled"] = dns_enabled
                if dns_server:
                    dhcp_cfg["dns_server"] = dns_server
                continue

            if row_type == "output":
                if row.get("commands"):
                    output_cfg["commands"] = row.get("commands")
                if row.get("answers"):
                    output_cfg["answers"] = row.get("answers")
                if row.get("banner"):
                    output_cfg["banner"] = row.get("banner")
                continue

            errors.append(f"Line {line_no}: unknown type '{row_type}'")

    if pending_vlans:
        for switch_name in pending_vlans:
            errors.append(f"Missing switch definition for VLANs on {switch_name}")

    if base_ip:
        config["base_ip"] = base_ip
    else:
        errors.append("Missing base_ip in CSV")

    config["routing"] = routing_cfg
    config["dhcp"] = dhcp_cfg
    config["output"] = output_cfg

    if errors:
        raise ValueError("CSV validation errors:\n" + "\n".join(errors))

    return config
