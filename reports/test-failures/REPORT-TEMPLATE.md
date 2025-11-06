# Test Failure Report: {TEST_NAME}

**Date:** {DATE}
**Task ID:** task-{TASK_NUMBER}
**Test File:** {TEST_FILE}
**Test Function:** {TEST_FUNCTION}

---

## Executive Summary

**Status:** {RESOLVED/BLOCKED/IN PROGRESS}
**Root Cause:** {ONE_LINE_SUMMARY}
**Fix Complexity:** {TRIVIAL/SIMPLE/MODERATE/COMPLEX}

---

## Test Information

### Test Location
- **File:** `{TEST_FILE}`
- **Function:** `{TEST_FUNCTION}`
- **Line:** {LINE_NUMBER}

### Error Details
```
{ERROR_MESSAGE}
{TRACEBACK}
```

### Expected vs Actual
- **Expected:** {EXPECTED_BEHAVIOR}
- **Actual:** {ACTUAL_BEHAVIOR}

---

## Root Cause Analysis

### Investigation Steps
1. {STEP_1}
2. {STEP_2}
3. {STEP_3}

### Findings
{DETAILED_FINDINGS}

### Root Cause
{ROOT_CAUSE_DESCRIPTION}

**Category:** {BUG_IN_CODE/BUG_IN_TEST/CONFIG_ISSUE/DEPENDENCY/BREAKING_CHANGE/OTHER}

---

## Fix Implementation

### Approach
{FIX_APPROACH_DESCRIPTION}

### Code Changes
```python
# File: {CHANGED_FILE}
# Changes made:

{CODE_DIFF_OR_DESCRIPTION}
```

### Related Changes
- {CHANGE_1}
- {CHANGE_2}

---

## Verification

### Test Execution
```bash
$ pytest {TEST_FILE}::{TEST_FUNCTION} -v
```

**Result:** {PASS/FAIL}

### Related Tests
Verified the following related tests still pass:
- {RELATED_TEST_1}: {PASS/FAIL}
- {RELATED_TEST_2}: {PASS/FAIL}

### Full Suite Impact
```
Total tests run: {N}
Passed: {N}
Failed: {N}
```

---

## Discoveries

### Issues Found During Investigation
1. {DISCOVERY_1}
2. {DISCOVERY_2}

### Recommendations
1. {RECOMMENDATION_1}
2. {RECOMMENDATION_2}

### Follow-up Tasks
- [ ] {FOLLOW_UP_1}
- [ ] {FOLLOW_UP_2}

---

## User Approval Needed

*No items requiring approval*

OR

### Item 1: {TITLE}
**Issue:** {DESCRIPTION}
**Recommendation:** {PROPOSED_ACTION}
**Impact:** {WHAT_THIS_AFFECTS}
**Urgency:** {LOW/MEDIUM/HIGH/CRITICAL}

---

## Conclusion

{SUMMARY_OF_WORK_DONE}

**Test Status:** {NOW_PASSING/STILL_FAILING/BLOCKED}
**Next Steps:** {WHAT_TO_DO_NEXT}

---

*Report generated for Task-{TASK_NUMBER} | {DATE}*
