#!/usr/bin/env python3
"""
Examples of using the flowchart generator.

Run this file to generate example diagrams as PNG files.
"""

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


def example_branching():
    """Branching and merging flow"""
    print("Example 2: Branching Flow")

    input_text = """
    START -> PROCESS A
    START -> PROCESS B
    PROCESS A -> END
    PROCESS B -> END
    """

    generator = FlowchartGenerator()
    generator.save_png(input_text, "example_branching.png", scale=2)
    print("  Saved: example_branching.png\n")


def example_data_pipeline():
    """ETL data pipeline"""
    print("Example 3: Data Pipeline")

    input_text = """
    EXTRACT -> TRANSFORM
    TRANSFORM -> VALIDATE
    VALIDATE -> LOAD
    LOAD -> DONE
    VALIDATE -> ERROR
    ERROR -> LOG
    """

    generator = FlowchartGenerator()
    generator.save_png(input_text, "example_pipeline.png", scale=2)
    print("  Saved: example_pipeline.png\n")


def example_software_workflow():
    """Software development workflow with cycles"""
    print("Example 4: Software Workflow")

    input_text = """
    PLAN -> DESIGN
    DESIGN -> CODE
    CODE -> TEST
    TEST -> REVIEW
    REVIEW -> DEPLOY
    TEST -> CODE
    REVIEW -> CODE
    """

    generator = FlowchartGenerator()
    generator.save_png(input_text, "example_workflow.png", scale=2)
    print("  Saved: example_workflow.png\n")


def example_microservice():
    """Microservice architecture"""
    print("Example 5: Microservice Architecture")

    input_text = """
    API GATEWAY -> AUTH SERVICE
    API GATEWAY -> USER SERVICE
    API GATEWAY -> ORDER SERVICE
    AUTH SERVICE -> DATABASE
    USER SERVICE -> DATABASE
    ORDER SERVICE -> DATABASE
    ORDER SERVICE -> PAYMENT SERVICE
    PAYMENT SERVICE -> NOTIFICATION
    """

    generator = FlowchartGenerator()
    generator.save_png(input_text, "example_microservice.png", scale=2)
    print("  Saved: example_microservice.png\n")


def example_ci_cd():
    """CI/CD pipeline"""
    print("Example 6: CI/CD Pipeline")

    input_text = """
    GIT PUSH -> BUILD
    BUILD -> UNIT TESTS
    UNIT TESTS -> INTEGRATION TESTS
    INTEGRATION TESTS -> SECURITY SCAN
    SECURITY SCAN -> DEPLOY STAGING
    DEPLOY STAGING -> E2E TESTS
    E2E TESTS -> DEPLOY PROD
    UNIT TESTS -> NOTIFY FAILURE
    INTEGRATION TESTS -> NOTIFY FAILURE
    SECURITY SCAN -> NOTIFY FAILURE
    """

    generator = FlowchartGenerator()
    generator.save_png(input_text, "example_cicd.png", scale=2)
    print("  Saved: example_cicd.png\n")


def example_error_handling():
    """Error handling pattern"""
    print("Example 7: Error Handling")

    input_text = """
    REQUEST -> VALIDATE
    VALIDATE -> PROCESS
    PROCESS -> RESPONSE
    VALIDATE -> ERROR HANDLER
    PROCESS -> ERROR HANDLER
    ERROR HANDLER -> LOG
    ERROR HANDLER -> RETRY
    RETRY -> VALIDATE
    """

    generator = FlowchartGenerator()
    generator.save_png(input_text, "example_error_handling.png", scale=2)
    print("  Saved: example_error_handling.png\n")


def example_auth_flow():
    """Authentication flow"""
    print("Example 8: Authentication Flow")

    input_text = """
    USER -> LOGIN
    LOGIN -> AUTHENTICATE
    AUTHENTICATE -> VALID TOKEN
    AUTHENTICATE -> INVALID
    VALID TOKEN -> DASHBOARD
    INVALID -> LOGIN
    DASHBOARD -> LOGOUT
    LOGOUT -> LOGIN
    """

    generator = FlowchartGenerator()
    generator.save_png(input_text, "example_auth.png", scale=2)
    print("  Saved: example_auth.png\n")


def main():
    """Run all examples."""
    print("=" * 50)
    print("Flowchart Generator Examples")
    print("=" * 50)
    print()

    example_simple_linear()
    example_branching()
    example_data_pipeline()
    example_software_workflow()
    example_microservice()
    example_ci_cd()
    example_error_handling()
    example_auth_flow()

    print("=" * 50)
    print("All examples generated!")
    print("=" * 50)


if __name__ == "__main__":
    main()
