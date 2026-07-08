from auto_refactor import AutoRefactor

def test_auto_refactor_init():
    """Test that AutoRefactor initializes with default values."""
    refactor = AutoRefactor()
    assert refactor.orc is None
    assert refactor._log == []

def test_auto_refactor_init_with_orchestrator():
    """Test that AutoRefactor initializes with orchestrator."""
    mock_orc = object()
    refactor = AutoRefactor(orchestrator=mock_orc)
    assert refactor.orc is mock_orc
    assert refactor._log == []

def test_log_returns_copy():
    """Test that log() returns a copy of the internal list."""
    refactor = AutoRefactor()
    log = refactor.log()
    assert log == []
    # Modify the returned list to verify it's a copy
    log.append("test")
    assert refactor._log == []
    assert refactor.log() == []

def test_refactor_file_file_not_found():
    """Test refactor_file returns error for non-existent file."""
    refactor = AutoRefactor()
    import asyncio
    result = asyncio.run(refactor.refactor_file("/nonexistent/file.py"))
    assert result == {"status": "error", "error": "File not found"}

def test_refactor_file_no_orchestrator():
    """Test refactor_file returns skipped when no orchestrator."""
    refactor = AutoRefactor()
    import tempfile
    import os
    import asyncio
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        f.write(b"x = 1\n")
        temp_path = f.name
    try:
        result = asyncio.run(refactor.refactor_file(temp_path))
        assert result == {"status": "skipped", "reason": "No orchestrator"}
    finally:
        os.unlink(temp_path)

def test_refactor_file_no_coder_agent():
    """Test refactor_file returns skipped when no coder agent."""
    class MockOrchestrator:
        def get_agent(self, name):
            return None
    
    refactor = AutoRefactor(orchestrator=MockOrchestrator())
    import tempfile
    import os
    import asyncio
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        f.write(b"x = 1\n")
        temp_path = f.name
    try:
        result = asyncio.run(refactor.refactor_file(temp_path))
        assert result == {"status": "skipped", "reason": "No coder agent"}
    finally:
        os.unlink(temp_path)

def test_refactor_project_empty_directory():
    """Test refactor_project with empty directory returns zero files."""
    refactor = AutoRefactor()
    import tempfile
    import os
    import asyncio
    with tempfile.TemporaryDirectory() as tmpdir:
        result = asyncio.run(refactor.refactor_project(root=tmpdir))
        assert result["total"] == 0
        assert result["refactored"] == 0
        assert result["results"] == []