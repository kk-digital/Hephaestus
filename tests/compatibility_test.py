#!/usr/bin/env python3
"""Test backward compatibility of import paths after three-layer refactoring.

This script verifies that:
1. Old import paths still work (via backward compatibility shims)
2. New import paths work (direct imports from c1/c2/c3 modules)
3. Old and new paths point to the same objects
4. All critical services and models are accessible
"""

import sys
from typing import Any


def test_old_database_imports():
    """Old database imports should still work via shims."""
    print("\n=== Testing Old Database Imports (src.core.database) ===")
    try:
        from src.core.database import (
            Agent,
            Task,
            Memory,
            Workflow,
            WorkflowResult,
            AgentResult,
            Ticket,
            TicketHistory,
            AgentLog,
            GuardianAnalysis,
            ConductorAnalysis,
        )
        assert Agent is not None
        assert Task is not None
        assert Memory is not None
        assert Workflow is not None
        assert WorkflowResult is not None
        assert AgentResult is not None
        assert Ticket is not None
        print("✓ Old database imports work (Agent, Task, Memory, Workflow, WorkflowResult, AgentResult, Ticket, etc.)")
        return True
    except ImportError as e:
        print(f"✗ Old database imports FAILED: {e}")
        return False


def test_new_model_imports():
    """New c1 model imports should work."""
    print("\n=== Testing New C1 Model Imports ===")
    try:
        from src.c1_agent_models.agent import Agent, AgentResult
        from src.c1_task_models.task import Task
        from src.c1_memory_models.memory import Memory
        from src.c1_workflow_models.workflow import Workflow, WorkflowResult
        from src.c1_ticket_models.ticket import Ticket
        assert Agent is not None
        assert Task is not None
        assert Memory is not None
        assert Workflow is not None
        assert WorkflowResult is not None
        assert AgentResult is not None
        assert Ticket is not None
        print("✓ New c1 model imports work (Agent, Task, Memory, Workflow, WorkflowResult, AgentResult, Ticket)")
        return True
    except ImportError as e:
        print(f"✗ New c1 model imports FAILED: {e}")
        return False


def test_same_classes():
    """Old and new imports should point to the same classes."""
    print("\n=== Testing Import Identity ===")
    failures = []

    # Test Agent
    try:
        from src.core.database import Agent as OldAgent
        from src.c1_agent_models.agent import Agent as NewAgent
        if OldAgent is NewAgent:
            print("✓ Agent: Old and new imports are identical")
        else:
            print("✗ Agent: Old and new imports are DIFFERENT objects!")
            failures.append("Agent")
    except Exception as e:
        print(f"✗ Agent identity test FAILED: {e}")
        failures.append("Agent")

    # Test Task
    try:
        from src.core.database import Task as OldTask
        from src.c1_task_models.task import Task as NewTask
        if OldTask is NewTask:
            print("✓ Task: Old and new imports are identical")
        else:
            print("✗ Task: Old and new imports are DIFFERENT objects!")
            failures.append("Task")
    except Exception as e:
        print(f"✗ Task identity test FAILED: {e}")
        failures.append("Task")

    # Test Memory
    try:
        from src.core.database import Memory as OldMemory
        from src.c1_memory_models.memory import Memory as NewMemory
        if OldMemory is NewMemory:
            print("✓ Memory: Old and new imports are identical")
        else:
            print("✗ Memory: Old and new imports are DIFFERENT objects!")
            failures.append("Memory")
    except Exception as e:
        print(f"✗ Memory identity test FAILED: {e}")
        failures.append("Memory")

    # Test Workflow
    try:
        from src.core.database import Workflow as OldWorkflow
        from src.c1_workflow_models.workflow import Workflow as NewWorkflow
        if OldWorkflow is NewWorkflow:
            print("✓ Workflow: Old and new imports are identical")
        else:
            print("✗ Workflow: Old and new imports are DIFFERENT objects!")
            failures.append("Workflow")
    except Exception as e:
        print(f"✗ Workflow identity test FAILED: {e}")
        failures.append("Workflow")

    # Test WorkflowResult
    try:
        from src.core.database import WorkflowResult as OldWorkflowResult
        from src.c1_workflow_models.workflow import WorkflowResult as NewWorkflowResult
        if OldWorkflowResult is NewWorkflowResult:
            print("✓ WorkflowResult: Old and new imports are identical")
        else:
            print("✗ WorkflowResult: Old and new imports are DIFFERENT objects!")
            failures.append("WorkflowResult")
    except Exception as e:
        print(f"✗ WorkflowResult identity test FAILED: {e}")
        failures.append("WorkflowResult")

    # Test AgentResult
    try:
        from src.core.database import AgentResult as OldAgentResult
        from src.c1_agent_models.agent import AgentResult as NewAgentResult
        if OldAgentResult is NewAgentResult:
            print("✓ AgentResult: Old and new imports are identical")
        else:
            print("✗ AgentResult: Old and new imports are DIFFERENT objects!")
            failures.append("AgentResult")
    except Exception as e:
        print(f"✗ AgentResult identity test FAILED: {e}")
        failures.append("AgentResult")

    # Test Ticket
    try:
        from src.core.database import Ticket as OldTicket
        from src.c1_ticket_models.ticket import Ticket as NewTicket
        if OldTicket is NewTicket:
            print("✓ Ticket: Old and new imports are identical")
        else:
            print("✗ Ticket: Old and new imports are DIFFERENT objects!")
            failures.append("Ticket")
    except Exception as e:
        print(f"✗ Ticket identity test FAILED: {e}")
        failures.append("Ticket")

    return len(failures) == 0


def test_old_service_imports():
    """Old service imports should still work via shims."""
    print("\n=== Testing Old Service Imports ===")
    failures = []

    # Test services that were migrated to c2 modules
    services_to_test = [
        ("src.services.ticket_service", "TicketService"),
        ("src.services.queue_service", "QueueService"),
        ("src.services.result_service", "ResultService"),
        ("src.services.embedding_service", "EmbeddingService"),
    ]

    for module_path, class_name in services_to_test:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            assert cls is not None
            print(f"✓ {module_path}.{class_name} imports successfully")
        except ImportError as e:
            print(f"✗ {module_path}.{class_name} FAILED: {e}")
            failures.append(f"{module_path}.{class_name}")
        except AttributeError as e:
            print(f"✗ {module_path}.{class_name} FAILED (AttributeError): {e}")
            failures.append(f"{module_path}.{class_name}")

    return len(failures) == 0


def test_new_service_imports():
    """New c2 service imports should work."""
    print("\n=== Testing New C2 Service Imports ===")
    failures = []

    services_to_test = [
        ("src.c2_ticket_service.ticket_service", "TicketService"),
        ("src.c2_queue_service.queue_service", "QueueService"),
        ("src.c2_result_service.result_service", "ResultService"),
        ("src.c2_embedding_service.embedding_service", "EmbeddingService"),
    ]

    for module_path, class_name in services_to_test:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            assert cls is not None
            print(f"✓ {module_path}.{class_name} imports successfully")
        except ImportError as e:
            print(f"✗ {module_path}.{class_name} FAILED: {e}")
            failures.append(f"{module_path}.{class_name}")
        except AttributeError as e:
            print(f"✗ {module_path}.{class_name} FAILED (AttributeError): {e}")
            failures.append(f"{module_path}.{class_name}")

    return len(failures) == 0


def test_service_identity():
    """Old and new service imports should point to same classes."""
    print("\n=== Testing Service Import Identity ===")
    failures = []

    # Test TicketService
    try:
        from src.services.ticket_service import TicketService as OldTicketService
        from src.c2_ticket_service.ticket_service import TicketService as NewTicketService
        if OldTicketService is NewTicketService:
            print("✓ TicketService: Old and new imports are identical")
        else:
            print("✗ TicketService: Old and new imports are DIFFERENT objects!")
            failures.append("TicketService")
    except Exception as e:
        print(f"✗ TicketService identity test FAILED: {e}")
        failures.append("TicketService")

    # Test QueueService
    try:
        from src.services.queue_service import QueueService as OldQueueService
        from src.c2_queue_service.queue_service import QueueService as NewQueueService
        if OldQueueService is NewQueueService:
            print("✓ QueueService: Old and new imports are identical")
        else:
            print("✗ QueueService: Old and new imports are DIFFERENT objects!")
            failures.append("QueueService")
    except Exception as e:
        print(f"✗ QueueService identity test FAILED: {e}")
        failures.append("QueueService")

    # Test ResultService
    try:
        from src.services.result_service import ResultService as OldResultService
        from src.c2_result_service.result_service import ResultService as NewResultService
        if OldResultService is NewResultService:
            print("✓ ResultService: Old and new imports are identical")
        else:
            print("✗ ResultService: Old and new imports are DIFFERENT objects!")
            failures.append("ResultService")
    except Exception as e:
        print(f"✗ ResultService identity test FAILED: {e}")
        failures.append("ResultService")

    # Test EmbeddingService
    try:
        from src.services.embedding_service import EmbeddingService as OldEmbeddingService
        from src.c2_embedding_service.embedding_service import EmbeddingService as NewEmbeddingService
        if OldEmbeddingService is NewEmbeddingService:
            print("✓ EmbeddingService: Old and new imports are identical")
        else:
            print("✗ EmbeddingService: Old and new imports are DIFFERENT objects!")
            failures.append("EmbeddingService")
    except Exception as e:
        print(f"✗ EmbeddingService identity test FAILED: {e}")
        failures.append("EmbeddingService")

    return len(failures) == 0


def test_core_database_import():
    """Test core.database backward compatibility shim."""
    print("\n=== Testing Core Database Import ===")
    try:
        from src.core.database import DatabaseManager
        assert DatabaseManager is not None
        print("✓ src.core.database.DatabaseManager imports successfully")
        return True
    except ImportError as e:
        print(f"✗ src.core.database.DatabaseManager FAILED: {e}")
        return False


def main():
    """Run all compatibility tests."""
    print("=" * 70)
    print("BACKWARD COMPATIBILITY TEST SUITE")
    print("Three-Layer Architecture Refactoring")
    print("=" * 70)

    results = []

    # Run all tests
    results.append(("Old Database Imports", test_old_database_imports()))
    results.append(("New C1 Model Imports", test_new_model_imports()))
    results.append(("Model Import Identity", test_same_classes()))
    results.append(("Old Service Imports", test_old_service_imports()))
    results.append(("New C2 Service Imports", test_new_service_imports()))
    results.append(("Service Import Identity", test_service_identity()))
    results.append(("Core Database Import", test_core_database_import()))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:12} {test_name}")

    print("-" * 70)
    print(f"Total: {passed}/{total} tests passed ({passed * 100 // total}%)")
    print("=" * 70)

    if passed == total:
        print("\n✅ ALL COMPATIBILITY TESTS PASSED!")
        print("\nBackward compatibility is maintained:")
        print("  • Old import paths work (via shims)")
        print("  • New import paths work (direct)")
        print("  • Both paths point to same objects")
        print("  • All services accessible")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED!")
        print("\nBackward compatibility issues detected.")
        print("See test output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
