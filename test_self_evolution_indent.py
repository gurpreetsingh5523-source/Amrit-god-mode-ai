import ast

from self_evolution import SelfEvolution


def _se() -> SelfEvolution:
    return SelfEvolution.__new__(SelfEvolution)


def test_replace_function_preserves_async_nested_indent() -> None:
    code = "def helper():\n    return 1\n\nasync def target(x):\n    return x\n"
    old = "async def target(x):\n    return x"

    # LLM output arrives with extra left padding before async def.
    new_funcs = (
        "    async def target(x):\n"
        "        async def _inner(y):\n"
        "            return y + 1\n"
        "        v = await _inner(x)\n"
        "        return v\n\n"
        "    def _helper(z):\n"
        "        return z * 2\n"
    )

    patched = _se()._replace_function_in_source(code, "target", old, new_funcs)
    assert patched
    ast.parse(patched)
    assert "async def target(x):" in patched
    assert "    async def _inner(y):" in patched
    assert "def helper():" in patched


def test_replace_function_respects_class_method_base_indent() -> None:
    code = (
        "class A:\n"
        "    async def target(self, x):\n"
        "        return x\n\n"
        "def outside():\n"
        "    return 42\n"
    )
    old = "async def target(self, x):\n        return x"
    new_funcs = (
        "async def target(self, x):\n"
        "    async def _step(v):\n"
        "        return v + 2\n"
        "    return await _step(x)\n\n"
        "def _helper(self, q):\n"
        "    return q\n"
    )

    patched = _se()._replace_function_in_source(code, "target", old, new_funcs)
    assert patched
    ast.parse(patched)
    assert "    async def target(self, x):" in patched
    assert "        async def _step(v):" in patched
    assert "def outside():" in patched


def test_replace_function_handles_tabs_in_original_body() -> None:
    code = "def target(x):\n\tif x > 0:\n\t\treturn x\n\treturn 0\n"
    old = "def target(x):\n\tif x > 0:\n\t\treturn x\n\treturn 0"
    new_funcs = "def target(x):\n    if x > 0:\n        return x + 1\n    return 0\n"

    patched = _se()._replace_function_in_source(code, "target", old, new_funcs)
    assert patched
    ast.parse(patched)
    assert "def target(x):" in patched
    assert "return x + 1" in patched
