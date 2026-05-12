import pandas as pd
from router import Router, Switch
from pkt_tr_router_config import generate_router_commands
from pkt_tr_switch_config import generate_switch_commands


def generate_cisco_ios_commands(routers: list[Router],
                                vlsm_df: pd.DataFrame,  # dataframe containing VLSM calculations
                                switches: list[Switch] = None,
                                output_file: str = "packet_tracer_commands.txt"):
    with open(output_file, 'w') as f:
        for r in routers:
            f.write(generate_router_commands(r, vlsm_df))

        if switches:
            for s in switches:
                f.write(generate_switch_commands(s))

    print(f"Packet Tracer text commands successfully generated: {output_file}")
