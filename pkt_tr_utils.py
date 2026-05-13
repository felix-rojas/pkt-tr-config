import re

INTERFACE_ALIASES = {
    "FastEthernet": ["F", "Fa", "FastEthernet"],
    "GigabitEthernet": ["G", "Gi", "GigabitEthernet"],
    "Serial": ["S", "Se", "Serial"],
}


def get_wildcard_mask(subnet_mask_str: str) -> str:
    """Converts a subnet mask (e.g., 255.255.255.0) to a wildcard mask (0.0.0.255)."""
    parts = subnet_mask_str.split('.')
    return '.'.join(str(255 - int(p)) for p in parts)


def normalize_interface_name(port: str) -> str:
    """Normalize interface names to canonical Cisco form.

    Examples:
    - Gi0/0/0 -> GigabitEthernet0/0/0
    - Fa0/1 -> FastEthernet0/1
    - S0/0/0 -> Serial0/0/0
    """
    if port is None:
        return port
    port = str(port).strip()
    if not port:
        return port

    match = re.match(r"^([A-Za-z]+)([0-9/\.]+)$", port)
    if not match:
        return port

    prefix, suffix = match.groups()
    prefix_lower = prefix.lower()

    for canonical, aliases in INTERFACE_ALIASES.items():
        if prefix_lower == canonical.lower() or prefix_lower in [a.lower() for a in aliases]:
            return f"{canonical}{suffix}"

    return port


def abbreviate_interface_name(port: str) -> str:
    """Abbreviate canonical interface names for IOS-style output."""
    if port is None:
        return port
    normalized = normalize_interface_name(port)
    if normalized.startswith("GigabitEthernet"):
        return normalized.replace("GigabitEthernet", "g", 1)
    if normalized.startswith("FastEthernet"):
        return normalized.replace("FastEthernet", "fa", 1)
    if normalized.startswith("Serial"):
        return normalized.replace("Serial", "s", 1)
    return normalized


def render_interface_name(port: str) -> str:
    return abbreviate_interface_name(port)


def render_interface_range(range_str: str) -> str:
    if not range_str:
        return range_str
    if "-" not in range_str:
        return render_interface_name(range_str)
    left, right = range_str.split("-", 1)
    left = left.strip()
    right = right.strip()
    left_rendered = render_interface_name(left)
    return f"{left_rendered}-{right}"


def normalize_port_type(port_type: str) -> str:
    """Normalize a port type token to its canonical interface family name."""
    if port_type is None:
        return port_type
    token = str(port_type).strip()
    if not token:
        return token

    for canonical, aliases in INTERFACE_ALIASES.items():
        if token.lower() == canonical.lower() or token.lower() in [a.lower() for a in aliases]:
            return canonical

    return token


def build_interface_map(interface_family: str, count: int, base: str = "0/0") -> dict:
    """Build an interface dictionary with canonical names initialized to None."""
    if count <= 0:
        return {}
    family = normalize_port_type(interface_family)
    return {f"{family}{base}/{i}": None for i in range(count)}