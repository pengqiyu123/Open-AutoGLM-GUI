# Implementation Plan

## Phase 1: Mental Shortcut System (First Stage)

- [x] 1. Set up database schema for mental shortcuts





  - [x] 1.1 Add mental_shortcuts table creation to database initialization


    - Create table with all required fields (app, scene, element, coords, etc.)
    - Add indexes for app, app+scene, confidence
    - _Requirements: 2.1, 2.3_
  - [ ]* 1.2 Write property test for database schema
    - **Property 5: Shortcut deduplication**
    - **Validates: Requirements 2.1, 2.2, 2.3**

- [x] 2. Implement MentalShortcut data model



  - [x] 2.1 Create MentalShortcut dataclass in `gui/utils/mental_shortcut.py`


    - Define all fields with proper types and defaults
    - Add JSON serialization methods for coords and variance
    - _Requirements: 2.1_
  - [ ]* 2.2 Write unit tests for MentalShortcut serialization
    - Test JSON round-trip for coords and variance
    - _Requirements: 2.1_

- [x] 3. Implement ThinkingExtractor



  - [x] 3.1 Create `gui/utils/thinking_extractor.py` with ThinkingExtractor class


    - Implement extract_from_step() method
    - Implement _extract_coords_from_action() with priority logic
    - Implement _extract_coords_from_thinking() with regex patterns
    - Implement _extract_location_hint() with position patterns
    - Implement _extract_element_name() with UI element patterns
    - Implement _calculate_confidence() with source weights
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 6.1, 6.2, 6.3, 6.4, 6.5_
  - [ ]* 3.2 Write property test for coordinate extraction priority
    - **Property 1: Action coordinates have highest priority**
    - **Validates: Requirements 1.1, 1.2**
  - [ ]* 3.3 Write property test for confidence decay
    - **Property 2: Confidence decay by source**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**
  - [ ]* 3.4 Write property test for extraction error handling
    - **Property 11: Error handling - extraction failure**
    - **Validates: Requirements 8.2**

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement MentalShortcutRepository



  - [x] 5.1 Create `gui/utils/mental_shortcut_repository.py` with repository class


    - Implement __init__() with table creation
    - Implement save() method
    - Implement find_by_app() method
    - Implement find_by_app_scene() method
    - Implement find_or_create() with deduplication logic
    - Implement update_usage() method
    - Implement update_coords_variance() with standard deviation calculation
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 7.1, 7.3, 7.4_
  - [ ]* 5.2 Write property test for query filtering
    - **Property 6: Query filtering correctness**
    - **Validates: Requirements 2.4**
  - [ ]* 5.3 Write property test for variance calculation
    - **Property 10: Variance calculation correctness**
    - **Validates: Requirements 7.1, 7.4**

- [x] 6. Implement ShortcutQualityController



  - [x] 6.1 Create `gui/utils/shortcut_quality_controller.py` with controller class


    - Implement __init__() with configurable learning_period
    - Implement validate_shortcut() with all threshold checks
    - Implement should_inject() with context matching
    - Implement is_in_learning_period() check
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 7.2_
  - [ ]* 6.2 Write property test for learning period
    - **Property 3: Learning period prevents injection**
    - **Validates: Requirements 3.1**
  - [ ]* 6.3 Write property test for validation thresholds
    - **Property 4: Validation thresholds are enforced**
    - **Validates: Requirements 3.2, 3.3, 3.4, 3.5**

- [ ] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement ShortcutInjector



  - [x] 8.1 Create `gui/utils/shortcut_injector.py` with injector class


    - Implement __init__() with repository and quality_controller
    - Implement build_shortcut_prompt() with step-based logic
    - Implement _build_step1_prompt() for task overview
    - Implement _build_step2_3_prompt() for current step guidance
    - Implement _build_step4_plus_prompt() for element positions
    - Implement _format_shortcuts() with 3-item limit
    - Implement _add_disclaimer() method
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_
  - [ ]* 8.2 Write property test for step-based prompt content
    - **Property 7: Step-based prompt content**
    - **Validates: Requirements 4.4**
  - [ ]* 8.3 Write property test for shortcut limit
    - **Property 8: Shortcut limit enforcement**
    - **Validates: Requirements 4.5**
  - [ ]* 8.4 Write property test for disclaimer
    - **Property 9: Disclaimer always present**
    - **Validates: Requirements 4.6**
  - [ ]* 8.5 Write property test for injection error handling
    - **Property 12: Error handling - injection failure**
    - **Validates: Requirements 8.3**

- [x] 9. Integrate with AgentRunner



  - [x] 9.1 Modify `gui/utils/agent_runner.py` to initialize shortcut components
    - Add ThinkingExtractor, MentalShortcutRepository, QualityController, ShortcutInjector
    - Initialize in __init__() method
    - _Requirements: 5.1_
  - [x] 9.2 Add shortcut extraction on step success
    - Call ThinkingExtractor.extract_from_step() after successful step
    - Call MentalShortcutRepository.find_or_create() to save shortcut
    - Wrap in try-except for error handling
    - _Requirements: 5.2, 5.5_
  - [x] 9.3 Add shortcut injection to prompt building
    - Call ShortcutInjector.build_shortcut_prompt() in _build_enhanced_prompt()
    - Merge shortcut prompt with existing prompt
    - Wrap in try-except for error handling
    - _Requirements: 5.3, 5.6_
  - [x] 9.4 Add statistics update on step completion
    - Call MentalShortcutRepository.update_usage() after step completes
    - Pass success/failure status
    - _Requirements: 5.4_
  - [ ]* 9.5 Write integration tests for AgentRunner
    - Test extraction on step success
    - Test injection in prompt building
    - Test error handling and fallback
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 10. Final Checkpoint - Ensure all tests pass





  - Ensure all tests pass, ask the user if questions arise.

