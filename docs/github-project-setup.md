# GitHub Project Setup Guide

This document provides step-by-step instructions for setting up the GitHub Project to track the WrkHrs-Birtha convergence implementation.

## Project Overview

**Project URL**: https://github.com/users/mhold3n/projects/3
**Repository**: https://github.com/mhold3n/server

Issue links below reference the **legacy** `Birtha_bigger_n_badder` repository (archived); they remain valid for historical traceability.

## Step 1: Configure Project Views

### 1.1 Create Project Views
Navigate to the project and create the following views:

1. **Backlog View**
   - Name: "Backlog"
   - Filter: `is:open label:wrkhrs-convergence`
   - Group by: Priority
   - Sort by: Created (Oldest first)

2. **In Progress View**
   - Name: "In Progress"
   - Filter: `is:open label:wrkhrs-convergence assignee:*`
   - Group by: Component
   - Sort by: Updated (Newest first)

3. **Done View**
   - Name: "Done"
   - Filter: `is:closed label:wrkhrs-convergence`
   - Group by: Phase
   - Sort by: Closed (Newest first)

4. **Blocked View**
   - Name: "Blocked"
   - Filter: `is:open label:wrkhrs-convergence label:blocked`
   - Group by: Component
   - Sort by: Created (Oldest first)

## Step 2: Create Custom Fields

### 2.1 Component Field
- **Field Name**: Component
- **Field Type**: Single select
- **Options**:
  - API Service
  - Router Service
  - MCP Registry
  - Observability
  - Policy Middleware
  - Resource Management
  - Feedback System
  - Evaluation Framework
  - Infrastructure
  - Documentation

### 2.2 Priority Field
- **Field Name**: Priority
- **Field Type**: Single select
- **Options**:
  - Low
  - Medium
  - High
  - Critical

### 2.3 Phase Field
- **Field Name**: Phase
- **Field Type**: Single select
- **Options**:
  - Phase 1: Foundation
  - Phase 2: Service Integration
  - Phase 3: Policy & Quality
  - Phase 4: Resource Management
  - Phase 5: Feedback & Evaluation
  - Phase 6: Testing & Validation
  - Phase 7: GitHub Integration
  - Phase 8: Documentation & ADRs
  - Phase 9: Project Management

### 2.4 Status Field
- **Field Name**: Status
- **Field Type**: Single select
- **Options**:
  - Not Started
  - In Progress
  - In Review
  - Done
  - Blocked

## Step 3: Configure Automation

### 3.1 Auto-Add Issues
Create automation rules to automatically add issues to the project:

1. **Auto-add labeled issues**
   - Trigger: When an issue is created
   - Condition: Has label `wrkhrs-convergence`
   - Action: Add to project

2. **Auto-set status**
   - Trigger: When an issue is added to project
   - Condition: Has label `wrkhrs-convergence`
   - Action: Set Status field to "Not Started"

3. **Auto-move on assignment**
   - Trigger: When an issue is assigned
   - Condition: Is in project
   - Action: Set Status field to "In Progress"

4. **Auto-move on close**
   - Trigger: When an issue is closed
   - Condition: Is in project
   - Action: Set Status field to "Done"

## Step 4: Add Existing Issues

### 4.1 Current Issues to Add
Add the following existing issues to the project:

- [Issue #8](https://github.com/mhold3n/Birtha_bigger_n_badder/issues/8): Phase 7.1: GitHub Projects Integration
- [Issue #9](https://github.com/mhold3n/Birtha_bigger_n_badder/issues/9): Phase 7.2: GitHub Workflow for Code-Related Prompts
- [Issue #10](https://github.com/mhold3n/Birtha_bigger_n_badder/issues/10): Phase 11.1: Integration Tests for WrkHrs Integration
- [Issue #11](https://github.com/mhold3n/Birtha_bigger_n_badder/issues/11): Phase 11.2: End-to-End Test Scenarios
- [Issue #12](https://github.com/mhold3n/Birtha_bigger_n_badder/issues/12): Phase 10.2: Operator Runbooks
- [Issue #13](https://github.com/mhold3n/Birtha_bigger_n_badder/issues/13): Phase 12.1: GitHub Issue Templates
- [Issue #14](https://github.com/mhold3n/Birtha_bigger_n_badder/issues/14): Phase 12.2: GitHub Project Setup Documentation
- [Issue #15](https://github.com/mhold3n/Birtha_bigger_n_badder/issues/15): Phase 10.3: Update README with Convergence Architecture
- [Issue #16](https://github.com/mhold3n/Birtha_bigger_n_badder/issues/16): Exit Criteria: WrkHrs-Birtha Convergence Project

### 4.2 Set Custom Fields
For each issue, set the appropriate custom fields:

**Issue #8**: Component: MCP/GitHub, Priority: High, Phase: Phase 7, Status: Not Started
**Issue #9**: Component: Router/Workflow, Priority: High, Phase: Phase 7, Status: Not Started
**Issue #10**: Component: Testing, Priority: High, Phase: Phase 11, Status: Not Started
**Issue #11**: Component: Testing, Priority: High, Phase: Phase 11, Status: Not Started
**Issue #12**: Component: Documentation, Priority: Medium, Phase: Phase 10, Status: Not Started
**Issue #13**: Component: Documentation/Templates, Priority: Medium, Phase: Phase 12, Status: Not Started
**Issue #14**: Component: Documentation/Project Management, Priority: Medium, Phase: Phase 12, Status: Not Started
**Issue #15**: Component: Documentation, Priority: Medium, Phase: Phase 10, Status: Not Started
**Issue #16**: Component: Project Management, Priority: High, Phase: Phase 12, Status: Not Started

## Step 5: Create Workflow Automation

### 5.1 GitHub Workflow File
Create `.github/workflows/project-automation.yml`:

```yaml
name: Project Automation

on:
  issues:
    types: [opened, labeled, assigned, closed]
  pull_request:
    types: [opened, closed]

jobs:
  update-project:
    runs-on: ubuntu-latest
    steps:
      - name: Update project status
        uses: actions/github-script@v6
        with:
          script: |
            const { data: project } = await github.rest.projects.get({
              owner: context.repo.owner,
              project_id: 3
            });
            
            // Add logic to update project fields based on issue/PR events
            console.log('Project automation triggered');
```

## Step 6: Verification

### 6.1 Test the Setup
1. Create a test issue with the `wrkhrs-convergence` label
2. Verify it appears in the Backlog view
3. Assign the issue to yourself
4. Verify it moves to In Progress view
5. Close the issue
6. Verify it moves to Done view

### 6.2 Validate Custom Fields
1. Open each existing issue
2. Verify custom fields are set correctly
3. Test filtering by custom fields in each view

## Step 7: Documentation

### 7.1 Update README
Add a section to the main README about the GitHub Project:

```markdown
## Project Management

This project uses GitHub Projects for task tracking and project management.

- **Project Board**: https://github.com/users/mhold3n/projects/3
- **Issue Templates**: Available in `.github/ISSUE_TEMPLATE/`
- **Automation**: Configured via `.github/workflows/project-automation.yml`

### Creating Issues

Use the appropriate issue template:
- **WrkHrs Features**: Use `feature-wrkhrs.md` template
- **MCP Servers**: Use `mcp-server.md` template  
- **Observability**: Use `observability.md` template

### Project Views

- **Backlog**: All open issues with `wrkhrs-convergence` label
- **In Progress**: Assigned issues currently being worked on
- **Done**: Completed issues
- **Blocked**: Issues that are blocked or waiting for dependencies
```

## Troubleshooting

### Common Issues

1. **Issues not appearing in project**
   - Verify the issue has the `wrkhrs-convergence` label
   - Check automation rules are enabled
   - Ensure the issue is not filtered out by view conditions

2. **Custom fields not updating**
   - Verify field names match exactly
   - Check that automation rules are properly configured
   - Ensure the GitHub token has project permissions

3. **Automation not working**
   - Check GitHub Actions logs
   - Verify workflow file syntax
   - Ensure repository has Actions enabled

## Maintenance

### Regular Tasks

1. **Weekly**: Review project status and update issue priorities
2. **Monthly**: Clean up completed issues and archive old ones
3. **Quarterly**: Review and update custom fields and automation rules

### Updates

When adding new phases or components:
1. Update custom field options
2. Update issue templates
3. Update automation rules
4. Update this documentation



