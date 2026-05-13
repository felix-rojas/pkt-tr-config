import ipaddress
import math
import pandas as pd
from router import Router


def get_critical_bit(prefix_length: int) -> int:
    remainder = prefix_length % 8
    return 1 if remainder == 0 else 2 ** (8 - remainder)


def extract_requirements(routers: list[Router], link_overrides: set | None = None) -> list[dict]:
    """
    Returns a list of dicts with keys "name" and "hosts" 
    representing the subnet requirements for each router's interfaces and links.
    Automatically generates links between routers based on serial connections.
    """
    requirements = []
    seen_links = set()
    link_overrides = link_overrides or set()

    for r in routers:
        for port, data in r.fast_interfaces.items():
            # greater than 0 check ensures we skip physical trunk links
            if data and data['hosts'] > 0:
                subnet_label = data['name'] if data['name'] else port
                requirements.append({
                    "name": f"{r.router_name}_{subnet_label}",
                    "hosts": data['hosts']
                })

        for port, data in r.gigabyte_interfaces.items():
            # greater than 0 check ensures we skip physical trunk links
            if data and data['hosts'] > 0:
                subnet_label = data['name'] if data['name'] else port
                requirements.append({
                    "name": f"{r.router_name}_{subnet_label}",
                    "hosts": data['hosts']
                })

        for port, remote_name in r.serial_interfaces.items():
            if remote_name:
                link = frozenset([r.router_name, remote_name])
                if link not in seen_links and link not in link_overrides:
                    # double zz to ensure link subnets are sorted after regular subnets
                    requirements.append({
                        "name": f"zzLink_{r.router_name}_{remote_name}",
                        "hosts": 2
                    })
                    seen_links.add(link)

    return requirements


def calculate_vlsm_from_routers(base_ip_str, routers: list[Router], link_overrides: dict | None = None) -> pd.DataFrame:
    link_overrides = link_overrides or {}
    subnets = extract_requirements(routers, set(link_overrides.keys()))

    if "/" not in base_ip_str:
        # find the smallest prefix that can accommodate all subnets
        total_needed = sum(
            2 ** math.ceil(math.log2(s['hosts'] + 2)) for s in subnets)
        prefix = 32 - math.ceil(math.log2(total_needed)
                                ) if total_needed > 0 else 32
        base_ip_str = f"{base_ip_str}/{prefix}"

    # too lazy to implement ipaddress handling from scratch
    root_network = ipaddress.IPv4Network(base_ip_str, strict=False)
    # sort by number of hosts, largest to smallest
    sorted_reqs = sorted(subnets, key=lambda x: x['hosts'], reverse=True)
    current_pointer = root_network.network_address
    data_rows = []

    for req in sorted_reqs:
        host_bits = math.ceil(math.log2(req['hosts'] + 2))
        prefix_len = 32 - host_bits

        try:
            subnet = ipaddress.IPv4Network((current_pointer, prefix_len))
            data_rows.append({
                "Subnet Name": req['name'],
                "Potential IPs": subnet.num_addresses-2,
                "Total IPs": req['hosts'] + 1 if "zzLink_" not in req['name'] else req['hosts'],
                "Host Bits": host_bits,
                "Net Suffix": prefix_len,
                "Critical Bit": get_critical_bit(prefix_len),
                "Subnet Mask": str(subnet.netmask),
                "Network ID": str(subnet.network_address),
                "First Valid IP": str(subnet.network_address + 1),
                "Last Valid IP": str(subnet.broadcast_address - 1),
                "Broadcast IP": str(subnet.broadcast_address)
            })
            current_pointer = subnet.broadcast_address + 1
        except ValueError:
            data_rows.append(
                {"Subnet Name": req['name'], "Status": "Error: Insufficient Space"})

    for link, network_str in link_overrides.items():
        if not network_str:
            continue
        if "/" in network_str:
            network = ipaddress.IPv4Network(network_str, strict=False)
        else:
            network = ipaddress.IPv4Network(f"{network_str}/30", strict=False)

        if len(link) != 2:
            continue
        router_a, router_b = sorted(link)
        link_name = f"zzLink_{router_a}_{router_b}"
        prefix_len = network.prefixlen
        host_bits = 32 - prefix_len
        data_rows.append({
            "Subnet Name": link_name,
            "Potential IPs": network.num_addresses - 2,
            "Total IPs": 2,
            "Host Bits": host_bits,
            "Net Suffix": prefix_len,
            "Critical Bit": get_critical_bit(prefix_len),
            "Subnet Mask": str(network.netmask),
            "Network ID": str(network.network_address),
            "First Valid IP": str(network.network_address + 1),
            "Last Valid IP": str(network.broadcast_address - 1),
            "Broadcast IP": str(network.broadcast_address)
        })

    return pd.DataFrame(data_rows)
