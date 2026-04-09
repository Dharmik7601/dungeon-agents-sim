# Dungeon Agents: Diagnostic Trace Schema & Logging Plan

## 1. Global Event Schema (JSON)
This is the normalized structure for every agent step. The keys within `state_context` are strictly standardized to eliminate the need for parsing heuristics in the UI.

```json
{
  "event_id": "string",
  "timestamp": "ISO 8601 string",
  "turn_number": "integer",
  "agent_id": "string",
  "action": {
    "tool_name": "string (move, look, pick_up, check_coordinates, check_inventory, use_item, send_message)",
    "arguments": "object",
    "spatial_context": {
      "agent_position": "[x, y]",
      "target_position": "[x, y] | null"
    }
  },
  "state_context": {
    "agent_beliefs": {
      "reasoning": "string",
      "expected_state": {
        "cell_status_[x]_[y]": "string | null",
        "cell_contents_[x]_[y]": "array | null",
        "agent_inventory": "array | null",
        "partner_position": "[x, y] | null"
      }
    },
    "shadow_state": {
      "cell_status_[x]_[y]": "string | null",
      "cell_contents_[x]_[y]": "array | null",
      "agent_inventory": "array | null",
      "partner_position": "[x, y] | null"
    },
    "ground_truth": {
      "cell_status_[x]_[y]": "string | null",
      "cell_contents_[x]_[y]": "array | null",
      "agent_inventory": "array | null",
      "partner_position": "[x, y] | null"
    }
  },
  "execution_result": {
    "status": "success | failure",
    "error_message": "string | null",
    "deltas": [
      {
        "property_key": "string",
        "expected_value": "any",
        "actual_value": "any",
        "discrepancy_source": "string"
      }
    ]
  }
}