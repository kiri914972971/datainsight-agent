# Module

Analytics Tracking / 数据埋点与产品指标

# Related Documents

- `docs/prd/PRD_v0.2_Project_and_Page_Structure.md`，第 13 节“数据埋点与产品指标”
- `docs/handoff/HANDOFF_STANDARD.md`
- `docs/harness/PRODUCT_RULES.md`

# Module Lifecycle

Testing

# Current Status

Analytics Tracking 的 MVP 已完成本地事件记录、核心流程事件接入和开发者查看工具。
当前实现以本地 JSONL 为唯一持久化方式，不连接外部分析平台。
事件覆盖数据上传、数据集选择、数据质量查看、清洗数据集生成和报告导出主流程。

## 模块目标

Analytics Tracking 用于观察 DataInsight Agent 的核心工作流完成情况、功能使用情况、稳定性和完成率，并为 AI 辅助开发过程中的回归排查提供可检查的产品行为证据。

该模块采用 local-first 设计。事件默认只写入本地工作区，并以隐私保护为边界：记录操作和聚合元数据，不采集原始 dataframe 行或敏感单元格值。

# External Dependencies

- Python 标准库提供 JSON 序列化、UUID、UTC 时间和本地文件读写。
- Streamlit session state 提供当前运行会话内稳定的 `session_id`，并承载事件去重标记。
- Streamlit 提供 Analytics Viewer 的折叠区、指标卡、表格、下载和清空控件。
- Pandas 和项目已有的 Plotly 依赖用于 Viewer 中的事件表格与事件类型分布图。
- 本地文件系统用于保存 `workspace/analytics/events.jsonl`。
- 当前没有 PostHog、Mixpanel、SQLite、云数据库或其他外部分析服务依赖。

# Key Files

## 关键文件

- `docs/prd/PRD_v0.2_Project_and_Page_Structure.md`
  - 第 13 节定义埋点目标、产品指标、MVP 事件字典、本地日志格式、隐私原则和未来扩展方向。

- `src/services/analytics_service.py`
  - 负责生成通用事件字段、管理会话 ID、追加和读取 JSONL、清空日志，以及对部分敏感属性和复杂值进行轻量保护。

- `src/services/analytics_tracking_service.py`
  - 负责安全调用日志服务、会话内事件去重、构造聚合属性，以及为 Analytics Viewer 汇总事件数量、成功率、主流程计数和近期事件。

- `tests/test_analytics_service.py`
  - 覆盖 JSONL 写入和读取、通用字段、清空行为、无网络调用、空上下文和敏感属性脱敏。

- `tests/test_analytics_tracking_service.py`
  - 覆盖安全失败隔离、事件去重、聚合属性、清洗前后计数、事件汇总、事件分布、主流程计数和近期事件表。

- `app.py`
  - 接入当前 MVP 主流程事件，并提供侧边栏摘要和主页面底部的完整 Analytics Viewer。

- `workspace/analytics/events.jsonl`
  - 运行时按需创建的本地事件日志。每行保存一个独立 JSON 事件，不属于版本控制内容。

- `.gitignore`
  - 忽略 `workspace/analytics/*.jsonl` 和 `workspace/analytics/*.log`，防止本地分析日志被提交。

# Implemented Features

## 当前已实现能力

- PRD 已增加第 13 节“数据埋点与产品指标”。
- 已实现本地 JSONL 事件记录器，支持写入、读取、限制读取数量和清空日志。
- 已接入数据上传、数据集选择、数据质量查看、清洗数据集生成和报告导出等 MVP 主流程事件。
- 埋点失败不会阻断用户主流程；事件写入异常会被隔离。
- 已实现 Analytics Viewer，包括侧边栏轻量摘要和主页面全宽详细视图。
- `.gitignore` 已配置本地 analytics JSONL 和日志文件忽略规则。

## PRD 指标体系

PRD 第 13 节定义了以下指标体系：

- 分析任务完成率：衡量一次项目会话能否从数据接入继续到数据处理、业务分析或报告导出。
- 数据处理完成率：衡量进入数据质量流程后成功生成可继续分析的清洗数据集的比例。
- 多表建模使用率：衡量具备多表数据的项目是否使用表关系和分析数据集建模能力。
- 报告导出成功率：以 `report_export_success / report_export_clicked` 衡量导出闭环可靠性。
- 功能使用指标：覆盖模块访问、数据质量子页签、缺失值、重复值、ID 覆盖、异常值、清洗数据集、业务分析和报告导出使用情况。
- 质量与稳定性指标：覆盖功能执行成功率、错误率、数据处理耗时和适用功能的空结果率。

当前 MVP 只实现上述指标所需的一部分主流程事件。多表建模、业务分析和数据质量细粒度操作指标仍属于后续扩展范围。

## 已接入事件列表

| event_name | 当前触发时机 | 主要 properties | 成功与失败行为 |
| --- | --- | --- | --- |
| `dataset_uploaded` | 用户提交 CSV/Excel 文件并完成项目文件保存与数据集注册后。通常按保存结果中的文件或工作表分别记录。 | `file_type`、`dataset_type`、`row_count`、`column_count`、`sheet_count`；失败时记录 `file_count`。 | 成功事件使用 `success=true`。保存或解析流程抛出异常时记录 `success=false`、`error_type=upload_error`。 |
| `dataset_selected` | 用户将上传、追加、清洗或其他已注册项目数据集设为当前分析数据集时。相同项目和数据集指纹在 session state 中去重。 | `dataset_type`、`row_count`、`column_count`；项目与数据集标识位于通用上下文字段。 | 当前只记录成功选择，不单独记录选择失败事件。 |
| `data_quality_viewed` | 数据质量页签内容针对当前数据集完成渲染时。相同项目和数据集在当前会话中只记录一次。 | `dataset_type`、`row_count`、`column_count`、`quality_score`、`missing_total`、`duplicate_count`、`suspected_id_count`、`outlier_field_count`、`outlier_value_count`。 | 当前只记录成功渲染，默认 `success=true`；其语义不是独立的显式点击事件。 |
| `cleaned_dataset_generated` | 用户点击生成清洗数据集并完成 `cleaned_dataset` 创建与注册后。 | `source_dataset_id`、`source_dataset_type`、`cleaned_dataset_id`、缺失值计划步骤数、重复值计划状态、ID 覆盖数、异常值计划步骤数、处理前后行列数。 | 成功时记录 `duration_ms`。失败时记录当前计划摘要、处理前行列数、`success=false`、`error_type=cleaning_error`。 |
| `report_export_clicked` | 对 Excel、Word、PPT 等下载类导出，在用户点击已经生成的下载按钮时记录；对周期报告和管理层摘要等 AI 生成流程，在开始生成前记录。 | `export_type`、`dataset_type`、`has_quality_summary`、`has_charts`；`file_size` 通常为空。 | 作为导出尝试的起点事件，默认 `success=true`，不代表最终文件或内容已经成功生成。 |
| `report_export_success` | 下载按钮被点击且导出内容已生成，或 AI 报告内容成功生成后。 | `export_type`、`dataset_type`、`file_size`、`has_quality_summary`、`has_charts`。 | 记录 `success=true`；可用时记录 `duration_ms`。 |
| `report_export_failed` | 报告文件或 AI 报告内容生成抛出异常时。部分下载类导出失败会按项目、数据集、导出类型和错误指纹在会话内去重。 | `export_type`、`dataset_type`、`has_quality_summary`、`has_charts`、截断后的 `error_message`。 | 记录 `success=false`、`error_type=export_error`；当前并非所有失败分支都记录 `duration_ms`。 |

## 事件文件与格式

事件文件路径：

```text
workspace/analytics/events.jsonl
```

文件采用 JSONL 格式，每一行是一个完整、独立的 JSON 对象。日志目录和文件在第一次成功写入事件时按需创建。

每个事件包含以下通用字段：

| 字段 | 当前含义 |
| --- | --- |
| `event_id` | 事件 UUID。 |
| `event_name` | 稳定的事件名称。 |
| `session_id` | 当前 Streamlit 会话 ID；无 Streamlit 上下文时使用进程内 fallback ID。 |
| `timestamp` | UTC ISO 8601 时间。 |
| `project_id` | 当前项目 ID；不可用时可为空。 |
| `dataset_id` | 当前数据集 ID；不可用时可为空。 |
| `dataset_type` | 当前数据集类型；不可用时可为空。 |
| `success` | 事件对应动作是否成功。 |
| `error_type` | 失败类型；成功事件通常为空。 |
| `duration_ms` | 可计时动作的执行耗时；纯访问或未计时事件可为空。 |
| `properties` | 事件专属的聚合元数据对象。 |

## Analytics Viewer

Analytics Viewer 是开发和调试工具，不是一级产品模块，也不新增主产品页签。

- 侧边栏“开发工具 / Analytics Viewer”折叠区只显示隐私提示、事件总数、成功率、最近事件时间和完整 Viewer 位置提示。
- 完整 Viewer 位于主页面底部的“开发工具 / Analytics Viewer”折叠区，默认收起。
- 完整 Viewer 显示事件总数、成功事件数、失败事件数、成功率和最近事件时间。
- Viewer 提供事件类型分布表和横向条形图。
- Viewer 提供基于事件总次数的主流程 funnel summary。
- Viewer 提供近期事件表，以及默认收起的近期事件原始 JSON。
- Viewer 支持刷新、下载 `events.jsonl`，以及勾选确认后清空本地日志。
- 无事件时显示引导用户先上传数据、进入数据质量或导出报告的空状态。

# Important Design Decisions

## 隐私与数据安全边界

- 不记录原始 dataframe 行。
- 不记录敏感单元格值。
- 优先只记录 `row_count`、`column_count`、`missing_count`、`duplicate_count`、`outlier_count` 等聚合元数据。
- `analytics_service` 对属性名中包含 `phone`、`mobile`、`email`、`customer_name` 的值进行轻量脱敏，并省略不适合直接序列化的复杂对象；该保护不能替代调用方的数据最小化责任。
- PRD 允许 MVP 在必要的细粒度事件中记录字段名，但当前已接入主流程事件不需要记录原始字段值。
- `events.jsonl` 是本地运行时数据，默认只保留在 `workspace/analytics`。
- `workspace/analytics/*.jsonl` 不应提交到 Git，也不应在用户未明确导出时自动上传到外部服务。
- 错误信息应保持简短，不记录完整数据内容或异常堆栈。

# Data Flow / State Flow

```text
用户操作或页面渲染
  -> app.py 识别事件触发点
  -> analytics_tracking_service 构造聚合 properties/context
  -> safe_track_event 隔离埋点异常
  -> analytics_service 生成通用字段
  -> 追加一行 JSON 到 workspace/analytics/events.jsonl
  -> Analytics Viewer 读取事件并进行本地计数展示
```

- `session_id` 在 Streamlit session state 中保持稳定。
- `dataset_selected` 和 `data_quality_viewed` 使用 session state 指纹避免同一上下文因 Streamlit rerun 被重复记录。
- 事件记录失败不会阻止数据上传、数据处理、数据集选择或报告导出。
- Analytics Viewer 只读取和汇总本地事件，不修改事件语义；清空操作必须经过用户确认。

# Known Issues

## 当前限制

- 当前没有连接外部 analytics 平台。
- 当前没有 SQLite、PostHog、Mixpanel 或云数据库持久化。
- 尚未接入缺失值、重复值、ID 覆盖和异常值处理计划的详细事件。
- `data_quality_viewed` 表示数据质量页签内容已渲染，不一定代表用户进行了明确、独立的点击。
- session 分析和 funnel conversion 目前是基础计数，不是严格的逐 session 转化漏斗。
- 多表建模和业务分析使用指标尚缺少对应的已接入事件。
- `report_export_clicked` 的触发语义因导出类型不同而略有差异：下载类导出在下载按钮实际点击时记录，AI 生成类导出在生成开始前记录。
- 当前日志没有自动轮转、保留周期或容量上限。

# Future Improvements

## 后续扩展建议

- 接入 `missing_value_plan_added`，记录缺失值处理计划新增动作。
- 接入 `duplicate_plan_added`，记录重复值处理计划新增动作。
- 接入 `id_field_override_applied`，记录人工 ID 识别覆盖动作。
- 接入 `outlier_plan_added`，记录异常值处理计划新增动作。
- 增加按 `session_id` 串联的用户路径和主流程转化分析。
- 增加 SQLite 持久化，以支持本地查询、聚合、保留策略和更大日志量。
- 增加可选的 analytics 汇总报告导出能力。
- 为企业模式增加字段名屏蔽、哈希或映射能力。
- 仅在产品确有集中分析需求时增加 PostHog、Mixpanel 或其他外部 analytics 集成，并保持现有事件名称和通用字段兼容。

# Do Not Break

- 埋点失败不得阻断任何主产品流程。
- 不得记录原始 dataframe 行或敏感单元格值。
- 不得未经用户明确操作把本地事件发送到外部服务。
- 必须保持 MVP 已接入事件的 `event_name` 稳定。
- 必须保持 JSONL 一行一个事件的格式，除非迁移方案同时提供兼容路径。
- `workspace/analytics/*.jsonl` 必须继续被 Git 忽略。
- Analytics Viewer 必须保持为低调的开发工具，不得替代或挤占现有一级产品模块。
- 清空本地日志必须继续要求用户确认。

## 验证方式

自动测试：

```powershell
.venv312\Scripts\python.exe -m unittest discover -s tests
```

手动验证：

1. 运行 `streamlit run app.py`。
2. 上传一个数据集。
3. 将数据集设为当前分析数据集。
4. 打开“数据质量”。
5. 生成清洗数据集。
6. 导出一份报告。
7. 打开侧边栏和主页面底部的 Analytics Viewer。
8. 确认上述主流程事件可见，成功/失败计数和近期事件内容符合实际操作。
9. 确认 `workspace/analytics/events.jsonl` 已生成，并保持一行一个 JSON 对象。
10. 运行 `git check-ignore -v workspace/analytics/events.jsonl`，确认该文件命中 `.gitignore`。
11. 运行 `git status --short`，确认 `events.jsonl` 未被 Git 跟踪。

# Last Updated

2026-07-16
