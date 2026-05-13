import csv
import sys
import json
import ipaddress
from config_builder import build_topology
from cisco_pkt import generate_from_config

def parse_minimal_csv(filepath):
    """
    Parses a minimal, parameter-based CSV format.
    Format: Entity, Name/ID, Param1=Value1, Param2=Value2, ...
    """
    config = {
        "base_ip": "192.168.1.0",
        "routers": [],
        "switches": [],
        "subnets": [],
        "links": [],
        "routing": {"auto_static": True, "auto_static_out_interface": True, "ospf": False},
        "dhcp": {"enabled": False, "dns_enabled": False, "dns_server": "8.8.8.8"},
        "output": {
            "commands": "packet_tracer_commands.txt",
            "answers": "subnetting.csv",
            "banner": "Unauthorized access is strictly prohibited."
        }
    }

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row_idx, row in enumerate(reader):
            if not row or not row[0].strip() or row[0].strip().startswith('#'):
                continue
            
            entity = row[0].strip().lower()
            name = row[1].strip() if len(row) > 1 else ""
            
            # Extract key=value parameters from the remaining columns.
            # We reconstruct items that might have been accidentally split by commas 
            # (like a Banner containing commas but no quotes).
            params = {}
            current_key = None
            for item in row[2:]:
                item = item.strip()
                if not item:
                    continue
                if '=' in item:
                    k, v = item.split('=', 1)
                    current_key = k.strip().lower()
                    params[current_key] = v.strip()
                elif current_key:
                    # If there's no '=', append it to the previous key's value
                    # This gracefully handles unquoted commas in things like Banners
                    params[current_key] += f", {item}"

            if entity == 'global':
                if 'baseip' in params: config['base_ip'] = params['baseip']
                if 'autostatic' in params: config['routing']['auto_static'] = params['autostatic'].lower() == 'true'
                if 'ospf' in params: config['routing']['ospf'] = params['ospf'].lower() == 'true'
                if 'dhcpenabled' in params: config['dhcp']['enabled'] = params['dhcpenabled'].lower() == 'true'
                if 'dnsenabled' in params: config['dhcp']['dns_enabled'] = params['dnsenabled'].lower() == 'true'
                if 'dnsserver' in params: config['dhcp']['dns_server'] = params['dnsserver']
                
                # --- Output Overrides ---
                if 'commands' in params: config['output']['commands'] = params['commands']
                if 'answers' in params: config['output']['answers'] = params['answers']
                if 'banner' in params: config['output']['banner'] = params['banner']

            elif entity == 'router':
                router_cfg = {
                    "name": name,
                    "interfaces": {
                        "fast": int(params.get('fast', 0)),
                        "gigabit": int(params.get('gigabit', 0)),
                        "serial": int(params.get('serial', 0))
                    }
                }
                if params.get('isisp', '').lower() == 'true':
                    router_cfg['is_isp'] = True
                
                # Handling custom static routes if defined in params (e.g., StaticRoute=0.0.0.0/0.0.0.0/Serial0/0/0)
                if 'staticroute' in params:
                    # Limiting split to 2 ensures interface names like Serial0/0/0 stay intact
                    dest, mask, out_if = params['staticroute'].split('/', 2)
                    router_cfg['static_routes'] = [{"dest": dest, "mask": mask, "out_interface": out_if}]
                
                config['routers'].append(router_cfg)

            elif entity == 'switch':
                switch_cfg = {
                    "name": name,
                    "vlans": [],
                    "_mgmt_vlan": int(params['mgmtvlan']) if 'mgmtvlan' in params else None
                }
                if params.get('skipvlan1', '').lower() == 'true':
                    switch_cfg['skip_vlan_1'] = True
                if 'trunkports' in params:
                    switch_cfg['trunk_ports'] = [p.strip() for p in params['trunkports'].split(';')]
                if 'accessranges' in params:
                    ranges = []
                    for r in params['accessranges'].split(';'):
                        vlan_id, port_range = r.split(':')
                        ranges.append({"vlan_id": int(vlan_id), "range": port_range})
                    switch_cfg['access_ranges'] = ranges
                
                config['switches'].append(switch_cfg)

            elif entity == 'vlan':
                # For VLANs, the 'name' column is the Switch name
                switch_name = name
                vlan_id = int(row[2].strip())
                vlan_name = row[3].strip()
                hosts = int(row[4].strip())
                
                sw_cfg = next((s for s in config['switches'] if s['name'] == switch_name), None)
                if sw_cfg is not None:
                    sw_cfg['vlans'].append({"id": vlan_id, "hosts": hosts, "name": vlan_name})
            
            elif entity == 'subnet':
                # Subnets handle standalone routed networks (not tied to a switch VLAN)
                config['subnets'].append({
                    "router": name,
                    "hosts": int(params['hosts']),
                    "port": params.get('port'),
                    "name": params.get('name', '')
                })

            elif entity == 'link':
                link_type = name.lower()
                if link_type == 'serial':
                    link_cfg = {
                        "type": "serial",
                        "a": row[2].strip(), "a_port": row[3].strip(),
                        "b": row[4].strip(), "b_port": row[5].strip()
                    }
                    if 'network' in params: link_cfg['network_ip'] = params['network']
                    config['links'].append(link_cfg)
                
                elif link_type == 'trunk':
                    config['links'].append({
                        "type": "trunk",
                        "router": row[2].strip(), "router_port": row[3].strip(),
                        "switch": row[4].strip(), "switch_port": row[5].strip()
                    })
                
                elif link_type == 'switch':
                    config['links'].append({
                        "type": "switch",
                        "a": row[2].strip(), "a_port": row[3].strip(),
                        "b": row[4].strip(), "b_port": row[5].strip()
                    })

    return config

def auto_assign_ips(config):
    """
    Runs a preliminary VLSM calculation to determine the subnets, 
    then sequentially assigns switch management IPs to prevent conflicts.
    """
    # Generate the topology and VLSM DataFrame in memory
    routers, switches, vlsm_df = build_topology(config)
    
    # 1. Map VLAN IDs to their calculated VLSM Subnet Rows based on Trunk links
    vlan_to_subnet = {}
    for link in config.get('links', []):
        if link['type'] == 'trunk':
            router_name = link['router']
            sw_name = link['switch']
            sw_cfg = next((s for s in config['switches'] if s['name'] == sw_name), None)
            if sw_cfg:
                for vlan in sw_cfg['vlans']:
                    # Include the router name to match vlsm.py output format
                    subnet_name = f"{router_name}_{sw_name}_{vlan['name']}"
                    row_match = vlsm_df[vlsm_df['Subnet Name'] == subnet_name]
                    if not row_match.empty:
                        vlan_to_subnet[vlan['id']] = row_match.iloc[0]

    # 2. Hash map to track IP assignments within each subnet to guarantee O(1) tracking
    ip_tracker = {}

    # 3. Assign IPs to switches
    for sw in config['switches']:
        mgmt_vlan = sw.pop('_mgmt_vlan', None)
        if not mgmt_vlan:
            continue
            
        subnet_row = vlan_to_subnet.get(mgmt_vlan)
        if subnet_row is None:
            print(f"Warning: Could not find routed subnet for VLAN {mgmt_vlan} on Switch {sw['name']}.")
            continue

        subnet_name = subnet_row['Subnet Name']
        
        # Initialize the tracker for this subnet if it hasn't been used yet.
        # Router sub-interfaces use the Last Valid IP as the default gateway.
        # Therefore, we start assigning switches sequentially from the First Valid IP.
        if subnet_name not in ip_tracker:
            first_valid = ipaddress.IPv4Address(subnet_row['First Valid IP'])
            ip_tracker[subnet_name] = int(first_valid)

        # Allocate the next available IP
        allocated_ip = ipaddress.IPv4Address(ip_tracker[subnet_name])
        ip_tracker[subnet_name] += 1 # Increment for the next switch on this VLAN
        
        sw['management'] = {
            "vlan": mgmt_vlan,
            "ip": str(allocated_ip),
            "mask": subnet_row['Subnet Mask'],
            "default_gateway": subnet_row['Last Valid IP']
        }

    return config

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <topology.csv>")
        sys.exit(1)
        
    csv_file = sys.argv[1]
    
    print(f"Reading minimal layout from {csv_file}...")
    raw_config = parse_minimal_csv(csv_file)
    
    print("Calculating VLSM and auto-assigning Switch Management IPs...")
    final_config = auto_assign_ips(raw_config)
    
    json_out = csv_file.replace('.csv', '.json')
    with open(json_out, 'w', encoding='utf-8') as f:
        json.dump(final_config, f, indent=4)
    print(f"Intermediate JSON configuration saved to {json_out}")
    
    print("Generating Packet Tracer output files...")
    generate_from_config(final_config)
    print("Process complete.")

if __name__ == "__main__":
    main()