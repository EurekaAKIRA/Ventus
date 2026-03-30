Feature: exec_demo
  Background: 分析结果来自当前需求文档
    Given 已加载当前任务的需求说明

  # priority: P0
  Scenario: 用户登录后进入用户中心并看到昵称
    Given 用户登录后进入用户中心并看到昵称
    When 用户登录后进入用户中心并看到昵称
    Then 用户登录后进入用户中心并看到昵称
