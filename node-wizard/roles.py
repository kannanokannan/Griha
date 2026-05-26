"""Role matching — compare hardware capabilities against role requirements."""
import yaml
from pathlib import Path
from typing import List

def load_roles() -> dict:
    with open(Path(__file__).parent / "roles.yaml") as f:
        return yaml.safe_load(f)

def eligible_roles(hardware: dict, existing_coordinator: bool = True) -> List[dict]:
    roles = load_roles()
    eligible = []
    for role_name, role_def in roles.items():
        if role_name == "coordinator" and existing_coordinator: continue
        if not hardware["wired_active"]: continue
        if hardware["ram_gb"] < role_def.get("min_ram_gb", 0): continue
        if not _satisfies_requirements(role_def.get("requires", []), hardware["capabilities"]): continue
        eligible.append({"role": role_name, "score": _score(role_def, hardware), "note": role_def.get("note", ""), "preferred": role_def.get("preferred", [])})
    return sorted(eligible, key=lambda x: x["score"], reverse=True)

def _satisfies_requirements(required: list, capabilities: list) -> bool:
    if not required: return True
    for req in required:
        if isinstance(req, list):
            if not any(r in capabilities for r in req): return False
        else:
            if req not in capabilities: return False
    return True

def _score(role_def: dict, hardware: dict) -> int:
    return 10 + sum(5 for pref in role_def.get("preferred", []) if pref in hardware["capabilities"])
