#!/usr/bin/env python3
"""
Generate individual task files for each test failure.

Parses pytest output and creates a task file for each failed test with:
- Analysis requirements
- Fix requirements
- Verification requirements
- Report generation requirements
"""

import re
import sys
from pathlib import Path
from datetime import datetime

def parse_pytest_output(log_file):
    """Parse pytest log file and extract failed tests."""
    failures = []

    with open(log_file, 'r') as f:
        content = f.read()

    # Pattern to match FAILED test lines
    # Example: FAILED tests/test_example.py::test_function - AssertionError: ...
    # Or: FAILED tests/test_example.py::ClassName::test_function (with class name)
    # Or: FAILED tests/test_example.py::test_function (without error message)
    pattern = r'FAILED\s+(tests/[^\s:]+)::(?:[\w]+::)?(test_\w+)(?:\[([^\]]+)\])?(?:\s*-\s*(.+?))?(?=\n|$)'

    matches = re.finditer(pattern, content, re.MULTILINE)

    for match in matches:
        test_file = match.group(1)
        test_name = match.group(2)
        test_params = match.group(3) if match.group(3) else None
        error_msg = match.group(4).strip() if match.group(4) else "Test failed (no error message captured)"

        failures.append({
            'file': test_file,
            'name': test_name,
            'params': test_params,
            'error': error_msg,
            'full_name': f"{test_file}::{test_name}" + (f"[{test_params}]" if test_params else "")
        })

    return failures

def generate_task_file(failure, task_number, output_dir):
    """Generate a task file for a single test failure."""

    date_str = datetime.now().strftime("%y%m%d")
    task_file = output_dir / f"{date_str}-task-{task_number:02d}-fix-{failure['name']}.pending.txt"

    content = f"""TASK-{task_number}: Fix Test Failure - {failure['name']}
{'=' * 70}
Date Created: {datetime.now().strftime("%Y-%m-%d")}
Status: PENDING
Priority: HIGH
Category: Test Failure, Bug Fix

TEST INFORMATION:
=================

Test File: {failure['file']}
Test Function: {failure['name']}
{f"Test Parameters: {failure['params']}" if failure['params'] else ""}
Full Test Name: {failure['full_name']}

ERROR MESSAGE:
==============

{failure['error']}

TASK OBJECTIVES:
================

1. ANALYSIS
   - Review test code to understand what is being tested
   - Review application code that the test is validating
   - Identify root cause of test failure
   - Determine if failure is due to:
     * Bug in application code
     * Bug in test code
     * Configuration issue
     * Missing dependency
     * Environmental issue
     * Breaking change from refactoring

2. INVESTIGATION
   - Check git history for recent changes to this test
   - Check git history for recent changes to tested code
   - Review related tests for similar failures
   - Check if test was passing before refactoring
   - Identify when test started failing (git bisect if needed)

3. FIX IMPLEMENTATION
   - Implement fix based on root cause analysis
   - Update test code if test is incorrect
   - Update application code if application is incorrect
   - Update mocks/fixtures if setup is incorrect
   - Add missing dependencies if needed

4. VERIFICATION
   - Run the specific test to verify fix
   - Run related tests to ensure no regressions
   - Run full test suite to ensure no side effects
   - Verify test coverage is maintained or improved
   - Test edge cases related to the fix

5. DOCUMENTATION
   - Document root cause in report
   - Document fix approach in report
   - Document any related issues discovered
   - Update code comments if needed
   - Update test documentation if needed

DELIVERABLES:
=============

[ ] Root cause analysis completed
[ ] Fix implemented and tested
[ ] Related tests verified
[ ] Report generated in reports/test-failures/
[ ] Task marked as complete

REPORT REQUIREMENTS:
====================

Create report: reports/test-failures/report-task-{task_number:02d}-{failure['name']}.txt

Report must include:
1. Test failure summary
2. Root cause analysis
3. Fix description and implementation
4. Verification results
5. Any related issues discovered
6. Recommendations for preventing similar failures

ACCEPTANCE CRITERIA:
====================

- Test passes successfully
- No new test failures introduced
- Root cause documented
- Fix is appropriate and maintainable
- Report is complete and clear

DEPENDENCIES:
=============

- Access to test suite
- Access to application code
- Ability to run tests
- Understanding of tested functionality

NOTES:
======

- This is part of systematic test failure resolution
- Coordinate with Task-34 (test changes review) if related
- Flag any discoveries that need user approval
- If fix requires significant refactoring, flag for approval before proceeding

[USER APPROVAL NEEDED]
If this test failure reveals a broader issue or requires significant changes beyond
simple bug fix, flag for user review before implementing large-scale changes.
"""

    task_file.write_text(content)
    return task_file

def main():
    if len(sys.argv) < 2:
        print("Usage: generate_test_failure_tasks.py <pytest_log_file>")
        sys.exit(1)

    log_file = Path(sys.argv[1])
    if not log_file.exists():
        print(f"Error: Log file not found: {log_file}")
        sys.exit(1)

    # Parse failures
    failures = parse_pytest_output(log_file)

    if not failures:
        print("No test failures found in log file.")
        return

    print(f"Found {len(failures)} test failures")

    # Create tasks directory if it doesn't exist
    tasks_dir = Path("/home/user/claude-hephaestus-python/Hephaestus/tasks")
    tasks_dir.mkdir(parents=True, exist_ok=True)

    # Find next available task number
    existing_tasks = list(tasks_dir.glob("*-task-*.txt"))
    if existing_tasks:
        # Extract task numbers
        task_numbers = []
        for task in existing_tasks:
            match = re.search(r'task-(\d+)', task.name)
            if match:
                task_numbers.append(int(match.group(1)))
        next_task_num = max(task_numbers) + 1 if task_numbers else 36
    else:
        next_task_num = 36

    # Generate task files
    generated_tasks = []
    for i, failure in enumerate(failures):
        task_num = next_task_num + i
        task_file = generate_task_file(failure, task_num, tasks_dir)
        generated_tasks.append(task_file)
        print(f"Created: {task_file.name}")

    print(f"\nGenerated {len(generated_tasks)} task files")
    print(f"Task numbers: {next_task_num} to {next_task_num + len(failures) - 1}")

    # Create summary file
    summary_file = tasks_dir / f"{datetime.now().strftime('%y%m%d')}-test-failures-summary.txt"
    summary_content = f"""TEST FAILURES SUMMARY
{'=' * 70}
Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Total Failures: {len(failures)}

FAILED TESTS:
"""

    for i, failure in enumerate(failures, 1):
        summary_content += f"\n{i}. {failure['full_name']}\n"
        summary_content += f"   Error: {failure['error'][:100]}...\n"
        summary_content += f"   Task: task-{next_task_num + i - 1:02d}\n"

    summary_file.write_text(summary_content)
    print(f"\nSummary created: {summary_file.name}")

if __name__ == "__main__":
    main()
