from agent_01_boq_extractor import Agent01_BOQExtractor
from agent_03_input_auditor import Agent03_InputAuditor

# Backward-compatible aliases (Đã chuẩn hóa sang Agent 01 & Agent 03)
Agent0A_UniversalExtractor = Agent01_BOQExtractor
Agent0B_InputAuditor = Agent03_InputAuditor

__all__ = [
    "Agent01_BOQExtractor",
    "Agent03_InputAuditor",
    "Agent0A_UniversalExtractor",
    "Agent0B_InputAuditor"
]
