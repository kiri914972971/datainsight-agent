# DataInsight Agent PRD v0.2

# 项目结构与页面结构

---

# 1. 产品结构

DataInsight Agent 采用：

```text
首页（项目中心）
↓
项目
↓
分析工作区
```

模式。

用户首先进入项目中心。

然后进入具体项目。

所有分析行为都发生在项目内部。

---

# 2. 首页（项目中心）

首页不直接上传文件。

首页首先展示项目。

原因：

分析师的工作是围绕项目持续进行的，而不是围绕单个文件。

---

## 页面结构

```text
DataInsight Agent

[ 新建项目 ]

最近项目

├ 淘宝销售分析
├ 华东销售周报
├ 用户增长分析
├ 宠物保险市场分析

```

---

## 项目卡片

显示：

```text
项目名称

最近更新时间

数据表数量

历史报告数量

项目描述（可选）
```

例如：

```text
淘宝销售分析

更新时间：
2025-09-10

数据表：
4张

历史报告：
12份
```

---

## 项目操作

支持：

```text
打开项目

重命名

复制项目

删除项目
```

---

# 3. 新建项目

点击：

```text
新建项目
```

进入向导。

---

## Step1

项目基本信息

```text
项目名称

项目描述

项目类型
```

项目类型：

```text
销售分析

运营分析

用户分析

财务分析

自定义
```

---

## Step2

导入数据

支持：

```text
Excel

CSV

多个文件同时上传
```

---

## Step3

Agent自动识别

```text
数据表

字段

主键

关联关系
```

生成候选结果。

---

## Step4

用户确认

确认：

```text
字段映射

表关联

KPI定义
```

---

## Step5

创建项目

进入分析工作区。

---

# 4. 项目工作区

结构：

```text
项目名称

├ 数据源
├ 数据质量
├ 探索分析
├ 业务分析
├ Agent发现
├ 报告中心
├ 项目记忆
```

---

# 5. 数据源

目标：

管理项目中的所有数据。

---

## 功能

### 数据表列表

显示：

```text
订单表

用户表

商品表

区域表
```

---

### 表结构

显示：

```text
字段

类型

缺失率

唯一值数量
```

---

### 表关联

显示：

```text
订单.user_id
=
用户.user_id

订单.product_id
=
商品.product_id
```

---

支持修改。

---

### KPI定义

显示：

```text
销售额

订单数

客单价

客户数
```

以及计算逻辑。

例如：

```text
订单数
=
order_id去重
```

支持修改。

---

# 6. 数据质量

目标：

发现数据问题。

不是直接分析业务。

---

## 模块

### 缺失值

显示：

```text
缺失数量

缺失率

影响等级
```

---

### 重复值

显示：

```text
重复行

重复率
```

---

### 异常值

显示：

```text
异常值数量

异常值占比
```

支持：

```text
查看明细
```

---

### ID识别

自动识别：

```text
用户ID

订单ID

商品ID
```

避免进入统计分析。

---

### 数据修复

支持：

```text
缺失值处理

重复值处理

异常值处理
```

---

# 7. 探索分析

目标：

理解数据结构。

---

## 数值分析

显示：

```text
均值

中位数

标准差

偏度

峰度
```

以及：

```text
直方图

箱线图
```

---

## 类别分析

显示：

```text
TopN

频次

占比
```

以及：

```text
柱状图

饼图
```

---

## 相关分析

显示：

```text
相关矩阵

热力图
```

---

# 8. 业务分析

目标：

回答业务问题。

---

## 时间趋势

支持：

```text
日

周

月

季度

年
```

自动生成：

```text
趋势图

环比

同比
```

---

## 维度对比

用户选择：

```text
维度

指标
```

例如：

```text
区域 × 销售额

产品 × 销售额

销售人员 × 成交客户数
```

---

## Top N

自动分析：

```text
Top产品

Top区域

Top销售
```

---

## 业务问答

用户输入：

```text
近一个月成交金额最高的销售是谁？

销量最高的5个产品是什么？
```

Agent返回：

```text
表格

图表

解释
```

---

# 9. Agent发现

产品核心模块。

Agent主动发现值得分析的变化。

---

## 异常变化

例如：

```text
华东销量下降18%
```

---

## 贡献变化

例如：

```text
产品A贡献了72%的下降
```

---

## 结构变化

例如：

```text
华东占比从40%提升到60%
```

---

## Top变化

例如：

```text
产品B首次进入Top3
```

---

用户可以：

```text
加入报告

忽略

继续追问
```

---

# 10. 报告中心

目标：

生成分析草稿。

不是最终成品。

---

## 周报

自动生成：

```text
关键发现

风险

建议
```

---

## 月报

自动生成：

```text
数据概况

业务表现

问题分析

建议
```

---

## 编辑器

支持：

```text
修改文字

修改图表类型

调整TopN
```

不支持：

```text
自由拖拽排版
```

---

## 导出

支持：

```text
Word

PPT
```

---

# 11. 项目记忆

保存：

```text
字段映射

表关联

KPI定义

常用图表

历史报告
```

---

Agent下次打开项目时自动继承。

---

# 12. 页面导航原则

原则：

```text
数据源
↓
数据质量
↓
探索分析
↓
业务分析
↓
Agent发现
↓
报告中心
```

形成完整分析链路。

避免功能重复。

---

# 13. 数据埋点与产品指标

## 13.1 埋点目标

数据埋点用于评估 DataInsight Agent 的产品工作流是否顺畅、核心功能是否被使用、数据处理与报告导出是否稳定，以及 AI 辅助开发过程中是否引入产品回归风险。

埋点不用于收集原始用户数据，不记录原始数据行，不记录敏感单元格值，也不作为用户数据内容分析能力的一部分。

MVP 阶段重点回答：

* 用户是否能完成从上传数据到生成报告的主流程。
* 数据质量、数据建模、业务分析、报告导出等关键能力是否被实际使用。
* 清洗、建模、导出等高风险操作是否成功完成。
* 新功能或 AI 辅助改动是否导致完成率下降、错误率上升或空结果增加。

---

## 13.2 核心产品指标

| 指标 | Definition | Calculation method | Trigger or related events | Product meaning |
| --- | --- | --- | --- | --- |
| 分析任务完成率 | 用户在一个项目会话中完成从数据接入到业务分析或报告导出的比例。 | 完成分析任务的 session 数 / 启动分析任务的 session 数。MVP 可将触发 `dataset_uploaded` 后又触发 `cleaned_dataset_generated`、业务分析使用事件或 `report_export_success` 的 session 视为完成。 | `dataset_uploaded`、`dataset_selected`、业务分析使用事件、`cleaned_dataset_generated`、`report_export_success` | 衡量 DataInsight Agent 是否真正帮助用户走完整个分析工作流。 |
| 数据处理完成率 | 用户进入数据质量处理后，成功生成可继续分析的清洗后数据集的比例。 | `cleaned_dataset_generated.success=true` 次数 / 进入数据质量处理并产生处理计划或预览的 session 数。 | `data_quality_viewed`、`missing_value_plan_added`、`duplicate_plan_added`、`outlier_plan_added`、`cleaned_dataset_generated` | 衡量数据质量中心是否能把问题识别转化为可用数据产物。 |
| 多表建模使用率 | 上传或选择多表数据的项目中，用户进入表关系/分析数据集建模流程的比例。 | 使用多表建模相关功能的 project 数 / 具备多表数据的 project 数。MVP 可基于 `dataset_uploaded` 的 `dataset_type=multi_table` 与后续表关系、分析数据集生成事件统计。 | `dataset_uploaded`、`dataset_selected`、表关系确认事件、分析数据集生成事件 | 衡量多表能力是否被用户理解并用于真实分析。 |
| 报告导出成功率 | 用户点击报告导出后成功生成导出文件的比例。 | `report_export_success` 次数 / `report_export_clicked` 次数。按导出格式、项目类型、数据集类型拆分观察。 | `report_export_clicked`、`report_export_success`、`report_export_failed` | 衡量交付导出能力是否可靠，是周报/月报场景的关键闭环指标。 |

---

## 13.3 功能使用指标

MVP 需要覆盖以下功能使用指标：

| 指标 | 说明 | 推荐统计方式 |
| --- | --- | --- |
| Module visits | 用户访问一级工作区模块的次数与去重 session 数。 | 记录模块名称、来源模块、停留时长。 |
| Data Quality Center subtab visits | 用户访问数据质量中心各子页签的次数。 | 记录 `subtab_name`，例如 missing_values、duplicates、id_detection、outliers。 |
| Missing value plan actions | 用户新增、移除、预览缺失值处理方案的次数。 | 统计 plan add/remove/preview 事件，并按处理策略拆分。 |
| Duplicate handling actions | 用户新增或预览重复值处理方案的次数。 | 统计 duplicate plan add/preview，并记录 duplicate_count。 |
| ID override actions | 用户手动覆盖或重置 ID 字段识别结果的次数。 | 统计 override applied/reset，并记录字段数量。 |
| Outlier handling actions | 用户选择异常值字段、新增处理方案、生成预览的次数。 | 统计 outlier selected/plan/preview，并记录方法与异常值数量。 |
| Cleaned dataset generation | 用户生成清洗后数据集的次数与成功率。 | 统计 `cleaned_dataset_generated`，记录行列数变化和处理计划数量。 |
| Business analysis usage | 用户使用业务分析、业务问答、趋势、Top N、维度对比等能力的次数。 | 记录分析类型、输入数据集类型、结果状态。 |
| Report export usage | 用户点击、成功、失败导出报告的次数。 | 记录导出格式、报告类型、成功状态、失败原因。 |

---

## 13.4 质量与稳定性指标

| 指标 | Definition | Calculation method | Product meaning |
| --- | --- | --- | --- |
| 功能执行成功率 | 某类功能动作成功完成的比例。 | `success=true` 事件数 / 同类事件总数。可按 missing、duplicate、outlier、export 等 event group 统计。 | 判断关键能力是否稳定可用。 |
| 错误率 | 某类功能动作产生错误的比例。 | `success=false` 或带 `error_type` 的事件数 / 同类事件总数。 | 帮助定位回归、异常输入和边界条件问题。 |
| 数据处理耗时 | 数据质量检查、预览生成、清洗数据集生成、报告导出的耗时。 | 统计 `duration_ms` 的 P50、P90、P95。 | 衡量用户等待成本和性能退化风险。 |
| Empty result rate | 用户触发分析或预览后得到空结果的比例。仅在业务分析、预览、异常检测等可能返回空结果的功能中统计。 | `result_empty=true` 次数 / 对应功能执行次数。 | 判断分析逻辑是否过严、数据选择是否错误，或 AI 辅助改动是否导致结果不可用。 |

---

## 13.5 MVP 事件字典

### Dataset events

| event_name | trigger timing | key properties | success/error fields |
| --- | --- | --- | --- |
| `dataset_uploaded` | 用户上传 CSV、Excel 或多文件数据并完成解析后。 | `file_count`、`dataset_type`、`row_count`、`column_count`、`table_count`、`file_ext` | `success`、`error_type`、`duration_ms` |
| `dataset_selected` | 用户在项目数据集中切换当前数据集时。 | `previous_dataset_id`、`dataset_id`、`dataset_type`、`row_count`、`column_count` | `success`、`error_type` |
| `dataset_previewed` | 用户查看前20行、后20行、随机20行或字段信息预览时。 | `preview_type`、`dataset_id`、`row_count`、`column_count` | `success`、`error_type`、`duration_ms`、`result_empty` |

### Data quality events

| event_name | trigger timing | key properties | success/error fields |
| --- | --- | --- | --- |
| `data_quality_viewed` | 用户进入数据质量中心时。 | `dataset_id`、`dataset_type`、`row_count`、`column_count`、`quality_score` | `success`、`error_type`、`duration_ms` |
| `data_quality_subtab_viewed` | 用户切换数据质量子页签时。 | `subtab_name`、`dataset_id`、`missing_count`、`duplicate_count`、`outlier_count` | `success`、`error_type` |

### Missing value events

| event_name | trigger timing | key properties | success/error fields |
| --- | --- | --- | --- |
| `missing_value_plan_added` | 用户为字段新增缺失值处理方案时。 | `field_name`、`field_type`、`strategy`、`missing_count`、`missing_rate` | `success`、`error_type` |
| `missing_value_plan_removed` | 用户移除缺失值处理方案时。 | `field_name`、`strategy`、`remaining_plan_count` | `success`、`error_type` |
| `missing_value_preview_generated` | 用户生成缺失值处理预览时。 | `plan_count`、`affected_field_count`、`affected_row_count` | `success`、`error_type`、`duration_ms`、`result_empty` |

### Duplicate events

| event_name | trigger timing | key properties | success/error fields |
| --- | --- | --- | --- |
| `duplicate_plan_added` | 用户新增重复值处理方案时。 | `duplicate_scope`、`key_field_count`、`duplicate_count`、`strategy` | `success`、`error_type` |
| `duplicate_preview_generated` | 用户生成重复值处理预览时。 | `plan_count`、`duplicate_count`、`affected_row_count` | `success`、`error_type`、`duration_ms`、`result_empty` |

### ID override events

| event_name | trigger timing | key properties | success/error fields |
| --- | --- | --- | --- |
| `id_field_override_applied` | 用户手动覆盖 ID 字段识别结果时。 | `field_name`、`previous_role`、`new_role`、`confidence` | `success`、`error_type` |
| `id_field_override_reset` | 用户重置 ID 字段覆盖结果时。 | `field_name`、`reset_to_role` | `success`、`error_type` |

### Outlier events

| event_name | trigger timing | key properties | success/error fields |
| --- | --- | --- | --- |
| `outlier_field_selected` | 用户在异常值分析中选择字段时。 | `field_name`、`field_type`、`method`、`outlier_count`、`outlier_rate` | `success`、`error_type` |
| `outlier_plan_added` | 用户新增异常值处理方案时。 | `field_name`、`method`、`strategy`、`outlier_count` | `success`、`error_type` |
| `outlier_preview_generated` | 用户生成异常值处理预览时。 | `plan_count`、`affected_field_count`、`affected_row_count`、`outlier_count` | `success`、`error_type`、`duration_ms`、`result_empty` |

### Cleaned dataset event

| event_name | trigger timing | key properties | success/error fields |
| --- | --- | --- | --- |
| `cleaned_dataset_generated` | 用户确认处理方案并生成清洗后数据集时。 | `source_dataset_id`、`new_dataset_id`、`plan_count`、`row_count_before`、`row_count_after`、`column_count` | `success`、`error_type`、`duration_ms` |

### Export events

| event_name | trigger timing | key properties | success/error fields |
| --- | --- | --- | --- |
| `report_export_clicked` | 用户点击 Word、PPT 或其他报告导出入口时。 | `report_type`、`export_format`、`dataset_id`、`section_count` | `success` |
| `report_export_success` | 报告文件成功生成后。 | `report_type`、`export_format`、`file_size_bytes`、`section_count` | `success=true`、`duration_ms` |
| `report_export_failed` | 报告导出失败时。 | `report_type`、`export_format`、`section_count` | `success=false`、`error_type`、`duration_ms` |

### Recommended extension events

以下事件不属于 MVP 必须实现的最低集合，但建议在实现核心指标时同步规划：

| event_name | trigger timing | key properties | success/error fields |
| --- | --- | --- | --- |
| `workspace_module_viewed` | 用户访问一级工作区模块时。 | `module_name`、`previous_module_name`、`dataset_id` | `success`、`error_type` |
| `table_relationship_confirmed` | 用户确认或修改多表关系时。 | `table_count`、`relationship_count`、`modified_relationship_count` | `success`、`error_type` |
| `analysis_dataset_generated` | 用户生成多表 Join 后的分析数据集时。 | `source_table_count`、`relationship_count`、`row_count`、`column_count` | `success`、`error_type`、`duration_ms` |
| `business_analysis_started` | 用户启动趋势、Top N、维度对比或业务问答分析时。 | `analysis_type`、`dataset_id`、`dataset_type`、`metric_count`、`dimension_count` | `success` |
| `business_analysis_completed` | 业务分析结果生成后。 | `analysis_type`、`result_row_count`、`chart_count`、`result_empty` | `success`、`error_type`、`duration_ms` |

---

## 13.6 Local MVP tracking design

第一版实现应采用本地 JSONL 事件日志，路径为：

```text
workspace/analytics/events.jsonl
```

每一行代表一个独立事件，便于本地调试、回归排查和后续迁移到数据库或第三方分析平台。

每个事件必须包含通用属性：

| property | 说明 |
| --- | --- |
| `event_id` | 单个事件的唯一 ID。 |
| `event_name` | 事件名称，必须来自 MVP 事件字典或后续扩展字典。 |
| `session_id` | 当前用户会话 ID，用于串联一次分析流程。 |
| `project_id` | 当前项目 ID。 |
| `dataset_id` | 当前数据集 ID；如果事件发生时没有数据集，可为空。 |
| `dataset_type` | 数据集类型，例如 single_table、multi_table、cleaned、joined；如果不可用，可为空。 |
| `timestamp` | 事件发生时间，建议使用 ISO 8601 格式。 |
| `success` | 布尔值，表示该动作是否成功完成。 |
| `error_type` | 失败类型；成功时为空。 |
| `duration_ms` | 有明确执行过程的动作耗时；纯访问事件可为空。 |

事件属性应尽量稳定，避免把 UI 展示文案作为唯一统计字段。涉及模块、子页签、策略、导出格式等枚举值时，应使用可长期维护的英文枚举。

---

## 13.7 Privacy and data safety principles

埋点必须遵守以下原则：

* 不记录原始数据行。
* 不记录敏感单元格值。
* 优先记录聚合元数据，例如 `row_count`、`column_count`、`missing_count`、`duplicate_count`、`outlier_count`。
* MVP 阶段允许记录字段名，用于排查字段识别、ID 覆盖、异常值处理等产品问题。
* 未来企业模式必须支持字段名脱敏或字段名映射，避免在日志中暴露业务敏感字段。
* 本地日志默认只保留在 `workspace/analytics` 内，除非用户明确执行导出，否则不得自动上传或发送到外部服务。
* 错误信息应记录错误类型和错误阶段，避免写入完整异常堆栈中的敏感路径、文件名或数据内容。

---

## 13.8 Future extension

后续可按产品成熟度迁移或扩展到：

* SQLite：适合本地可查询、可聚合的单机分析。
* PostHog：适合产品行为分析、漏斗分析和事件留存。
* Mixpanel：适合更强的用户行为路径和分群分析。
* Cloud database：适合团队版或企业版的集中式使用分析。
* Usage analytics dashboard：在产品内或运维后台展示完成率、错误率、功能使用率、导出成功率和回归风险。

迁移时应保持 MVP 事件字典的 `event_name` 和核心通用属性稳定，避免破坏历史趋势对比。
