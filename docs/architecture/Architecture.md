# DataInsight Agent Architecture

## 1. 架构目标

DataInsight Agent 的系统架构目标是支持一个完整的 AI 分析搭子工作流：

```text
项目
↓
数据接入
↓
数据理解
↓
数据质量
↓
探索分析
↓
业务分析
↓
Agent发现
↓
报告生成
↓
项目记忆沉淀
```

该系统不是单纯的 EDA 工具，而是面向周报/月报场景的 AI Analyst Workspace。

---

## 2. 总体架构图

```text
DataInsight Agent
│
├── Project Workspace
│   │
│   ├── Data Source Layer
│   │   ├── File Upload
│   │   ├── CSV Reader
│   │   ├── Excel Reader
│   │   └── Multi-table Loader
│   │
│   ├── Data Understanding Layer
│   │   ├── Field Mapping Engine
│   │   ├── Table Relationship Engine
│   │   └── KPI Definition Engine
│   │
│   ├── Data Quality Layer
│   │   └── Data Quality Engine
│   │
│   ├── Analysis Layer
│   │   ├── Exploration Engine
│   │   ├── Business Analysis Engine
│   │   └── Business QA Engine
│   │
│   ├── Agent Layer
│   │   ├── Analysis Workflow Engine
│   │   └── Agent Discovery Engine
│   │
│   ├── Report Layer
│   │   └── Report Generation Engine
│   │
│   └── Memory Layer
│       └── Project Memory Engine
```

---

## 3. 核心数据流

```text
用户上传数据
↓
Data Source Layer 读取文件
↓
Field Mapping Engine 识别字段含义
↓
用户确认字段映射
↓
Table Relationship Engine 识别表关联
↓
用户确认表关联
↓
KPI Definition Engine 识别 KPI
↓
用户确认 KPI
↓
Data Quality Engine 检查数据质量
↓
Exploration Engine 生成探索分析
↓
Business Analysis Engine 生成业务分析
↓
Agent Discovery Engine 主动发现异常变化
↓
Business QA Engine 支持自然语言追问
↓
Report Generation Engine 生成报告草稿
↓
Project Memory Engine 保存项目配置和历史记录
```

---

## 4. 模块关系图

```text
                 ┌─────────────────────┐
                 │   Project Memory     │
                 │       Engine         │
                 └──────────┬──────────┘
                            │
                            │ 提供历史配置
                            ↓
┌──────────────┐     ┌───────────────┐     ┌───────────────┐
│ Data Source  │ --> │ Field Mapping │ --> │ Relationship  │
│    Layer     │     │    Engine     │     │    Engine     │
└──────────────┘     └───────────────┘     └───────────────┘
                                                   │
                                                   ↓
                                         ┌─────────────────┐
                                         │ KPI Definition  │
                                         │     Engine      │
                                         └────────┬────────┘
                                                  │
                                                  ↓
                                         ┌─────────────────┐
                                         │ Data Quality    │
                                         │     Engine      │
                                         └────────┬────────┘
                                                  │
                                                  ↓
                                         ┌─────────────────┐
                                         │ Exploration     │
                                         │    Engine       │
                                         └────────┬────────┘
                                                  │
                                                  ↓
                                         ┌─────────────────┐
                                         │ Business        │
                                         │ Analysis Engine │
                                         └────────┬────────┘
                                                  │
                     ┌────────────────────────────┴─────────────────────┐
                     ↓                                                  ↓
          ┌─────────────────────┐                          ┌─────────────────────┐
          │ Agent Discovery     │                          │ Business QA Engine  │
          │      Engine         │                          │                     │
          └──────────┬──────────┘                          └──────────┬──────────┘
                     │                                                │
                     └────────────────────┬───────────────────────────┘
                                          ↓
                                ┌─────────────────────┐
                                │ Report Generation   │
                                │      Engine         │
                                └─────────────────────┘
```

---

## 5. 分层说明

## 5.1 Project Workspace

Project Workspace 是用户实际工作的空间。

一个项目代表一个持续分析主题，例如：

* 淘宝销售分析
* 华东销售周报
* 用户增长分析

周报、月报、季报只是同一项目下的不同输出。

---

## 5.2 Data Source Layer

负责读取用户上传的数据。

支持：

* CSV
* Excel
* 多文件上传
* 多 Sheet 读取

输出：

```text
raw_tables
```

每张表包含：

* 表名
* 字段
* 数据内容
* 基础元数据

---

## 5.3 Data Understanding Layer

负责让 Agent 理解数据。

包含：

### Field Mapping Engine

识别字段业务含义。

例如：

```text
gmv_amt → 销售额
trade_date → 日期
province → 区域
```

---

### Table Relationship Engine

识别多表关联关系。

例如：

```text
订单表.user_id = 用户表.user_id
订单表.product_id = 商品表.product_id
```

---

### KPI Definition Engine

识别业务指标定义。

例如：

```text
销售额 = SUM(gmv_amt)
订单数 = COUNT_DISTINCT(order_id)
客单价 = 销售额 / 客户数
```

---

## 5.4 Data Quality Layer

负责判断数据是否适合继续分析。

检查：

* 缺失值
* 重复值
* 异常值
* ID字段
* 日期异常
* 数据类型异常
* 数据量异常

输出：

```text
data_quality_report
```

---

## 5.5 Analysis Layer

负责生成分析结果。

包含：

### Exploration Engine

用于理解数据结构。

包括：

* 数值分析
* 类别分析
* 相关分析

---

### Business Analysis Engine

用于回答常见业务问题。

包括：

* 时间趋势
* 环比
* 同比
* Top N
* 维度对比

---

### Business QA Engine

用于自然语言业务问答。

包括：

* 基础查询
* 业务规则查询
* 分析问答
* 多轮追问

---

## 5.6 Agent Layer

负责让 Agent 从“工具”变成“分析搭子”。

### Analysis Workflow Engine

负责引导用户完成完整分析流程。

例如：

```text
上传数据
↓
确认字段
↓
确认KPI
↓
检查质量
↓
分析业务
↓
生成报告
```

---

### Agent Discovery Engine

负责主动发现值得关注的问题。

例如：

* 异常增长
* 异常下降
* 贡献变化
* 结构变化
* Top变化

---

## 5.7 Report Layer

负责生成可编辑报告初稿。

支持：

* 周报
* 月报
* Word
* PPT
* 模板导出

报告不是最终成品，而是 80% 初稿。

---

## 5.8 Memory Layer

负责保存项目级记忆。

保存内容：

* 字段映射
* 表关联
* KPI定义
* 报告偏好
* 历史报告
* 历史发现

项目记忆只属于当前项目，不跨项目共享。

---

## 6. 模块输入输出

| 模块                        | 输入                                            | 输出                  |
| ------------------------- | --------------------------------------------- | ------------------- |
| Data Source Layer         | 用户上传文件                                        | raw_tables          |
| Field Mapping Engine      | raw_tables, project_memory                    | field_mappings      |
| Table Relationship Engine | raw_tables, field_mappings, project_memory    | table_relationships |
| KPI Definition Engine     | field_mappings, relationships, project_memory | kpi_definitions     |
| Data Quality Engine       | raw_tables, kpi_definitions                   | data_quality_report |
| Exploration Engine        | prepared_dataset                              | exploration_results |
| Business Analysis Engine  | prepared_dataset, kpi_definitions             | business_results    |
| Agent Discovery Engine    | business_results, historical_results          | discoveries         |
| Business QA Engine        | user_question, project_context                | qa_result           |
| Report Generation Engine  | discoveries, business_results, user_edits     | report_draft        |
| Project Memory Engine     | confirmed_configs, reports                    | project_memory      |

---

## 7. 状态管理

系统至少需要维护以下状态：

```text
current_project

raw_tables

prepared_dataset

field_mappings

table_relationships

kpi_definitions

data_quality_report

exploration_results

business_results

discoveries

report_draft

project_memory
```

---

## 8. 推荐目录结构

```text
DataInsight-Agent
│
├── app.py
├── requirements.txt
├── README.md
│
├── docs
│   ├── Architecture.md
│   ├── PRD_v0.1_Product_Positioning.md
│   ├── PRD_v0.2_Project_and_Page_Structure.md
│   └── specs
│       ├── Analysis_Workflow_Engine.md
│       ├── Agent_Discovery_Engine.md
│       ├── Project_Memory_Engine.md
│       ├── Business_QA_Engine.md
│       ├── Report_Generation_Engine.md
│       ├── KPI_Definition_Engine.md
│       ├── Table_Relationship_Engine.md
│       ├── Field_Mapping_Engine.md
│       └── Data_Quality_Engine.md
│
├── src
│   ├── pages
│   │   ├── project_home.py
│   │   ├── data_source_page.py
│   │   ├── data_quality_page.py
│   │   ├── exploration_page.py
│   │   ├── business_analysis_page.py
│   │   ├── agent_discovery_page.py
│   │   ├── report_center_page.py
│   │   └── project_memory_page.py
│   │
│   ├── engines
│   │   ├── field_mapping_engine.py
│   │   ├── table_relationship_engine.py
│   │   ├── kpi_definition_engine.py
│   │   ├── data_quality_engine.py
│   │   ├── exploration_engine.py
│   │   ├── business_analysis_engine.py
│   │   ├── business_qa_engine.py
│   │   ├── agent_discovery_engine.py
│   │   ├── report_generation_engine.py
│   │   └── project_memory_engine.py
│   │
│   ├── services
│   │   ├── file_service.py
│   │   ├── ai_service.py
│   │   ├── export_service.py
│   │   └── project_service.py
│   │
│   ├── storage
│   │   ├── sqlite_store.py
│   │   └── file_store.py
│   │
│   └── models
│       ├── project.py
│       ├── table_schema.py
│       ├── kpi.py
│       ├── discovery.py
│       └── report.py
```

---

## 9. MVP架构边界

MVP支持：

* 本地项目
* 本地 SQLite 存储
* Excel / CSV 上传
* 多表分析
* 项目级记忆
* Word / PPT 导出

MVP不支持：

* 多人协作
* 云端同步
* 权限管理
* 企业级数据仓库
* 实时数据库连接
* 在线PPT拖拽编辑
* 预测模型

---

## 10. 架构原则

### 原则1

项目优先，而不是文件优先。

---

### 原则2

所有关键推断必须可确认。

---

### 原则3

所有 AI 输出必须可追溯。

---

### 原则4

所有报告都是可编辑初稿。

---

### 原则5

Agent负责发现问题，不负责替用户背锅。
