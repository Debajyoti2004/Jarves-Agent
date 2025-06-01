
from typing import Dict,List,Any

def group_actions_by_contact(actions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped_actions: Dict[str, List[Dict[str, Any]]] = {}
    for action in actions:
        contact_name = action.get("contact_name")
        if contact_name:
            if contact_name not in grouped_actions:
                grouped_actions[contact_name] = []
            grouped_actions[contact_name].append(action)
        else:
            print(f"Warning: Action missing 'contact_name': {action}")
    return grouped_actions