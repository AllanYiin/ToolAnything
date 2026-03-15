from pathlib import Path


def test_class_method_example_demo_registers_both_orders():
    module = __import__("examples.class_method_tools.demo", fromlist=["registry"])
    registry = module.registry
    tool_names = sorted(spec.name for spec in registry.list())

    assert tool_names == ["classmethod.inner_order", "classmethod.outer_order"]


def test_class_method_example_readme_mentions_both_orders_and_demo_command():
    readme = Path("examples/class_method_tools/README.md").read_text(encoding="utf-8")

    assert "python examples/class_method_tools/demo.py" in readme
    assert "@tool(...)" in readme
    assert "@classmethod" in readme
    assert "classmethod.outer_order" in readme
    assert "classmethod.inner_order" in readme
