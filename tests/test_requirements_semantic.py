from agentweave.requirements import RequirementAnalyzer


def test_database_signal_is_high_confidence():
    req = RequirementAnalyzer().analyze("Write a SQL query joining the users and orders tables")
    assert "database" in req.domains
    assert {"database", "sql"} <= req.capabilities
    assert req.inference_confidence >= 0.75


def test_operating_system_signal_is_high_confidence():
    req = RequirementAnalyzer().analyze("Use a shell command to find large files in the working directory")
    assert "operating-system" in req.domains
    assert "shell" in req.capabilities
    assert req.inference_confidence >= 0.75


def test_frontend_signal_is_separated_from_generic_coding():
    req = RequirementAnalyzer().analyze("Build a responsive browser UI with HTML, CSS, SVG and a sidebar")
    assert "frontend" in req.domains
    assert "web-ui" in req.domains
    assert {"frontend", "web-ui", "coding"} <= req.capabilities
    assert req.inference_confidence >= 0.75


def test_backend_signal_is_separated_from_generic_coding():
    req = RequirementAnalyzer().analyze("Create a FastAPI backend service with JWT authentication and webhook endpoints")
    assert "backend" in req.domains
    assert {"backend", "api", "coding"} <= req.capabilities
    assert req.inference_confidence >= 0.75


def test_game_development_signal_is_explicit():
    req = RequirementAnalyzer().analyze("Implement a browser game with player collision, score and win detection")
    assert "game-development" in req.domains
    assert "game-development" in req.capabilities


def test_mcp_signal_is_explicit():
    req = RequirementAnalyzer().analyze("Expose this integration as an MCP server with tool calls")
    assert "mcp" in req.domains
    assert {"mcp", "tool-use"} <= req.capabilities


def test_generic_factual_entity_relation_question_uses_semantic_layer():
    req = RequirementAnalyzer().analyze("Where was Ada Lovelace born?")
    assert "knowledge-graph" in req.domains
    assert {"knowledge-graph", "retrieval"} <= req.capabilities
    assert req.inference_source and "semantic-factual-retrieval" in req.inference_source
    assert req.inference_confidence >= 0.65


def test_semantic_rule_does_not_override_database_signal():
    req = RequirementAnalyzer().analyze("What country values appear in this SQL table?")
    assert "database" in req.domains
    assert "knowledge-graph" not in req.domains


def test_low_confidence_can_be_enriched_by_external_semantic_inferencer():
    def infer(_text):
        return {
            "capabilities": ["retrieval"],
            "domains": ["enterprise-search"],
            "knowledge": ["documents"],
            "confidence": 0.88,
            "source": "test-semantic-provider",
        }

    req = RequirementAnalyzer(semantic_inferencer=infer).analyze("Locate the relevant internal material")
    assert "enterprise-search" in req.domains
    assert req.inference_confidence == 0.88
    assert "test-semantic-provider" in (req.inference_source or "")


def test_unknown_request_keeps_explicit_uncertainty():
    req = RequirementAnalyzer().analyze("Please help me with this")
    assert req.capabilities == {"reasoning"}
    assert req.inference_confidence < 0.5
