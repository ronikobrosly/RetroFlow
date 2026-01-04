# ascii-diagram
Cool, retro computing format for flow charts and diagrams


Run `examples.py` for test output

```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flowchart import FlowchartGenerator


def example_simple_linear():
    """Simple linear flow: A -> B -> C -> D"""
    print("Example 1: Simple Linear Flow")

    input_text = """
    A -> B
    B -> C
    C -> D
    """

    generator = FlowchartGenerator()
    generator.save_png(input_text, "example_linear.png", scale=2)
    print("  Saved: example_linear.png\n")
```