"""
Main flowchart module.

Provides the high-level API for generating flowcharts.
"""

from typing import Optional
try:
    from .parser import parse_flowchart
    from .graph import create_graph
    from .layout import compute_layout
    from .renderer import render_flowchart
    from .png_renderer import render_to_png
except ImportError:
    # Allow direct imports for testing
    from parser import parse_flowchart
    from graph import create_graph
    from layout import compute_layout
    from renderer import render_flowchart
    from png_renderer import render_to_png


class FlowchartGenerator:
    """
    Main class for generating ASCII flowcharts.
    
    Example:
        generator = FlowchartGenerator()
        flowchart = generator.generate('''
            A -> B
            B -> C
            A -> C
        ''')
        print(flowchart)
    """
    
    def __init__(self,
                 box_width: int = 11,
                 box_height: int = 3,
                 horizontal_spacing: int = 4,
                 vertical_spacing: int = 3,
                 layout_algorithm: str = 'layered'):
        """
        Initialize the flowchart generator.
        
        Args:
            box_width: Width of each box (default: 11)
            box_height: Height of each box (default: 3)
            horizontal_spacing: Space between boxes horizontally (default: 4)
            vertical_spacing: Space between boxes vertically (default: 3)
            layout_algorithm: 'layered' or 'simple' (default: 'layered')
        """
        self.box_width = box_width
        self.box_height = box_height
        self.horizontal_spacing = horizontal_spacing
        self.vertical_spacing = vertical_spacing
        self.layout_algorithm = layout_algorithm
    
    def generate(self, input_text: str) -> str:
        """
        Generate an ASCII flowchart from input text.
        
        Args:
            input_text: Multi-line string with connections (e.g., "A -> B")
            
        Returns:
            ASCII string representation of the flowchart
            
        Raises:
            ParseError: If input format is invalid
        """
        # Parse input
        connections = parse_flowchart(input_text)
        
        # Create graph
        graph = create_graph(connections)
        
        # Compute layout
        layout = compute_layout(
            graph,
            algorithm=self.layout_algorithm,
            horizontal_spacing=self.horizontal_spacing,
            vertical_spacing=self.vertical_spacing
        )
        
        # Render flowchart
        flowchart = render_flowchart(
            graph,
            layout,
            box_width=self.box_width,
            box_height=self.box_height,
            horizontal_spacing=self.horizontal_spacing,
            vertical_spacing=self.vertical_spacing
        )
        
        return flowchart
    
    def generate_with_stats(self, input_text: str) -> tuple:
        """
        Generate flowchart and return statistics.
        
        Args:
            input_text: Multi-line string with connections
            
        Returns:
            Tuple of (flowchart_string, statistics_dict)
        """
        connections = parse_flowchart(input_text)
        graph = create_graph(connections)
        
        layout = compute_layout(
            graph,
            algorithm=self.layout_algorithm,
            horizontal_spacing=self.horizontal_spacing,
            vertical_spacing=self.vertical_spacing
        )
        
        flowchart = render_flowchart(
            graph,
            layout,
            box_width=self.box_width,
            box_height=self.box_height,
            horizontal_spacing=self.horizontal_spacing,
            vertical_spacing=self.vertical_spacing
        )
        
        stats = {
            'nodes': len(graph.nodes),
            'edges': len(graph.edges),
            'has_cycle': graph.has_cycle(),
            'layout_dimensions': layout.get_layout_dimensions(),
            'longest_path': graph.get_longest_path_length(),
        }
        
        return flowchart, stats

    def save_png(self, input_text: str, output_path: str = "diagram.png", **png_kwargs) -> str:
        """
        Generate a flowchart and save it as a high-resolution PNG image.

        Args:
            input_text: Multi-line string with connections (e.g., "A -> B")
            output_path: Path to save the PNG file
            **png_kwargs: Additional parameters for PNG renderer

        Returns:
            Path to the saved PNG file
        """
        # Parse input
        connections = parse_flowchart(input_text)

        # Create graph
        graph = create_graph(connections)

        # Compute layout
        layout = compute_layout(
            graph,
            algorithm=self.layout_algorithm,
            horizontal_spacing=self.horizontal_spacing,
            vertical_spacing=self.vertical_spacing
        )

        # Render to PNG
        return render_to_png(graph, layout, output_path, **png_kwargs)

    def save_txt(self, input_text: str, output_path: str = "diagram.txt") -> str:
        """
        Generate a flowchart and save it as an ASCII text file.

        Args:
            input_text: Multi-line string with connections (e.g., "A -> B")
            output_path: Path to save the text file

        Returns:
            Path to the saved text file
        """
        # Generate ASCII flowchart
        flowchart = self.generate(input_text)

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(flowchart)

        return output_path


def generate_flowchart(input_text: str, **kwargs) -> str:
    """
    Convenience function to generate a flowchart.
    
    Args:
        input_text: Multi-line string with connections
        **kwargs: Additional parameters for FlowchartGenerator
        
    Returns:
        ASCII string representation of the flowchart
    """
    generator = FlowchartGenerator(**kwargs)
    return generator.generate(input_text)
