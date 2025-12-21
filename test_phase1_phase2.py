"""Test script for Phase 1 and Phase 2 components.

This script tests the core architecture without requiring the full GUI.
"""

import sys
import time
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from gui.core import TaskState, TaskStateMachine, TaskData, StepData, TaskExecutor
from gui.persistence import ConnectionPool, TaskRepository, StepRepository, BackupManager
from gui.utils.crash_recovery import recover_crashed_tasks


def test_state_machine():
    """Test state machine transitions."""
    print("\n" + "="*60)
    print("Testing State Machine")
    print("="*60)
    
    # Create state machine
    state_machine = TaskStateMachine("test-session-1")
    
    # Test valid transitions
    print(f"Initial state: {state_machine.get_state()}")
    assert state_machine.get_state() == TaskState.CREATED
    
    print("Transitioning to RUNNING...")
    assert state_machine.transition_to(TaskState.RUNNING)
    assert state_machine.get_state() == TaskState.RUNNING
    
    print("Transitioning to STOPPING...")
    assert state_machine.transition_to(TaskState.STOPPING)
    assert state_machine.get_state() == TaskState.STOPPING
    
    print("Transitioning to STOPPED...")
    assert state_machine.transition_to(TaskState.STOPPED)
    assert state_machine.get_state() == TaskState.STOPPED
    
    # Test invalid transition
    print("Attempting invalid transition to RUNNING (should fail)...")
    assert not state_machine.transition_to(TaskState.RUNNING)
    
    # Test CRASHED transition (always valid)
    print("Transitioning to CRASHED (always valid)...")
    assert state_machine.transition_to(TaskState.CRASHED)
    assert state_machine.get_state() == TaskState.CRASHED
    
    print("✅ State machine tests passed!")


def test_repositories():
    """Test repository operations."""
    print("\n" + "="*60)
    print("Testing Repositories")
    print("="*60)
    
    # Create test database
    test_db = "logs/test_phase1_phase2.db"
    Path(test_db).unlink(missing_ok=True)
    
    # Create connection pool
    pool = ConnectionPool(test_db, pool_size=3)
    
    # Create repositories
    task_repo = TaskRepository(pool)
    step_repo = StepRepository(pool)
    
    # Test task creation
    print("Creating task...")
    task_data = TaskData.create(
        description="Test task",
        user_id="test_user",
        device_id="test_device"
    )
    session_id = task_repo.create_task(task_data)
    print(f"Created task: {session_id}")
    
    # Test state update
    print("Updating task state to RUNNING...")
    task_repo.update_task_state(session_id, TaskState.RUNNING)
    
    # Test step insertion
    print("Inserting steps...")
    for i in range(1, 4):
        step_data = StepData(
            session_id=session_id,
            step_num=i,
            screenshot_path=f"/path/to/screenshot_{i}.png",
            screenshot_analysis=f"Analysis {i}",
            action={"type": "tap", "x": 100, "y": 200},
            action_params={"duration": 0.1},
            execution_time=0.5,
            success=True,
            message=f"Step {i} completed",
            thinking=f"Thinking for step {i}"
        )
        step_repo.insert_step(step_data)
        print(f"  Inserted step {i}")
    
    # Test step existence check
    print("Checking step existence...")
    assert step_repo.step_exists(session_id, 1)
    assert step_repo.step_exists(session_id, 2)
    assert step_repo.step_exists(session_id, 3)
    assert not step_repo.step_exists(session_id, 4)
    
    # Test finalization
    print("Finalizing task...")
    task_repo.finalize_task(session_id, TaskState.SUCCESS, 3, 1.5, None)
    
    # Test retrieval
    print("Retrieving steps...")
    steps = step_repo.get_steps_for_session(session_id)
    assert len(steps) == 3
    print(f"  Retrieved {len(steps)} steps")
    
    # Cleanup
    pool.close_all()
    
    print("✅ Repository tests passed!")


def test_backup_manager():
    """Test backup and recovery."""
    print("\n" + "="*60)
    print("Testing Backup Manager")
    print("="*60)
    
    backup_manager = BackupManager("logs/test_backup")
    
    # Test task backup
    print("Saving task backup...")
    task_data = {
        'session_id': 'test-backup-1',
        'user_id': 'test_user',
        'timestamp': '2025-12-19T10:00:00',
        'description': 'Test backup task',
    }
    backup_manager.save_task_backup('test-backup-1', task_data)
    
    # Test step backup
    print("Saving step backups...")
    for i in range(1, 4):
        step_data = {
            'session_id': 'test-backup-1',
            'step_num': i,
            'message': f'Step {i}',
        }
        backup_manager.save_step_backup('test-backup-1', step_data)
    
    # Test recovery
    print("Recovering from backup...")
    recovered_task, recovered_steps = backup_manager.recover_from_backup('test-backup-1')
    assert recovered_task is not None
    assert len(recovered_steps) == 3
    print(f"  Recovered task and {len(recovered_steps)} steps")
    
    # Test cleanup
    print("Cleaning up backup...")
    backup_manager.cleanup_backup('test-backup-1')
    assert not backup_manager.has_backup('test-backup-1')
    
    print("✅ Backup manager tests passed!")


def test_task_executor():
    """Test task executor."""
    print("\n" + "="*60)
    print("Testing Task Executor")
    print("="*60)
    
    # Setup
    test_db = "logs/test_executor.db"
    Path(test_db).unlink(missing_ok=True)
    
    pool = ConnectionPool(test_db, pool_size=3)
    task_repo = TaskRepository(pool)
    step_repo = StepRepository(pool)
    backup_manager = BackupManager("logs/test_executor_backup")
    
    # Create task data
    task_data = TaskData.create(
        description="Test executor task",
        user_id="test_user"
    )
    
    # Create executor
    print("Creating task executor...")
    executor = TaskExecutor(task_data, task_repo, step_repo, backup_manager)
    
    # Start task
    print("Starting task...")
    executor.start()
    assert executor.get_current_state() == TaskState.RUNNING
    print(f"  Task state: {executor.get_current_state()}")
    
    # Simulate steps
    print("Simulating steps...")
    for i in range(1, 4):
        executor.on_step_completed(
            step_num=i,
            screenshot_path=f"/path/to/screenshot_{i}.png",
            screenshot_analysis=f"Analysis {i}",
            action={"type": "tap"},
            action_params={"x": 100, "y": 200},
            execution_time=0.5,
            success=True,
            message=f"Step {i} completed",
            thinking=f"Thinking {i}"
        )
        time.sleep(0.1)  # Small delay
        print(f"  Completed step {i}")
    
    # Complete task
    print("Completing task...")
    executor.on_task_completed(success=True)
    assert executor.get_current_state() == TaskState.SUCCESS
    print(f"  Final state: {executor.get_current_state()}")
    print(f"  Total steps: {executor.get_step_count()}")
    
    # Verify in database
    print("Verifying database...")
    steps = step_repo.get_steps_for_session(task_data.session_id)
    assert len(steps) == 3
    print(f"  Found {len(steps)} steps in database")
    
    # Cleanup
    pool.close_all()
    
    print("✅ Task executor tests passed!")


def test_stop_functionality():
    """Test stop functionality."""
    print("\n" + "="*60)
    print("Testing Stop Functionality")
    print("="*60)
    
    # Setup
    test_db = "logs/test_stop.db"
    Path(test_db).unlink(missing_ok=True)
    
    pool = ConnectionPool(test_db, pool_size=3)
    task_repo = TaskRepository(pool)
    step_repo = StepRepository(pool)
    backup_manager = BackupManager("logs/test_stop_backup")
    
    # Create task
    task_data = TaskData.create(description="Test stop task")
    executor = TaskExecutor(task_data, task_repo, step_repo, backup_manager)
    
    # Start task
    print("Starting task...")
    executor.start()
    
    # Add some steps
    print("Adding steps...")
    for i in range(1, 3):
        executor.on_step_completed(
            step_num=i,
            screenshot_path=None,
            screenshot_analysis=None,
            action=None,
            action_params=None,
            execution_time=0.5,
            success=True,
            message=f"Step {i}",
            thinking=None
        )
        time.sleep(0.05)
    
    # Stop task
    print("Stopping task...")
    executor.stop()
    time.sleep(0.2)  # Wait for finalization
    
    # Verify state
    print(f"  Final state: {executor.get_current_state()}")
    assert executor.get_current_state() == TaskState.STOPPED
    
    # Verify steps saved
    steps = step_repo.get_steps_for_session(task_data.session_id)
    print(f"  Steps saved: {len(steps)}")
    assert len(steps) == 2
    
    # Cleanup
    pool.close_all()
    
    print("✅ Stop functionality tests passed!")


def test_crash_recovery():
    """Test crash recovery."""
    print("\n" + "="*60)
    print("Testing Crash Recovery")
    print("="*60)
    
    # Setup
    test_db = "logs/test_crash.db"
    Path(test_db).unlink(missing_ok=True)
    
    pool = ConnectionPool(test_db, pool_size=3)
    task_repo = TaskRepository(pool)
    step_repo = StepRepository(pool)
    backup_manager = BackupManager("logs/test_crash_backup")
    
    # Create a "crashed" task (RUNNING state but not finished)
    print("Creating crashed task...")
    task_data = TaskData.create(description="Crashed task")
    task_repo.create_task(task_data)
    task_repo.update_task_state(task_data.session_id, TaskState.RUNNING)
    
    # Add some steps
    for i in range(1, 3):
        step_data = StepData(
            session_id=task_data.session_id,
            step_num=i,
            message=f"Step {i}",
            success=True
        )
        step_repo.insert_step(step_data)
    
    # Simulate crash recovery
    print("Running crash recovery...")
    recovered = recover_crashed_tasks(task_repo, step_repo, backup_manager)
    print(f"  Recovered {len(recovered)} tasks")
    
    # Verify task marked as CRASHED
    tasks = task_repo.find_tasks_by_states([TaskState.CRASHED])
    assert len(tasks) == 1
    assert tasks[0]['session_id'] == task_data.session_id
    print(f"  Task marked as CRASHED")
    
    # Cleanup
    pool.close_all()
    
    print("✅ Crash recovery tests passed!")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Phase 1 & Phase 2 Component Tests")
    print("="*60)
    
    try:
        test_state_machine()
        test_repositories()
        test_backup_manager()
        test_task_executor()
        test_stop_functionality()
        test_crash_recovery()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        
    except Exception as e:
        print("\n" + "="*60)
        print(f"❌ TEST FAILED: {e}")
        print("="*60)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
