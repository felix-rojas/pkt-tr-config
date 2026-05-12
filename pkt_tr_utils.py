def get_wildcard_mask(subnet_mask_str: str) -> str:
    """Converts a subnet mask (e.g., 255.255.255.0) to a wildcard mask (0.0.0.255)"""
    parts = subnet_mask_str.split('.')
    return '.'.join(str(255 - int(p)) for p in parts)