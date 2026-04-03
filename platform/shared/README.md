# shared

平台共享基础层。

用于统一存放：

- `schemas/` 协议与结构定义
- `models/` 核心数据模型
- `utils/` 通用工具函数
- `config/runtime_config.json` 平台运行期默认配置（跨模块共享，含 model profiles）

目标是降低各模块之间的重复定义和耦合。
