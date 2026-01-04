#!/usr/bin/env python3
"""
Demo script for the ASCII Flowchart Generator.

This script demonstrates the capabilities of the flowchart generator
with interactive examples.
"""

import sys
sys.path.insert(0, '/home/claude')

from flowchart_generator import FlowchartGenerator


def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def demo_1():
    """Demo 1: Simple Flow"""
    print_header("Demo 1: Simple Three-Node Flow")
    
    print("Input:")
    print("------")
    input_text = """
    A -> B
    B -> C
    A -> C
    """
    print(input_text)
    
    print("\nOutput:")
    print("-------")
    generator = FlowchartGenerator()
    print(generator.generate(input_text))


def demo_2():
    """Demo 2: Software Development Workflow"""
    print_header("Demo 2: Software Development Workflow")
    
    print("Input:")
    print("------")
    input_text = """
    Plan -> Design
    Design -> Code
    Code -> Test
    Test -> Review
    Review -> Deploy
    Review -> Code
    Test -> Code
    """
    print(input_text)
    
    print("\nOutput:")
    print("-------")
    generator = FlowchartGenerator()
    print(generator.generate(input_text))


def demo_3():
    """Demo 3: Error Handling Pattern"""
    print_header("Demo 3: Error Handling Pattern")
    
    print("Input:")
    print("------")
    input_text = """
    Start -> Process
    Process -> Validate
    Validate -> Success
    Validate -> Error
    Error -> Log
    Error -> Retry
    Retry -> Process
    """
    print(input_text)
    
    print("\nOutput:")
    print("-------")
    generator = FlowchartGenerator()
    print(generator.generate(input_text))


def demo_4():
    """Demo 4: Custom Sizing"""
    print_header("Demo 4: Custom Box Sizes")
    
    print("Input (with custom sizing):")
    print("---------------------------")
    input_text = """
    Login -> Auth
    Auth -> Dashboard
    """
    print(input_text)
    print("\nbox_width=17, box_height=5")
    
    print("\nOutput:")
    print("-------")
    generator = FlowchartGenerator(
        box_width=17,
        box_height=5,
        horizontal_spacing=6
    )
    print(generator.generate(input_text))


def demo_5():
    """Demo 5: Complex Branching"""
    print_header("Demo 5: Complex Branching Pattern")
    
    print("Input:")
    print("------")
    input_text = """
    Root -> Task1
    Root -> Task2
    Root -> Task3
    Task1 -> Merge
    Task2 -> Merge
    Task3 -> Merge
    Merge -> Done
    """
    print(input_text)
    
    print("\nOutput:")
    print("-------")
    generator = FlowchartGenerator()
    print(generator.generate(input_text))


def demo_6():
    """Demo 6: With Statistics"""
    print_header("Demo 6: Generate with Statistics")
    
    print("Input:")
    print("------")
    input_text = """
    Init -> Load
    Load -> Process
    Process -> Save
    Save -> Done
    Process -> Error
    Error -> Log
    """
    print(input_text)
    
    print("\nOutput:")
    print("-------")
    generator = FlowchartGenerator()
    flowchart, stats = generator.generate_with_stats(input_text)
    
    print("Statistics:")
    print(f"  • Nodes: {stats['nodes']}")
    print(f"  • Edges: {stats['edges']}")
    print(f"  • Has Cycle: {stats['has_cycle']}")
    print(f"  • Layout Dimensions (w×h): {stats['layout_dimensions']}")
    print(f"  • Longest Path: {stats['longest_path']}")
    print("\nFlowchart:")
    print(flowchart)


def interactive_mode():
    """Interactive mode for custom input."""
    print_header("Interactive Mode")
    
    print("Enter your flowchart connections (one per line).")
    print("Use format: NodeA -> NodeB")
    print("Enter an empty line when done.")
    print()
    
    lines = []
    while True:
        try:
            line = input("  ")
            if not line.strip():
                break
            lines.append(line)
        except EOFError:
            break
    
    if not lines:
        print("\nNo input provided.")
        return
    
    input_text = "\n".join(lines)
    
    print("\n" + "=" * 70)
    print("Your Flowchart:")
    print("=" * 70 + "\n")
    
    try:
        generator = FlowchartGenerator()
        flowchart = generator.generate(input_text)
        print(flowchart)
    except Exception as e:
        print(f"Error: {e}")


def main():
    """Main demo function."""
    demos = [
        ("Simple Flow", demo_1),
        ("Software Workflow", demo_2),
        ("Error Handling", demo_3),
        ("Custom Sizing", demo_4),
        ("Complex Branching", demo_5),
        ("With Statistics", demo_6),
    ]
    
    print("\n" + "=" * 70)
    print("  ASCII FLOWCHART GENERATOR - DEMONSTRATION")
    print("=" * 70)
    print("\nThis demo will show you various capabilities of the generator.")
    print("Press Enter after each demo to continue...")
    
    for title, demo_func in demos:
        input("\n[Press Enter to continue]")
        demo_func()
    
    print("\n" + "=" * 70)
    
    response = input("\nWould you like to try interactive mode? (y/n): ")
    if response.lower().startswith('y'):
        interactive_mode()
    
    print("\n" + "=" * 70)
    print("  Thank you for trying the ASCII Flowchart Generator!")
    print("=" * 70)
    print("\nFor more information:")
    print("  • See README.md for overview")
    print("  • See USAGE.md for detailed usage guide")
    print("  • Run examples.py for more examples")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted. Goodbye!")
        sys.exit(0)
