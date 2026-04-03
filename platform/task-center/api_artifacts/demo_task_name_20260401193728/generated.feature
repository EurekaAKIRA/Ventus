Feature: demo_task_name
  Background: 分析结果来自当前需求文档
    Given 已加载当前任务的需求说明

  # priority: P2
  Scenario: Execute the core business action
    Given Start from a valid API entry point
    When Execute the core business action
    Then System returns an observable result aligned with the requirement
