Feature: user_center_demo_v2
  Background: 分析结果来自当前需求文档
    Given 已加载当前任务的需求说明

  # priority: P2
  Scenario: 用户点击“最近订单”后，应跳转到订单列表页
    Given 普通用户登录后进入用户中心页面
    When 用户点击“最近订单”后，应跳转到订单列表页
    Then 页面应显示用户昵称和会员等级

  # priority: P1
  Scenario: 用户在搜索框输入订单号后，应显示匹配的订单结果
    Given 普通用户登录后进入用户中心页面
    When 用户在搜索框输入订单号后，应显示匹配的订单结果
    Then 页面应显示最近订单入口
