"""Execute existing repository contracts, inside the verified test process."""
from scripts.verify_db_guard import require_isolated_test_runtime
require_isolated_test_runtime()


def test_ai_tool_registry_compliance():
    from scripts.verify_ai_tool_compliance import main
    assert main() == 0


def test_existing_tool_schema_suite_covers_every_registered_capability():
    from scripts.verify_ai_tool_schemas import main
    assert main() == 0


def test_registered_media_capabilities_and_existing_script_expectations():
    import ast
    from pathlib import Path
    from ai.policies import AI_CAPABILITY_ROLES, AI_CAPABILITY_BUSINESS_ENDPOINTS
    from ai.tools.registry import AI_TOOL_REGISTRY
    tree = ast.parse((Path(__file__).resolve().parents[1] /
                      'scripts/verify_ai_permission_matrix.py').read_text(encoding='utf-8-sig'))
    expected = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == 'EXPECTED' for target in node.targets))
    for capability, roles in {
        'material_recognition': {'admin', 'warehouse', 'purchase', 'sales', 'production'},
        'audio_transcription': {'admin', 'warehouse', 'purchase', 'sales', 'production'},
        'document_retry': {'admin', 'warehouse', 'purchase', 'sales', 'production'},
        'document_recognition': {'admin', 'warehouse', 'purchase'},
    }.items():
        assert set(AI_CAPABILITY_ROLES[capability]) | {'admin'} == roles
        assert expected[capability] == roles
        spec = AI_TOOL_REGISTRY[capability]
        assert spec.risk_level == 'read' and spec.handler_name is None and not spec.idempotent
        assert AI_CAPABILITY_BUSINESS_ENDPOINTS[capability]
