Feature: migrate_demo
  Background: 分析结果来自当前需求文档
    Given 已加载当前任务的需求说明

  # priority: P2
  Scenario: 用户点击编辑按钮
    Given 用户中心
用户登录后进入个人中心
    When 用户点击编辑按钮
    Then 系统应显示资料编辑表单
