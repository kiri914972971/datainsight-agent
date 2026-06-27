# Codex_Architecture_Refactor_Prompt.md

## 任务背景

当前项目已经完成部分功能开发，但项目结构仍以功能堆叠和页面开发为主。

现需要根据项目文档体系，对整个项目进行架构重构。

请严格按照 docs 目录中的文档执行：

* Architecture.md
* MVP_SCOPE.md
* PRD_v0.1_Product_Positioning.md
* PRD_v0.2_Project_and_Page_Structure.md
* docs/specs/*

禁止根据个人理解随意增加功能。

禁止脱离文档重新设计产品。

目标是：

建立一个可持续扩展的 DataInsight Agent 架构。

---

## 产品定位

DataInsight Agent 是一个面向数据分析师的 AI Analyst Workspace。

核心价值：

帮助分析师完成：

数据
↓
分析
↓
发现
↓
报告

的完整工作流程。

不是：

* Power BI替代品
* Tableau替代品
* 数据仓库
* 在线PPT编辑器

---

## 重构目标

将当前项目重构为：

```text
src/
├ pages/
├ engines/
├ services/
├ storage/
├ models/
├ components/
```

架构。

确保：

页面层

业务层

存储层

AI层

完全解耦。

---

## 目录结构要求

```text
src/

├ pages/
│
│ ├ project_home.py
│ ├ data_source_page.py
│ ├ data_quality_page.py
│ ├ exploration_page.py
│ ├ business_analysis_page.py
│ ├ agent_discovery_page.py
│ ├ report_center_page.py
│ └ project_memory_page.py
│
├ engines/
│
│ ├ field_mapping_engine.py
│ ├ table_relationship_engine.py
│ ├ kpi_definition_engine.py
│ ├ data_quality_engine.py
│ ├ exploration_engine.py
│ ├ business_analysis_engine.py
│ ├ business_qa_engine.py
│ ├ agent_discovery_engine.py
│ ├ report_generation_engine.py
│ ├ analysis_workflow_engine.py
│ └ project_memory_engine.py
│
├ services/
│
│ ├ file_service.py
│ ├ ai_service.py
│ ├ export_service.py
│ ├ chart_service.py
│ └ project_service.py
│
├ storage/
│
│ ├ sqlite_store.py
│ ├ project_store.py
│ └ file_store.py
│
├ models/
│
│ ├ project.py
│ ├ dataset.py
│ ├ field_mapping.py
│ ├ relationship.py
│ ├ kpi.py
│ ├ discovery.py
│ └ report.py
│
└ components/
```

---

## 第一阶段目标

完成项目级工作空间。

实现：

### Project Workspace

支持：

* 新建项目
* 打开项目
* 删除项目
* 保存项目

项目信息保存至：

SQLite

---

## 第二阶段目标

完成数据理解层。

实现：

### Field Mapping Engine

支持：

* 字段识别
* 字段确认
* 项目记忆

---

### Table Relationship Engine

支持：

* 自动识别关联关系
* 用户确认
* 保存关联关系

---

### KPI Definition Engine

支持：

* KPI自动识别
* 用户确认
* 项目记忆

---

## 第三阶段目标

完成数据质量层。

实现：

### Data Quality Engine

支持：

* 缺失值
* 重复值
* 异常值
* ID识别
* 数据修复

所有逻辑从页面抽离。

放入：

engines/data_quality_engine.py

---

## 第四阶段目标

完成分析层。

实现：

### Exploration Engine

支持：

* 数值分析
* 类别分析
* 相关分析

---

### Business Analysis Engine

支持：

* 时间趋势
* Top N
* 同比
* 环比
* 维度分析

---

## 第五阶段目标

完成 Agent 层。

实现：

### Agent Discovery Engine

支持：

* 异常变化
* 贡献变化
* 结构变化
* Top变化

---

### Analysis Workflow Engine

支持：

分析流程管理：

上传数据
↓
数据理解
↓
数据质量
↓
探索分析
↓
业务分析
↓
报告生成

---

## 第六阶段目标

完成 Business QA Engine。

支持：

### 基础查询

销量最高的5个产品是什么？

---

### 业务规则查询

连续登录天数最长的用户是谁？

哪些商品贡献了80%的销售额？

---

### 分析问答

为什么销量下降？

哪个产品影响最大？

---

支持：

项目上下文

多轮追问

---

## 第七阶段目标

完成 Report Generation Engine。

支持：

### 周报

### 月报

### Word导出

### PPT导出

### 模板上传

---

报告必须支持：

修改文字

修改图表

调整模块

---

禁止实现：

在线PPT编辑器

---

## 项目记忆要求

Project Memory Engine 必须支持：

保存：

* 字段映射
* 表关联
* KPI定义
* 历史报告

项目再次打开时自动恢复。

---

## MVP边界

当前版本明确不实现：

* 预测
* 多人协作
* 权限系统
* 实时数据库
* Power BI替代能力
* Tableau替代能力
* 数据仓库
* 在线PPT编辑器

---

## 输出要求

请先：

1. 分析当前项目结构
2. 给出重构方案
3. 给出文件迁移计划
4. 给出分阶段实施计划

不要直接开始大规模修改代码。

先输出重构设计方案供确认。
