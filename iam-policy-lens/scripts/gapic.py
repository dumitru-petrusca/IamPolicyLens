from dataclasses import dataclass

@dataclass
class GapicCall:
    fullname: str
    file_path: str
    line: int
    source_line: str
    resolution: str

def clean_gapic_fullname(name: str) -> str:
    """Removes internal package structures like .services.[...].client."""
    import re
    name = re.sub(r'\.services\.[a-zA-Z0-9_]+\.client\.', '.', name)
    name = re.sub(r'\.client\.Client', '.Client', name)
    return name
