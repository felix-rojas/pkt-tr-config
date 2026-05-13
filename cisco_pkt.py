from typing import Optional

import pandas as pd
from router import Router, Switch
from pkt_tr_router_config import generate_router_commands
from pkt_tr_switch_config import generate_switch_commands
from config_builder import build_topology, get_output_paths, load_config


def compute_auto_static_routes(routers: list[Router], vlsm_df: pd.DataFrame, use_out_interface: bool = False) -> dict:
    """Compute static routes for routers based on direct serial adjacency.

    Returns a dict mapping router_name -> list of routes with keys: dest, mask, next_hop
    Only generates routes for subnets not owned by the router and that are reachable
    via a direct serial link to the owning router.
    """
    result = {r.router_name: [] for r in routers}

    # Build quick lookup for router objects by name
    routers_by_name = {r.router_name: r for r in routers}

    for r in routers:
        for _, row in vlsm_df.iterrows():
            subnet_name = str(row.get('Subnet Name', ''))
            if not subnet_name or subnet_name.startswith('zzLink_'):
                continue
            owner = subnet_name.split('_')[0]
            if owner == r.router_name:
                continue

            # check for direct serial adjacency
            if owner in r.serial_interfaces.values():
                # find the link subnet row
                link_name_1 = f"zzLink_{r.router_name}_{owner}"
                link_name_2 = f"zzLink_{owner}_{r.router_name}"
                link_row = vlsm_df[(vlsm_df['Subnet Name'] == link_name_1) | (vlsm_df['Subnet Name'] == link_name_2)]
                if link_row.empty:
                    continue
                link = link_row.iloc[0]
                link_name = link['Subnet Name']
                parts = link_name.split("_")
                router_a = parts[1]

                if r.router_name == router_a:
                    neighbor_ip = link['Last Valid IP']
                else:
                    neighbor_ip = link['First Valid IP']

                route = {
                    'dest': row['Network ID'],
                    'mask': row['Subnet Mask']
                }
                if use_out_interface:
                    for port, remote in r.serial_interfaces.items():
                        if remote == owner:
                            route['out_interface'] = port
                            break
                else:
                    route['next_hop'] = neighbor_ip
                result[r.router_name].append(route)

    return result


def generate_cisco_ios_commands(routers: list[Router],
                                vlsm_df: pd.DataFrame,  # dataframe containing VLSM calculations
                                switches: Optional[list[Switch]] = None,
                                output_file: str = "packet_tracer_commands.txt",
                                banner_text: str | None = None):
    with open(output_file, 'w') as f:
        for idx, r in enumerate(routers):
            f.write(generate_router_commands(r, vlsm_df, banner_text=banner_text))
            if idx != len(routers) - 1 or switches:
                f.write("\n--------------------------------------------------------------------------------\n\n")

        if switches:
            for idx, s in enumerate(switches):
                f.write(generate_switch_commands(s, banner_text=banner_text))
                if idx != len(switches) - 1:
                    f.write("\n--------------------------------------------------------------------------------\n\n")

    print(f"Packet Tracer text commands successfully generated: {output_file}")


def generate_from_config(config_source):
    """Build topology from a declarative config and generate outputs."""
    config = load_config(config_source)
    routers, switches, vlsm_df = build_topology(config)
    commands_path, answers_path = get_output_paths(config)
    output_cfg = config.get("output", {})
    banner_text = output_cfg.get("banner")

    vlsm_df.to_csv(answers_path, index=False)
    generate_cisco_ios_commands(
        routers,
        vlsm_df,
        switches=switches,
        output_file=commands_path,
        banner_text=banner_text,
    )
