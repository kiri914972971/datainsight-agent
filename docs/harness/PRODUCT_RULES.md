# Product Rules

These rules are non-negotiable product constraints for Codex-assisted changes.

## Main Workspace

- The main workspace must keep these groups: 项目数据, 数据建模, 指标配置, 分析工作台, 交付导出.
- 项目数据 must keep these tabs: 数据源, 数据合并, 数据质量.
- 数据源 must keep dataset upload, project dataset list, current dataset selection, and preview tabs: 前20行, 后20行, 随机20行, 字段信息.
- 数据建模 must keep: 字段映射, 表关系, 分析数据集.
- 分析工作台 must keep: 业务问题, 探索性分析, Dashboard, 业务分析.
- 交付导出 must keep the report export center available.

## Dataset Rules

- Uploaded datasets, appended datasets, cleaned datasets, and joined analysis datasets must all be treated as selectable project datasets.
- Selecting any registered project dataset must not break unrelated workspace tabs.
- Dataset metadata needed for preview, selection, and downstream analysis must be preserved.

## Data Quality Rules

- 数据质量 must keep missing values, duplicates, ID detection, outlier analysis, and IQR-related checks.
- IQR/outlier handling must not be removed or weakened when fixing local bugs.

## Change Safety

- Do not remove existing features to fix local bugs.
- Do not refactor unrelated modules unless explicitly requested.
- Keep fixes scoped to the smallest related files.
