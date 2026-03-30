Feature: smoke_test
  Background: 分析结果来自当前需求文档
    Given 已加载当前任务的需求说明

  # priority: P1
  Scenario: 用户打开首页后应看到搜索框和标题
    Given Start from a valid API entry point
    When 用户打开首页后应看到搜索框和标题
    Then System returns an observable result aligned with the requirement
