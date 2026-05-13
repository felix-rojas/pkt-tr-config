# pkt-tr-config
Creates Packet Tracer base config and calculates VLSM.

## Configuration wizard
Run the interactive wizard to create a config JSON and optionally generate outputs:

```
python3 wizard.py
```

## CSV template wizard
Create a CSV template by providing counts. Fill in the missing values, then generate outputs:

```
python3 csv_wizard.py
```

Generate outputs from a filled CSV:

```
python3 csv_generate.py config.csv
```

## Declarative config API
Use a dict (or JSON/YAML file) to describe the topology, then generate outputs.

```python
from cisco_pkt import generate_from_config

config = {
	"base_ip": "192.168.1.0",
	"routers": [
		{"name": "R1", "interfaces": {"fast": 0, "gigabit": 1, "serial": 1}},
		{"name": "R2", "interfaces": {"fast": 0, "gigabit": 1, "serial": 1}},
	],
	"switches": [
		{
			"name": "SW1",
			"vlans": [
				{"id": 10, "hosts": 50, "name": "Users"},
				{"id": 20, "hosts": 10, "name": "Mgmt"},
			],
		}
	],
	"subnets": [
		{"router": "R2", "hosts": 24, "name": "LAN", "port": "GigabitEthernet0/0/0"},
	],
	"links": [
		{"type": "serial", "a": "R1", "a_port": "Serial0/0/0", "b": "R2", "b_port": "Serial0/0/0", "network_ip": "65.255.255.252/30"},
		{"type": "trunk", "router": "R1", "router_port": "GigabitEthernet0/0/0", "switch": "SW1"},
	],
	"routing": {"auto_static": True, "ospf": True},
	"dhcp": {"enabled": True, "dns_enabled": True, "dns_server": "8.8.8.8"},
	"output": {"commands": "packet_tracer_commands.txt", "answers": "answers.csv", "banner": "Unauthorized access is strictly prohibited."},
}

generate_from_config(config)
```

### Interface naming
All interfaces are normalized to full names (e.g., `GigabitEthernet0/0/0`). Aliases like `Gi0/0/0`, `Fa0/1`, and `S0/0/0` are accepted as input and normalized.

### YAML configs
You can pass a YAML path to `generate_from_config("config.yaml")`. Install PyYAML if needed:
```
pip install pyyaml
```

### CSV configs
You can pass a CSV path to `generate_from_config("config.csv")`. The CSV uses a single file with a `type`
column. Blank `link` and `subnet` rows are ignored until filled.

### ISP serial link network
For a serial link involving the ISP router, you can set `links[].network_ip` to force the /30 network for that link. If omitted, the link subnet is allocated from the base IP space.
