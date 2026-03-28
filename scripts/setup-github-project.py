#!/usr/bin/env python3
"""
GitHub Project Setup Script

This script helps set up the GitHub Project by providing instructions
and automating some of the setup process.
"""

import os
import sys
from typing import List, Dict

# Issue data for the WrkHrs-Birtha convergence project
ISSUES = [
    {
        "number": 8,
        "title": "Phase 7.1: GitHub Projects Integration",
        "component": "MCP/GitHub",
        "priority": "High",
        "phase": "Phase 7",
        "status": "Not Started"
    },
    {
        "number": 9,
        "title": "Phase 7.2: GitHub Workflow for Code-Related Prompts",
        "component": "Router/Workflow",
        "priority": "High",
        "phase": "Phase 7",
        "status": "Not Started"
    },
    {
        "number": 10,
        "title": "Phase 11.1: Integration Tests for WrkHrs Integration",
        "component": "Testing",
        "priority": "High",
        "phase": "Phase 11",
        "status": "Not Started"
    },
    {
        "number": 11,
        "title": "Phase 11.2: End-to-End Test Scenarios",
        "component": "Testing",
        "priority": "High",
        "phase": "Phase 11",
        "status": "Not Started"
    },
    {
        "number": 12,
        "title": "Phase 10.2: Operator Runbooks",
        "component": "Documentation",
        "priority": "Medium",
        "phase": "Phase 10",
        "status": "Not Started"
    },
    {
        "number": 13,
        "title": "Phase 12.1: GitHub Issue Templates",
        "component": "Documentation/Templates",
        "priority": "Medium",
        "phase": "Phase 12",
        "status": "Not Started"
    },
    {
        "number": 14,
        "title": "Phase 12.2: GitHub Project Setup Documentation",
        "component": "Documentation/Project Management",
        "priority": "Medium",
        "phase": "Phase 12",
        "status": "Not Started"
    },
    {
        "number": 15,
        "title": "Phase 10.3: Update README with Convergence Architecture",
        "component": "Documentation",
        "priority": "Medium",
        "phase": "Phase 10",
        "status": "Not Started"
    },
    {
        "number": 16,
        "title": "Exit Criteria: WrkHrs-Birtha Convergence Project",
        "component": "Project Management",
        "priority": "High",
        "phase": "Phase 12",
        "status": "Not Started"
    }
]

def print_setup_instructions():
    """Print step-by-step setup instructions."""
    print("GitHub Project Setup Instructions")
    print("=" * 50)
    print()
    
    print("1. Add Issues to Project")
    print("   Go to: https://github.com/users/mhold3n/projects/3")
    print("   Click 'Add item' and search for each issue:")
    print()
    
    for issue in ISSUES:
        print(f"   - Issue #{issue['number']}: {issue['title']}")
        print(f"     Component: {issue['component']}")
        print(f"     Priority: {issue['priority']}")
        print(f"     Phase: {issue['phase']}")
        print()
    
    print("2. Configure Project Views")
    print("   Create these views:")
    print("   - Backlog: Filter by 'is:open label:wrkhrs-convergence'")
    print("   - In Progress: Filter by 'is:open label:wrkhrs-convergence assignee:*'")
    print("   - Done: Filter by 'is:closed label:wrkhrs-convergence'")
    print("   - Blocked: Filter by 'is:open label:wrkhrs-convergence label:blocked'")
    print()
    
    print("3. Set Custom Fields")
    print("   For each issue, set:")
    print("   - Component: (API Service, Router Service, MCP Registry, etc.)")
    print("   - Priority: (Low, Medium, High, Critical)")
    print("   - Phase: (Phase 1-12)")
    print("   - Status: (Not Started, In Progress, In Review, Done, Blocked)")
    print()
    
    print("4. Configure Automation")
    print("   Set up automation rules:")
    print("   - Auto-add issues with 'wrkhrs-convergence' label")
    print("   - Auto-set status to 'In Progress' when assigned")
    print("   - Auto-set status to 'Done' when closed")
    print()

def generate_project_urls():
    """Generate direct URLs for adding issues to the project."""
    print("Direct URLs for Adding Issues to Project")
    print("=" * 50)
    print()
    
    base_url = "https://github.com/mhold3n/server/issues"
    
    for issue in ISSUES:
        url = f"{base_url}/{issue['number']}"
        print(f"Issue #{issue['number']}: {url}")
        print(f"  Title: {issue['title']}")
        print(f"  Component: {issue['component']}")
        print(f"  Priority: {issue['priority']}")
        print()

def main():
    """Main function."""
    if len(sys.argv) > 1 and sys.argv[1] == "--urls":
        generate_project_urls()
    else:
        print_setup_instructions()
        
        print("Tip: Run with --urls flag to see direct issue URLs")
        print("   python scripts/setup-github-project.py --urls")

if __name__ == "__main__":
    main()
