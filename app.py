import hashlib
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.eda_ai_complete import (
    build_analysis_payload,
    request_ai_insights,
)
from src.ai_connection import test_ai_connection
from src.ai_presets import AI_MODEL_PRESETS
from src.business_analysis import (
    business_metric_options,
    calculate_kpi,
    execute_business_query,
    filter_time_slice,
    generate_business_explanation,
    generate_dashboard,
    generate_dimension_trend,
    generate_share_analysis,
    generate_top_n,
    identify_business_fields,
    parse_business_question,
    request_management_summary,
)
from src.cleaner import clean_data, comparison
from src.data_loader import basic_info, load_data
from src.dashboard_exporter import create_excel_dashboard, detect_dashboard_fields
from src.export_service import EXPORT_OPTIONS, export_dataframe
import importlib

from src import exporter as exporter_module
from src.engines.field_mapping_engine import FIELD_TYPES
from src.engines.kpi_engine import KPI_CATEGORIES, RESERVED_AGGREGATION, SUPPORTED_AGGREGATIONS
from src.engines.metric_dictionary_engine import METRIC_CATEGORIES
from src.engines.analysis_engine import execute_analysis
from src.engines.business_analysis_engine import generate_business_analysis as generate_rule_business_analysis
from src.engines.eda_engine import generate_eda_report
from src.engines.dashboard_engine import generate_dashboard as generate_project_dashboard

required_exporter_attributes = {
    "REPORT_TEMPLATE_PLACEHOLDERS",
    "export_executive_ppt",
    "export_full_excel_report",
    "export_ppt_from_template",
    "export_processed_data_excel",
    "export_word_from_template",
    "generate_ai_periodic_report",
}
if not all(hasattr(exporter_module, name) for name in required_exporter_attributes):
    exporter_module = importlib.reload(exporter_module)

REPORT_TEMPLATE_PLACEHOLDERS = exporter_module.REPORT_TEMPLATE_PLACEHOLDERS
export_executive_ppt = exporter_module.export_executive_ppt
export_full_excel_report = exporter_module.export_full_excel_report
export_ppt_from_template = exporter_module.export_ppt_from_template
export_processed_data_excel = exporter_module.export_processed_data_excel
export_word_from_template = exporter_module.export_word_from_template
generate_ai_periodic_report = exporter_module.generate_ai_periodic_report
from src.data_quality import (
    apply_missing_value_fix,
    data_quality_summary,
    detect_identifier_columns,
    drop_duplicate_rows,
    drop_high_missing_columns,
    generate_data_repair_suggestions,
    quality_stars,
    summarize_duplicates,
    summarize_identifier_columns,
    summarize_missing_values,
    suspicious_columns,
)
from src.exploration import (
    calculate_correlation_pairs,
    categorical_distribution_table,
    categorical_profile,
    get_analysis_categorical_columns,
    get_analysis_numeric_columns,
    interpret_categorical_distribution,
    interpret_numeric_distribution,
    numeric_profile,
    summarize_categorical_columns,
    summarize_numeric_columns,
)
from src.outlier import (
    calculate_iqr_bounds,
    compare_before_after_outlier_treatment,
    create_outlier_download,
    create_outlier_preview,
    detect_outliers_iqr,
    remove_outliers,
    replace_outliers_with_median,
    replace_outliers_with_quantile,
    summarize_outliers,
    winsorize_outliers,
)
from src.project_workspace import (
    create_project,
    delete_project,
    get_project,
    get_project_path,
    list_projects,
)
from src.query_engine import run_query
from src.report_generator import generate_report
from src.services.data_source_service import (
    build_field_profile,
    delete_project_data_file,
    get_data_file_profile,
    list_project_data_files,
    load_project_data_file,
    save_project_data_files,
    set_current_analysis_file,
)
from src.services.current_dataset_service import (
    DATASET_TYPE_LABELS,
    NO_CURRENT_ANALYSIS_DATASET_MESSAGE,
    get_current_analysis_dataset,
    list_project_datasets,
    load_project_dataset_dataframe,
    load_current_analysis_dataframe,
    set_current_analysis_dataset,
)
from src.services.data_quality_service import (
    apply_duplicate_handling_plan_preview,
    apply_duplicate_group_preview,
    apply_missing_value_plan_preview,
    apply_quality_operations,
    create_cleaned_dataset,
    detect_identifier_columns as detect_quality_identifier_columns,
    detect_invalid_columns as detect_quality_invalid_columns,
    duplicate_handling_plan_to_operations,
    format_duplicate_handling_plan,
    format_missing_value_plan,
    generate_data_repair_suggestions_for_quality,
    get_final_id_columns,
    get_iqr_numeric_measure_columns,
    get_cleaned_dataset_metadata,
    load_cleaned_dataset,
    missing_sample_preview,
    missing_value_plan_to_operations,
    remove_missing_value_plan_item,
    reset_id_override_state,
    set_cleaned_dataset_as_current,
    summarize_duplicates_for_quality,
    summarize_duplicate_handling_effect,
    summarize_identifier_columns,
    summarize_iqr_outliers_for_quality,
    summarize_missing_values_for_quality,
    summarize_missing_value_plan_effect,
    summarize_quality_overview,
    update_id_override_state,
    upsert_duplicate_handling_plan,
    upsert_missing_value_plan_item,
)
from src.services.analysis_dataset_service import (
    build_analysis_dataset,
    generate_join_plan,
    get_dataset_metadata,
    preview_analysis_dataset,
)
from src.services.append_service import (
    analyze_append_compatibility,
    build_appended_dataset,
    get_appended_dataset_metadata,
    list_append_sources,
    load_appended_dataset,
    set_appended_dataset_as_current,
)
from src.services.business_question_service import (
    load_question_parse_history,
    parse_question_for_project,
)
from src.services.field_mapping_service import (
    confirmed_columns_by_type,
    get_missing_historical_fields,
    get_new_fields,
    load_field_mappings,
    mapping_business_summary,
    merge_existing_mappings,
    prioritize_business_fields,
    prioritize_dashboard_fields,
    save_field_mappings,
)
from src.services.kpi_service import (
    add_kpi_definition,
    delete_kpi_definition,
    generate_project_kpi_candidates,
    list_enabled_kpis,
    load_kpi_definitions,
    merged_project_kpis,
    save_kpi_definitions,
)
from src.services.metric_dictionary_service import (
    add_metric_definition,
    delete_metric_definition,
    generate_project_metric_candidates,
    list_enabled_metrics,
    load_metric_dictionary,
    merged_project_metrics,
    save_metric_dictionary,
)
from src.services.relationship_service import (
    RELATIONSHIP_TYPES,
    clear_table_relationships,
    delete_table_relationship,
    discover_project_relationships,
    get_project_table_columns,
    list_project_tables,
    load_table_relationships,
    save_table_relationships,
)
from src.template_manager import get_active_template, save_uploaded_template
from src.type_detector import detect_and_parse_types, type_summary
from src.ui import (
    apply_product_theme,
    render_module_intro,
    render_page_header,
)
from src.visualizer import box_plot, correlation_heatmap, histogram


def render_outlier_visualization(
    df: pd.DataFrame,
    column: str,
    outlier_info: dict,
    key_prefix: str,
) -> None:
    bounds = outlier_info.get("bounds", {})
    mask = outlier_info.get("mask")
    if mask is None:
        series_for_mask = pd.to_numeric(df[column], errors="coerce")
        lower_bound = bounds.get("lower_bound")
        upper_bound = bounds.get("upper_bound")
        if pd.isna(lower_bound) or pd.isna(upper_bound):
            mask = pd.Series(False, index=df.index)
        else:
            mask = (series_for_mask < lower_bound) | (series_for_mask > upper_bound)
    mask = pd.Series(mask, index=df.index).fillna(False).astype(bool)

    plot_df = pd.DataFrame(
        {
            "原始行索引": df.index,
            column: pd.to_numeric(df[column], errors="coerce"),
            "状态": mask.map({True: "异常值", False: "正常值"}),
        }
    ).dropna(subset=[column])

    if plot_df.empty:
        st.info("当前字段没有可绘制的有效数值。")
        return

    palette = {"正常值": "#2563EB", "异常值": "#F97316"}
    box_fig = go.Figure()
    box_fig.add_trace(
        go.Box(
            x=plot_df[column],
            name=column,
            boxpoints=False,
            fillcolor="rgba(37, 99, 235, 0.18)",
            line={"color": "#1E3A8A", "width": 1.6},
            marker={"color": "#2563EB"},
            hovertemplate=f"{column}: %{{x:,.2f}}<extra></extra>",
        )
    )
    outlier_points = plot_df.loc[plot_df["状态"] == "异常值"]
    if not outlier_points.empty:
        box_fig.add_trace(
            go.Scatter(
                x=outlier_points[column],
                y=[column] * len(outlier_points),
                mode="markers",
                name="异常值",
                marker={"color": "#F97316", "size": 8, "line": {"color": "#9A3412", "width": 1}},
                customdata=outlier_points[["原始行索引"]],
                hovertemplate=(
                    f"{column}: %{{x:,.2f}}<br>"
                    "原始行索引: %{customdata[0]}<extra>异常值</extra>"
                ),
            )
        )
    box_fig.update_layout(
        title=f"{column} 异常值箱线图",
        xaxis_title=column,
        yaxis_title="",
        height=320,
        margin={"l": 24, "r": 24, "t": 58, "b": 42},
        legend_title_text="",
        template="plotly_white",
    )
    box_fig.update_xaxes(showgrid=True, gridcolor="rgba(148, 163, 184, 0.25)", separatethousands=True)
    box_fig.update_yaxes(showticklabels=False)
    distribution_fig = px.histogram(
        plot_df,
        x=column,
        color="状态",
        color_discrete_map=palette,
        barmode="overlay",
        opacity=0.72,
        title=f"{column} 正常值与异常值分布",
        labels={column: column, "count": "记录数", "状态": ""},
        hover_data={"原始行索引": True, column: ":,.2f", "状态": True},
    )
    distribution_fig.update_layout(
        height=320,
        margin={"l": 24, "r": 24, "t": 58, "b": 42},
        template="plotly_white",
        legend_title_text="",
    )
    distribution_fig.update_xaxes(showgrid=True, gridcolor="rgba(148, 163, 184, 0.25)", separatethousands=True)
    distribution_fig.update_yaxes(showgrid=True, gridcolor="rgba(148, 163, 184, 0.25)")

    chart_cols = st.columns(2)
    chart_cols[0].plotly_chart(
        box_fig,
        use_container_width=True,
        key=f"{key_prefix}_outlier_box",
    )
    chart_cols[1].plotly_chart(
        distribution_fig,
        use_container_width=True,
        key=f"{key_prefix}_outlier_distribution",
    )

    date_column = _detect_outlier_date_column(df)
    if date_column:
        time_df = plot_df.join(df[[date_column]], how="left")
        time_df[date_column] = pd.to_datetime(time_df[date_column], errors="coerce")
        time_df = time_df.dropna(subset=[date_column])
        if not time_df.empty:
            time_fig = px.scatter(
                time_df,
                x=date_column,
                y=column,
                color="状态",
                color_discrete_map=palette,
                title=f"{column} 异常值时间分布",
                labels={date_column: "日期", column: column, "状态": ""},
                hover_data={"原始行索引": True, column: ":,.2f", date_column: True, "状态": True},
            )
            time_fig.update_traces(marker={"size": 8, "line": {"width": 0.6, "color": "#FFFFFF"}})
            time_fig.update_layout(
                height=340,
                margin={"l": 24, "r": 24, "t": 58, "b": 42},
                template="plotly_white",
                legend_title_text="",
            )
            time_fig.update_xaxes(showgrid=True, gridcolor="rgba(148, 163, 184, 0.25)")
            time_fig.update_yaxes(showgrid=True, gridcolor="rgba(148, 163, 184, 0.25)", separatethousands=True)
            st.plotly_chart(
                time_fig,
                use_container_width=True,
                key=f"{key_prefix}_outlier_time",
            )


def _detect_outlier_date_column(df: pd.DataFrame) -> str | None:
    for column in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[column]):
            return column
    for column in df.columns:
        normalized = str(column).lower()
        if not any(hint in normalized for hint in ("date", "time", "日期", "时间")):
            continue
        parsed = pd.to_datetime(df[column].dropna(), errors="coerce", format="mixed")
        if not parsed.empty and parsed.notna().mean() >= 0.8:
            return column
    return None


st.set_page_config(page_title="DataInsight Agent", page_icon="📊", layout="wide")
apply_product_theme()
render_page_header()


def reset_for_file(uploaded_file) -> None:
    project_id = st.session_state.get("active_project_id", "")
    file_key = f"{project_id}-{uploaded_file.name}-{uploaded_file.size}"
    if st.session_state.get("file_key") != file_key:
        dataframe = load_data(uploaded_file)
        reset_for_dataframe(dataframe, uploaded_file.name, file_key)


def reset_for_dataframe(
    dataframe: pd.DataFrame,
    file_name: str,
    analysis_key: str,
) -> None:
    if st.session_state.get("file_key") != analysis_key:
        dataframe, detected = detect_and_parse_types(dataframe)
        st.session_state.file_key = analysis_key
        st.session_state.file_name = file_name
        st.session_state.original_df = dataframe
        st.session_state.current_df = dataframe.copy()
        st.session_state.working_df = dataframe.copy()
        st.session_state.field_types = detected
        st.session_state.last_comparison = None
        st.session_state.ai_eda_result = None
        st.session_state.ai_exploration_result = None
        st.session_state.ai_business_report = None
        st.session_state.ai_executive_summary = None
        st.session_state.ai_periodic_report = None
        st.session_state.business_query_plan = None
        st.session_state.business_query_result = None
        st.session_state.business_query_explanation = None
        st.session_state.last_outlier_comparison = None
        st.session_state.last_outlier_before_df = None
        st.session_state.last_outlier_after_df = None
        st.session_state.last_outlier_column = None
        st.session_state.outlier_treatment_message = None
        st.session_state.duplicate_comparison = None
        st.session_state.quality_action_message = None


def clear_outlier_treatment_result() -> None:
    st.session_state.last_outlier_comparison = None
    st.session_state.last_outlier_before_df = None
    st.session_state.last_outlier_after_df = None
    st.session_state.last_outlier_column = None
    st.session_state.outlier_treatment_message = None


def set_current_data(after: pd.DataFrame, before: pd.DataFrame | None = None) -> None:
    st.session_state.current_df = after
    st.session_state.working_df = after
    if before is not None:
        st.session_state.last_comparison = comparison(before, after)
    st.session_state.ai_eda_result = None
    st.session_state.ai_exploration_result = None
    st.session_state.ai_business_report = None
    st.session_state.business_query_plan = None
    st.session_state.business_query_result = None
    st.session_state.business_query_explanation = None


def clear_active_analysis() -> None:
    analysis_state_keys = (
        "file_key",
        "file_name",
        "original_df",
        "current_df",
        "working_df",
        "field_types",
        "last_comparison",
        "ai_eda_result",
        "ai_exploration_result",
        "ai_business_report",
        "ai_executive_summary",
        "ai_periodic_report",
        "business_query_plan",
        "business_query_result",
        "business_query_explanation",
        "last_outlier_comparison",
        "last_outlier_before_df",
        "last_outlier_after_df",
        "last_outlier_column",
        "outlier_treatment_message",
        "duplicate_comparison",
        "quality_action_message",
    )
    for key in analysis_state_keys:
        st.session_state.pop(key, None)


def activate_project(project_id: str) -> None:
    clear_active_analysis()
    st.session_state.active_project_id = project_id


def render_project_center() -> None:
    st.subheader("Project Center")
    st.caption("创建或打开一个分析项目。项目文件会持久化保存在本地工作区中。")

    message = st.session_state.pop("project_center_message", None)
    if message:
        st.success(message)

    create_column, open_column = st.columns(2)
    with create_column.container(border=True):
        st.markdown("### 新建项目")
        st.write("为一次完整分析建立独立工作区，后续可以持续添加数据文件。")
        with st.form("create_project_form", clear_on_submit=True):
            project_name = st.text_input(
                "项目名称",
                placeholder="例如：六月销售分析",
            )
            submitted = st.form_submit_button(
                "新建并打开项目",
                type="primary",
                use_container_width=True,
            )
        if submitted:
            try:
                project = create_project(project_name)
                activate_project(project["project_id"])
                st.rerun()
            except Exception as exc:
                st.error(f"项目创建失败：{exc}")

    projects = list_projects()
    with open_column.container(border=True):
        st.markdown("### 打开项目")
        if not projects:
            st.info("当前还没有项目，请先新建项目。")
        else:
            project_labels = {
                project["project_id"]: (
                    f"{project['project_name']} · {project['project_id']}"
                )
                for project in projects
            }
            selected_project_id = st.selectbox(
                "已有项目",
                options=list(project_labels),
                format_func=lambda project_id: project_labels[project_id],
            )
            selected_project = next(
                project
                for project in projects
                if project["project_id"] == selected_project_id
            )
            st.caption(f"最近更新：{selected_project['last_modified']}")
            open_button, delete_button = st.columns(2)
            if open_button.button(
                "打开项目",
                type="primary",
                use_container_width=True,
            ):
                activate_project(selected_project_id)
                st.rerun()
            confirm_delete = st.checkbox(
                "确认删除所选项目及其文件",
                key=f"confirm_delete_{selected_project_id}",
            )
            if delete_button.button(
                "删除项目",
                disabled=not confirm_delete,
                use_container_width=True,
            ):
                delete_project(selected_project_id)
                st.session_state.project_center_message = (
                    f"项目“{selected_project['project_name']}”已删除。"
                )
                st.rerun()

    if projects:
        st.markdown("### 最近项目")
        project_rows = []
        for project in projects[:10]:
            project_rows.append(
                {
                    "项目名称": project["project_name"],
                    "项目 ID": project["project_id"],
                    "文件数量": len(list_project_data_files(project["project_id"])),
                    "最近更新": project["last_modified"],
                }
            )
        st.dataframe(project_rows, use_container_width=True, hide_index=True)


def render_project_status_bar(
    project: dict,
    current_analysis_dataset: dict | None,
    data_file_count: int,
) -> None:
    with st.container(border=True):
        status_columns = st.columns([1.25, 1.8, 0.8, 0.8, 1.4])
        status_columns[0].markdown("#### 当前项目")
        status_columns[0].write(project.get("project_name", "-"))
        if current_analysis_dataset:
            dataset_name = current_analysis_dataset.get("dataset_name", "-")
            sheet_name = current_analysis_dataset.get("sheet_name", "")
            dataset_type = current_analysis_dataset.get("dataset_type", "-")
            dataset_type_label = DATASET_TYPE_LABELS.get(dataset_type, dataset_type)
            dataset_status = f"{dataset_name} / {sheet_name}" if sheet_name else dataset_name
            row_count = current_analysis_dataset.get("row_count", 0) or 0
            column_count = current_analysis_dataset.get("column_count", 0) or 0
            file_path = current_analysis_dataset.get("file_path", "-")
        else:
            dataset_status = NO_CURRENT_ANALYSIS_DATASET_MESSAGE
            dataset_type_label = "-"
            row_count = 0
            column_count = 0
            file_path = "-"
        status_columns[1].markdown("#### 当前分析数据集")
        status_columns[1].write(dataset_status)
        status_columns[1].caption(f"类型：{dataset_type_label} · 保存位置：{file_path}")
        status_columns[2].metric("行数", f"{int(row_count):,}" if row_count else "-")
        status_columns[3].metric("列数", f"{int(column_count):,}" if column_count else "-")
        status_columns[4].metric("项目数据文件", data_file_count)
        status_columns[4].caption(f"项目 ID：{project.get('project_id', '-')}")


def render_dataset_preview(
    df: pd.DataFrame,
    dataset_name: str,
    show_download: bool = True,
    key_prefix: str | None = None,
) -> None:
    resolved_key_prefix = _safe_streamlit_key(key_prefix or f"dataset_preview_{dataset_name}")
    st.markdown("#### 数据预览")
    st.caption(f"当前预览：{dataset_name}")
    preview_tabs = st.tabs(["前20行", "后20行", "随机20行", "字段信息"])
    with preview_tabs[0]:
        st.dataframe(df.head(20), use_container_width=True)
    with preview_tabs[1]:
        st.dataframe(df.tail(20), use_container_width=True)
    with preview_tabs[2]:
        sample_size = min(20, len(df))
        if sample_size:
            st.dataframe(df.sample(sample_size, random_state=42), use_container_width=True)
        else:
            st.info("当前数据集为空，暂无随机预览。")
    with preview_tabs[3]:
        st.dataframe(
            _dataset_field_profile(df),
            use_container_width=True,
            hide_index=True,
        )

    if show_download:
        csv_data = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "下载CSV",
            data=csv_data,
            file_name=_safe_csv_file_name(dataset_name),
            mime="text/csv",
            key=f"{resolved_key_prefix}_download_csv",
            use_container_width=True,
        )


def _dataset_field_profile(df: pd.DataFrame) -> pd.DataFrame:
    row_count = len(df)
    missing_counts = df.isna().sum().astype(int)
    if row_count:
        missing_rates = (missing_counts / row_count * 100).round(2)
    else:
        missing_rates = missing_counts.astype(float)
    return pd.DataFrame(
        {
            "字段名": df.columns.astype(str),
            "Pandas类型": [str(dtype) for dtype in df.dtypes],
            "缺失值数量": missing_counts.values,
            "缺失率": [f"{value:.2f}%" for value in missing_rates.values],
            "唯一值数量": df.nunique(dropna=True).astype(int).values,
        }
    )


def _safe_csv_file_name(dataset_name: str) -> str:
    safe_name = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "_"
        for char in str(dataset_name).strip()
    ).strip("._")
    safe_name = safe_name[:80] or "dataset"
    return safe_name if safe_name.lower().endswith(".csv") else f"{safe_name}.csv"


def _safe_streamlit_key(value: str) -> str:
    raw_value = str(value or "dataset_preview")
    digest = hashlib.md5(raw_value.encode("utf-8")).hexdigest()[:8]
    safe_value = "".join(
        char if char.isascii() and (char.isalnum() or char == "_") else "_"
        for char in raw_value
    )
    while "__" in safe_value:
        safe_value = safe_value.replace("__", "_")
    safe_value = safe_value.strip("_")[:80]
    if not safe_value:
        safe_value = "dataset_preview"
    return f"{safe_value}_{digest}"


def render_appended_dataset_summary(
    project_id: str,
    metadata: dict,
    *,
    key_prefix: str,
) -> None:
    dataset_name = metadata.get("dataset_display_name") or f"合并数据集 {metadata.get('file_name', 'appended_dataset.csv')}"
    saved_path = metadata.get(
        "saved_path",
        f"workspace/projects/{project_id}/analysis/appended_dataset.csv",
    )
    metadata_path = metadata.get(
        "metadata_path",
        f"workspace/projects/{project_id}/analysis/appended_dataset_meta.json",
    )
    source_files = metadata.get("source_files", [])
    before_total_rows = int(
        metadata.get(
            "before_total_rows",
            sum(int(item.get("rows", 0)) for item in source_files),
        )
    )
    after_rows = int(metadata.get("after_rows", 0))
    validation_summary = metadata.get("validation_summary") or {}
    row_count_matches = validation_summary.get(
        "row_count_matches",
        before_total_rows == after_rows,
    )
    filled_null_fields = validation_summary.get("filled_null_fields")
    if filled_null_fields is None:
        suggested_null_fields = (
            metadata.get("field_alignment", {}).get("suggested_null_fields", {})
        )
        filled_null_fields = sorted(
            {
                field
                for fields in suggested_null_fields.values()
                for field in fields
            }
        )

    with st.container(border=True):
        st.markdown(f"#### {dataset_name}")
        st.caption("该数据集由多个来源表纵向追加生成，不会覆盖原始上传文件。")
        result_columns = st.columns(5)
        result_columns[0].metric("合并后行数", f"{metadata.get('after_rows', 0):,}")
        result_columns[1].metric("合并后列数", metadata.get("columns", 0))
        result_columns[2].metric(
            "来源文件数",
            metadata.get("source_file_count", len(metadata.get("source_files", []))),
        )
        result_columns[3].metric(
            "数据大小",
            _format_file_size(int(metadata.get("file_size", 0))),
        )
        result_columns[4].metric("生成时间", str(metadata.get("created_at", ""))[:19])
        st.write(f"**保存路径：** `{saved_path}`")
        st.write(f"**元数据路径：** `{metadata_path}`")

        st.markdown("##### 数据校验摘要")
        validation_columns = st.columns(5)
        validation_columns[0].metric("合并前总行数", f"{before_total_rows:,}")
        validation_columns[1].metric("合并后总行数", f"{after_rows:,}")
        validation_columns[2].metric("行数是否一致", "是" if row_count_matches else "否")
        validation_columns[3].metric("字段数", metadata.get("columns", 0))
        validation_columns[4].metric("存在补空字段", "是" if filled_null_fields else "否")
        if row_count_matches:
            st.success("合并后行数与来源行数总和一致。")
        else:
            st.error(
                "合并后行数与来源行数总和不一致，请检查来源表选择和生成结果。"
            )
        if filled_null_fields:
            st.warning(f"补空字段：{', '.join(map(str, filled_null_fields))}")
        else:
            st.info("未检测到需要补空的字段。")

        if source_files:
            st.markdown("##### 各来源表行数汇总")
            st.dataframe(
                pd.DataFrame(source_files).rename(
                    columns={
                        "file_name": "来源文件",
                        "sheet_name": "Sheet",
                        "rows": "行数",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

        try:
            appended_df = load_appended_dataset(project_id)
        except Exception as exc:
            st.error(f"合并数据集读取失败：{exc}")
            appended_df = None

        if appended_df is not None:
            render_dataset_preview(
                appended_df,
                metadata.get("file_name", "appended_dataset.csv"),
                show_download=True,
                key_prefix=f"{key_prefix}_preview_{metadata.get('dataset_id', 'appended_dataset')}",
            )

        if st.button(
            "设为当前分析数据集",
            type="primary",
            key=f"{key_prefix}_set_appended_dataset_current_{project_id}",
        ):
            try:
                selection = set_appended_dataset_as_current(project_id)
                clear_active_analysis()
                message = f"已将“合并数据集 {selection['file_name']}”设为当前分析数据集。"
                st.session_state.data_source_message = message
                st.session_state.append_tables_message = message
                st.rerun()
            except Exception as exc:
                st.error(f"设置当前分析数据集失败：{exc}")


def _infer_append_field_type_from_sources(
    field: str,
    sources: list[dict],
    selected_source_ids: list[str],
    project_id: str,
) -> str:
    source_by_id = {source["source_id"]: source for source in sources}
    for source_id in selected_source_ids:
        source = source_by_id.get(source_id)
        if not source:
            continue
        try:
            dataframe = load_project_data_file(
                project_id,
                source["file_id"],
                source["sheet_name"],
            )
        except Exception:
            continue
        if field not in dataframe.columns:
            continue
        series = dataframe[field]
        if pd.api.types.is_numeric_dtype(series):
            return "数值字段"
        if pd.api.types.is_datetime64_any_dtype(series):
            return "日期字段"
        unique_ratio = series.nunique(dropna=True) / len(series) if len(series) else 0
        if unique_ratio <= 0.5:
            return "类别字段"
        return "文本字段"
    return "未知字段"


def _dataset_type_badge(dataset_type: str | None) -> str:
    return {
        "uploaded": "原始",
        "appended": "合并",
        "cleaned": "清洗",
        "joined": "关联",
    }.get(str(dataset_type or ""), str(dataset_type or "-"))


def _is_current_dataset(current_selection: dict | None, dataset: dict) -> bool:
    return bool(
        current_selection
        and current_selection.get("dataset_id") == dataset.get("dataset_id")
    )


def _dataset_option_label(dataset: dict, current_selection: dict | None) -> str:
    current_prefix = "[当前分析] " if _is_current_dataset(current_selection, dataset) else ""
    type_prefix = f"[{_dataset_type_badge(dataset.get('dataset_type'))}]"
    rows = int(dataset.get("row_count") or 0)
    columns = int(dataset.get("column_count") or 0)
    return f"{current_prefix}{type_prefix} {dataset.get('dataset_name', '-')} · {rows:,}行 × {columns:,}列"


def _dataset_source_description(dataset: dict) -> str:
    dataset_type = dataset.get("dataset_type")
    if dataset_type == "uploaded":
        sheet_name = dataset.get("sheet_name")
        if sheet_name and sheet_name != "CSV":
            return f"来自上传文件 Sheet：{sheet_name}"
        return "来自上传文件"
    if dataset_type == "appended":
        source_files = dataset.get("source_files") or []
        if source_files:
            names = [
                f"{item.get('file_name', '-')}/{item.get('sheet_name', '-')}"
                for item in source_files[:3]
                if isinstance(item, dict)
            ]
            suffix = " 等" if len(source_files) > 3 else ""
            return f"由 {len(source_files)} 个来源表纵向合并：{'，'.join(names)}{suffix}"
        return "由数据合并生成"
    if dataset_type == "cleaned":
        return "由数据清洗生成"
    if dataset_type == "joined":
        return "由表关系 / 分析数据集生成"
    return "项目数据集"


def render_data_source_tab(project_id: str) -> None:
    render_module_intro(
        "database",
        "Project data sources",
        "项目数据源",
        "上传并管理项目内的多个数据文件，选择一个文件或 Excel Sheet 作为当前分析数据。",
    )
    st.subheader("上传项目数据文件")
    st.caption("支持 CSV、XLSX 和 XLS。文件会持久化保存到当前项目的 data 目录。")
    uploaded_files = st.file_uploader(
        "选择一个或多个数据文件",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
        key=f"data_source_uploads_{project_id}",
    )
    if st.button(
        "上传并保存到项目",
        disabled=not uploaded_files,
        type="primary",
        key=f"save_data_sources_{project_id}",
    ):
        try:
            saved = save_project_data_files(project_id, uploaded_files)
            st.session_state.data_source_message = f"已保存 {len(saved)} 个项目数据文件。"
            st.rerun()
        except Exception as exc:
            st.error(f"文件保存失败：{exc}")

    message = st.session_state.pop("data_source_message", None)
    if message:
        st.success(message)

    current_selection = get_current_analysis_dataset(project_id)
    appended_metadata = get_appended_dataset_metadata(project_id)
    if current_selection:
        if current_selection.get("dataset_type") == "appended":
            st.success(f"当前分析数据：合并数据集 {current_selection.get('dataset_name', 'appended_dataset.csv')}")
        else:
            st.info(
                "当前分析数据："
                f"{current_selection.get('dataset_name', '-')} / {current_selection.get('sheet_name', '-')}"
            )

    st.subheader("项目文件列表")
    data_files = list_project_data_files(project_id)
    file_rows = []
    for item in data_files:
        sheets = item.get("sheets", [])
        file_rows.append(
            {
                "当前分析数据": (
                    "是"
                    if current_selection
                    and current_selection.get("dataset_id") == item["file_id"]
                    else ""
                ),
                "文件名": item["file_name"],
                "文件类型": item["file_type"].upper(),
                "文件大小": _format_file_size(item["file_size"]),
                "上传时间": item["uploaded_at"],
                "Sheet 数量": len(sheets),
                "总行数": sum(sheet["rows"] for sheet in sheets),
                "最大列数": max(
                    (sheet["columns"] for sheet in sheets),
                    default=0,
                ),
                "保存位置": item.get("file_path", f"data/{item['file_name']}"),
            }
        )
    if appended_metadata:
        file_rows.append(
            {
                "当前分析数据": (
                    "是"
                    if current_selection
                    and current_selection.get("dataset_type") == "appended"
                    else ""
                ),
                "文件名": appended_metadata.get("file_name", "appended_dataset.csv"),
                "文件类型": "CSV · 合并结果",
                "文件大小": _format_file_size(int(appended_metadata.get("file_size", 0))),
                "上传时间": appended_metadata.get("created_at", ""),
                "Sheet 数量": 1,
                "总行数": appended_metadata.get("after_rows", 0),
                "最大列数": appended_metadata.get("columns", 0),
                "保存位置": appended_metadata.get(
                    "saved_path",
                    f"workspace/projects/{project_id}/analysis/appended_dataset.csv",
                ),
            }
        )
    if file_rows:
        st.dataframe(file_rows, use_container_width=True, hide_index=True)
    else:
        st.info("当前项目还没有数据文件，请先上传文件。")

    if appended_metadata:
        st.markdown("### 已生成的合并数据集")
        render_appended_dataset_summary(
            project_id,
            appended_metadata,
            key_prefix="data_source",
        )

    if not data_files:
        return

    file_labels = {
        item["file_id"]: f"{item['file_name']} · {item['file_type'].upper()}"
        for item in data_files
    }
    selected_file_id = st.selectbox(
        "选择要查看的数据文件",
        options=list(file_labels),
        format_func=lambda file_id: file_labels[file_id],
        key=f"data_source_file_{project_id}",
    )
    profile = get_data_file_profile(project_id, selected_file_id)
    if profile.get("profile_error"):
        st.error(f"文件无法读取：{profile['profile_error']}")
    sheet_names = [sheet["sheet_name"] for sheet in profile.get("sheets", [])]
    if not sheet_names:
        st.warning("当前文件没有可读取的数据表。")
        return

    if profile["file_type"] in {"xlsx", "xls"}:
        selected_sheet = st.selectbox(
            "选择 Excel Sheet",
            options=sheet_names,
            key=f"data_source_sheet_{project_id}_{selected_file_id}",
        )
    else:
        selected_sheet = sheet_names[0]

    selected_sheet_profile = next(
        sheet
        for sheet in profile["sheets"]
        if sheet["sheet_name"] == selected_sheet
    )
    info_columns = st.columns(5)
    info_columns[0].metric("文件类型", profile["file_type"].upper())
    info_columns[1].metric("文件大小", _format_file_size(profile["file_size"]))
    info_columns[2].metric("Sheet 数量", len(profile["sheets"]))
    info_columns[3].metric("当前 Sheet 行数", selected_sheet_profile["rows"])
    info_columns[4].metric("当前 Sheet 列数", selected_sheet_profile["columns"])

    try:
        preview_df = load_project_data_file(
            project_id,
            selected_file_id,
            selected_sheet,
        )
    except Exception as exc:
        st.error(f"数据文件读取失败：{exc}")
        return

    st.subheader("数据预览")
    st.caption(f"当前预览：{profile['file_name']} / {selected_sheet}")
    st.dataframe(preview_df.head(20), use_container_width=True)

    st.subheader("字段列表")
    st.dataframe(
        build_field_profile(preview_df),
        use_container_width=True,
        hide_index=True,
    )

    set_column, delete_column = st.columns(2)
    if set_column.button(
        "设为当前分析数据",
        type="primary",
        use_container_width=True,
        key=f"set_current_data_source_{project_id}_{selected_file_id}_{selected_sheet}",
    ):
        set_current_analysis_file(project_id, selected_file_id, selected_sheet)
        clear_active_analysis()
        st.session_state.data_source_message = (
            f"已将“{profile['file_name']} / {selected_sheet}”设为当前分析数据。"
        )
        st.rerun()

    confirm_delete = st.checkbox(
        f"确认删除文件“{profile['file_name']}”",
        key=f"confirm_delete_data_source_{project_id}_{selected_file_id}",
    )
    if delete_column.button(
        "删除数据文件",
        disabled=not confirm_delete,
        use_container_width=True,
        key=f"delete_data_source_{project_id}_{selected_file_id}",
    ):
        result = delete_project_data_file(project_id, selected_file_id)
        if result["cleared_current_analysis"]:
            clear_active_analysis()
            message = "已删除当前分析数据，请重新选择分析数据。"
        else:
            message = f"已删除数据文件“{profile['file_name']}”。"
        st.session_state.data_source_message = message
        st.rerun()


def render_data_source_tab(project_id: str) -> None:
    render_module_intro(
        "database",
        "Project datasets",
        "项目数据源",
        "上传并管理项目内的数据文件；原始 Sheet、合并结果、清洗结果和关联结果会统一注册为项目数据集。",
    )
    st.subheader("上传项目数据文件")
    st.caption("支持 CSV、XLSX 和 XLS。文件会持久化保存到当前项目的 data 目录；每个文件 / Sheet 会自动注册为一个项目数据集。")
    uploaded_files = st.file_uploader(
        "选择一个或多个数据文件",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
        key=f"data_source_uploads_{project_id}",
    )
    if st.button(
        "上传并保存到项目",
        disabled=not uploaded_files,
        type="primary",
        key=f"save_data_sources_{project_id}",
    ):
        try:
            saved = save_project_data_files(project_id, uploaded_files)
            st.session_state.data_source_message = (
                f"已保存 {len(saved)} 个项目数据文件，并注册为项目数据集。"
            )
            st.rerun()
        except Exception as exc:
            st.error(f"文件保存失败：{exc}")

    message = st.session_state.pop("data_source_message", None)
    if message:
        st.success(message)

    current_selection = get_current_analysis_dataset(project_id)
    if current_selection:
        current_type = DATASET_TYPE_LABELS.get(
            current_selection.get("dataset_type"),
            current_selection.get("dataset_type", "-"),
        )
        st.success(
            f"当前分析数据集：{current_selection.get('dataset_name', '-')}（{current_type}）"
        )

    st.subheader("项目数据集列表")
    datasets = list_project_datasets(project_id)
    dataset_rows = []
    for dataset in datasets:
        dataset_rows.append(
            {
                "数据集名称": dataset.get("dataset_name", "-"),
                "数据集类型": DATASET_TYPE_LABELS.get(
                    dataset.get("dataset_type"),
                    dataset.get("dataset_type", "-"),
                ),
                "是否当前分析数据": "是" if _is_current_dataset(current_selection, dataset) else "",
                "行数": dataset.get("row_count", 0),
                "列数": dataset.get("column_count", 0),
                "保存位置": dataset.get("file_path", "-"),
                "来源说明": _dataset_source_description(dataset),
                "生成时间": dataset.get("created_at", ""),
            }
        )
    if dataset_rows:
        st.dataframe(dataset_rows, use_container_width=True, hide_index=True)
    else:
        st.info("当前项目还没有项目数据集，请先上传文件，或在「数据合并」中生成合并数据集。")
        return

    dataset_labels = {
        item["dataset_id"]: _dataset_option_label(item, current_selection)
        for item in datasets
    }
    selected_dataset_id = st.selectbox(
        "选择要查看的数据集",
        options=list(dataset_labels),
        format_func=lambda dataset_id: dataset_labels[dataset_id],
        key=f"data_source_dataset_{project_id}",
    )
    selected_dataset = next(
        item for item in datasets if item["dataset_id"] == selected_dataset_id
    )

    info_columns = st.columns(5)
    info_columns[0].metric(
        "数据集类型",
        DATASET_TYPE_LABELS.get(
            selected_dataset.get("dataset_type"),
            selected_dataset.get("dataset_type", "-"),
        ),
    )
    info_columns[1].metric("行数", f"{int(selected_dataset.get('row_count') or 0):,}")
    info_columns[2].metric("列数", selected_dataset.get("column_count", 0))
    info_columns[3].metric("Sheet", selected_dataset.get("sheet_name") or "-")
    info_columns[4].metric("来源表数", len(selected_dataset.get("source_files", []) or []))
    st.markdown(f"**数据集名称：** {selected_dataset.get('dataset_name', '-')}")
    st.caption(f"保存路径：{selected_dataset.get('file_path', '-')}")
    st.caption(f"来源说明：{_dataset_source_description(selected_dataset)}")

    try:
        preview_df = load_project_dataset_dataframe(project_id, selected_dataset_id)
    except Exception as exc:
        st.error(f"数据集读取失败：{exc}")
        return

    render_dataset_preview(
        preview_df,
        selected_dataset.get("dataset_name", "dataset"),
        show_download=True,
        key_prefix=f"data_source_preview_{selected_dataset_id}",
    )

    set_column, delete_column = st.columns(2)
    if set_column.button(
        "设为当前分析数据集",
        type="primary",
        use_container_width=True,
        key=f"set_current_dataset_{project_id}_{selected_dataset_id}",
    ):
        set_current_analysis_dataset(project_id, selected_dataset)
        clear_active_analysis()
        st.session_state.data_source_message = (
            f"已将“{selected_dataset.get('dataset_name', '-')}”设为当前分析数据集。"
        )
        st.rerun()

    if selected_dataset.get("dataset_type") == "uploaded":
        source_file_id = selected_dataset.get("source_file_id") or str(selected_dataset_id).split("::")[0]
        confirm_delete = st.checkbox(
            f"确认删除原始文件“{selected_dataset.get('dataset_name', '-')}”所在文件？",
            key=f"confirm_delete_data_source_{project_id}_{source_file_id}",
        )
        if delete_column.button(
            "删除原始文件",
            disabled=not confirm_delete,
            use_container_width=True,
            key=f"delete_data_source_{project_id}_{source_file_id}",
        ):
            result = delete_project_data_file(project_id, source_file_id)
            if result["cleared_current_analysis"]:
                clear_active_analysis()
                message = "已删除当前分析数据对应的原始文件，请重新选择分析数据集。"
            else:
                message = f"已删除原始文件“{result['file'].get('file_name', source_file_id)}”。"
            st.session_state.data_source_message = message
            st.rerun()
    else:
        delete_column.info("生成类数据集暂不在此处删除；可在对应功能模块重新生成覆盖。")


def render_append_tables_tab(project_id: str) -> None:
    render_module_intro(
        "rows",
        "Append Tables",
        "数据合并",
        "把多个结构相同或相似的时间段数据表纵向追加为一个新的分析数据集副本。",
    )
    st.info(
        "Append 是纵向追加行，适合多个时间段同结构数据，例如 4-5月销售数据 + 6月销售数据。"
        "Join 是横向关联字段，适合订单表关联员工表、产品表等维表。"
    )
    sources = list_append_sources(project_id)
    if len(sources) < 2:
        st.warning("当前项目至少需要两个数据表，才能进行纵向合并。请先在“数据源”上传更多文件或 Sheet。")
        return

    source_labels = {source["source_id"]: source["label"] for source in sources}
    selected_source_ids = st.multiselect(
        "选择需要纵向合并的数据文件 / Sheet",
        options=[source["source_id"] for source in sources],
        default=[source["source_id"] for source in sources[:2]],
        format_func=lambda value: source_labels[value],
        key=f"append_source_select_{project_id}",
    )
    source_rows = [
        {
            "文件名": source["file_name"],
            "Sheet": source["sheet_name"],
            "行数": source["rows"],
            "列数": source["columns"],
        }
        for source in sources
    ]
    st.dataframe(source_rows, use_container_width=True, hide_index=True)

    if len(selected_source_ids) < 2:
        st.warning("请至少选择两个数据表进行字段对齐和合并。")
        return

    try:
        compatibility = analyze_append_compatibility(project_id, selected_source_ids)
    except Exception as exc:
        st.error(f"字段结构检测失败：{exc}")
        return

    st.subheader("字段对齐结果")
    metric_columns = st.columns(4)
    metric_columns[0].metric("选择表数", len(selected_source_ids))
    metric_columns[1].metric("共同字段", len(compatibility["common_fields"]))
    metric_columns[2].metric("合并后字段", len(compatibility["all_fields"]))
    metric_columns[3].metric("结构相似度", f"{compatibility['schema_similarity']:.0%}")

    with st.expander("以下字段将在合并时自动对齐", expanded=True):
        st.caption("这是系统检测到的只读结果，不需要在这里选择或修改字段。")
        if compatibility["common_fields"]:
            st.dataframe(
                pd.DataFrame({"自动对齐字段": compatibility["common_fields"]}),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning("所选表没有完全一致的共同字段。")

    selected_labels = [source_labels[source_id] for source_id in selected_source_ids]
    only_rows = []
    missing_rows = []
    missing_field_details = {}
    for source_id, label in zip(selected_source_ids, selected_labels):
        only_fields = compatibility["only_fields_by_source"].get(source_id, [])
        missing_fields = compatibility["missing_fields_by_source"].get(source_id, [])
        only_rows.append(
            {
                "数据表": label,
                "仅该表存在字段": "，".join(only_fields) if only_fields else "无",
            }
        )
        missing_rows.append(
            {
                "数据表": label,
                "需要补空字段": "，".join(missing_fields) if missing_fields else "无",
                "建议": "合并时自动补空" if missing_fields else "无需补空",
            }
        )
        for field in missing_fields:
            missing_field_details.setdefault(field, []).append(label)
    alignment_columns = st.columns(2)
    with alignment_columns[0]:
        st.markdown("#### 仅单表存在字段")
        st.dataframe(only_rows, use_container_width=True, hide_index=True)
    with alignment_columns[1]:
        st.markdown("#### 建议补空字段")
        st.dataframe(missing_rows, use_container_width=True, hide_index=True)

    if missing_field_details:
        st.markdown("#### 仅部分表存在字段")
        st.caption(
            "数据合并仅负责纵向追加行。缺失表中的这些字段将自动补 NaN；缺失值、异常值和字段清洗请在数据质量中心处理。"
        )
        missing_field_rows = []
        for field, missing_in in sorted(missing_field_details.items()):
            missing_field_rows.append(
                {
                    "字段名": field,
                    "缺失在哪些表": "；".join(missing_in),
                    "默认处理": "自动补 NaN",
                }
            )
        st.dataframe(missing_field_rows, use_container_width=True, hide_index=True)
    else:
        st.info("没有检测到仅部分表存在的字段。")

    if compatibility["field_order_different"]:
        st.info("检测到字段顺序不同，系统会按字段名对齐，不按位置合并。")
    else:
        st.success("字段顺序一致。")

    if compatibility["similar_fields"]:
        st.markdown("#### 字段名相似提示")
        st.dataframe(
            pd.DataFrame(compatibility["similar_fields"]),
            use_container_width=True,
            hide_index=True,
        )

    if st.button(
        "生成合并数据集",
        type="primary",
        key=f"build_appended_dataset_{project_id}",
    ):
        try:
            metadata = build_appended_dataset(
                project_id,
                selected_source_ids,
            )
            st.session_state.append_tables_message = (
                f"数据合并完成：合并前 {sum(item['rows'] for item in metadata['before_rows']):,} 行，"
                f"合并后 {metadata['after_rows']:,} 行。"
            )
            st.rerun()
        except Exception as exc:
            st.error(f"数据合并失败：{exc}")

    message = st.session_state.pop("append_tables_message", None)
    if message:
        st.success(message)

    metadata = get_appended_dataset_metadata(project_id)
    if not metadata:
        st.info("当前项目还没有生成合并数据集。")
        return

    st.subheader("合并结果")
    render_appended_dataset_summary(
        project_id,
        metadata,
        key_prefix="append_tables",
    )


def render_project_data_quality_tab(project_id: str) -> None:
    render_module_intro(
        "shield-check",
        "Quality center",
        "数据质量中心",
        "数据质量中心用于在正式建模和分析前检查缺失值、重复值和异常值，并生成不覆盖原始文件的清洗数据集。",
    )
    try:
        current_dataset = get_current_analysis_dataset(project_id)
        quality_df = load_current_analysis_dataframe(project_id)
    except Exception as exc:
        if str(exc) == NO_CURRENT_ANALYSIS_DATASET_MESSAGE:
            st.info(NO_CURRENT_ANALYSIS_DATASET_MESSAGE)
        else:
            st.error(f"当前分析数据集读取失败：{exc}")
        return
    if not current_dataset:
        st.info(NO_CURRENT_ANALYSIS_DATASET_MESSAGE)
        return

    header_cards = st.columns(4)
    header_cards[0].metric("当前分析数据集", current_dataset.get("dataset_name", "-"))
    header_cards[1].metric("行数", f"{len(quality_df):,}")
    header_cards[2].metric("列数", len(quality_df.columns))
    header_cards[3].metric("数据来源类型", current_dataset.get("dataset_type", "-"))
    st.caption(f"保存路径：{current_dataset.get('file_path', '-')}")
    st.info("所有处理都会生成 cleaned_dataset.csv，不覆盖原始文件。生成后可手动设为当前分析数据集。")

    st.subheader("A. 缺失值检测")
    missing_summary = summarize_missing_values_for_quality(quality_df)
    st.dataframe(missing_summary, use_container_width=True, hide_index=True)
    missing_preview = missing_sample_preview(quality_df)
    with st.expander("缺失样例预览", expanded=not missing_preview.empty):
        if missing_preview.empty:
            st.success("当前未检测到包含缺失值的记录。")
        else:
            st.dataframe(missing_preview, use_container_width=True, hide_index=True)

    operations: list[dict] = []
    st.subheader("B. 缺失值处理")
    missing_columns = [
        column for column in quality_df.columns if quality_df[column].isna().any()
    ]
    missing_method = st.selectbox(
        "缺失值处理方式",
        [
            "不处理",
            "删除含缺失值的行",
            "删除缺失率高于指定阈值的字段",
            "数值字段填 0",
            "数值字段填均值",
            "数值字段填中位数",
            "类别字段填众数",
            "文本/类别字段填“未知”",
            "自定义填充值",
        ],
        key=f"project_quality_missing_method_{project_id}",
    )
    if missing_method == "删除含缺失值的行":
        operations.append({"type": "drop_missing_rows"})
    elif missing_method == "删除缺失率高于指定阈值的字段":
        threshold_percent = st.slider(
            "缺失率阈值",
            min_value=1,
            max_value=100,
            value=80,
            step=1,
            key=f"project_quality_missing_threshold_{project_id}",
        )
        operations.append(
            {
                "type": "drop_high_missing_columns",
                "threshold": threshold_percent / 100,
            }
        )
    elif missing_method != "不处理":
        if not missing_columns:
            st.info("当前没有可处理的缺失字段。")
        else:
            missing_column = st.selectbox(
                "选择缺失字段",
                missing_columns,
                key=f"project_quality_missing_column_{project_id}",
            )
            custom_value = ""
            method_map = {
                "数值字段填 0": "zero",
                "数值字段填均值": "mean",
                "数值字段填中位数": "median",
                "类别字段填众数": "mode",
                "文本/类别字段填“未知”": "unknown",
                "自定义填充值": "custom",
            }
            if missing_method == "自定义填充值":
                custom_value = st.text_input(
                    "自定义填充值",
                    key=f"project_quality_missing_custom_{project_id}",
                )
            operations.append(
                {
                    "type": "fill_missing",
                    "column": missing_column,
                    "method": method_map[missing_method],
                    "custom_value": custom_value,
                }
            )

    st.subheader("C. 重复值检测")
    duplicate_summary = summarize_duplicates_for_quality(quality_df)
    duplicate_cards = st.columns(2)
    duplicate_cards[0].metric("重复行数量", f"{duplicate_summary['duplicate_count']:,}")
    duplicate_cards[1].metric("重复率", f"{duplicate_summary['duplicate_ratio']:.2f}%")
    with st.expander("重复样例预览", expanded=not duplicate_summary["preview"].empty):
        if duplicate_summary["preview"].empty:
            st.success("当前未检测到完全重复行。")
        else:
            st.dataframe(duplicate_summary["preview"], use_container_width=True)

    st.subheader("D. 重复值处理")
    if st.checkbox(
        "删除完全重复行",
        value=False,
        key=f"project_quality_drop_duplicates_{project_id}",
    ):
        operations.append({"type": "drop_duplicates"})

    st.subheader("E. 异常值检测")
    outlier_summary = summarize_iqr_outliers_for_quality(quality_df)
    if outlier_summary.empty:
        st.info("当前没有可用于 IQR 异常值检测的数值字段。")
    else:
        st.dataframe(outlier_summary, use_container_width=True, hide_index=True)

    st.subheader("F. 异常值处理")
    numeric_columns = get_iqr_numeric_measure_columns(quality_df)
    outlier_method = st.selectbox(
        "异常值处理方式",
        ["保留不处理", "删除异常值行", "Winsorize 截尾处理", "标记异常值字段"],
        key=f"project_quality_outlier_method_{project_id}",
    )
    if outlier_method != "保留不处理":
        if not numeric_columns:
            st.info("当前没有可处理的数值字段。")
        else:
            outlier_column = st.selectbox(
                "选择异常值字段",
                numeric_columns,
                key=f"project_quality_outlier_column_{project_id}",
            )
            outlier_method_map = {
                "删除异常值行": "drop_rows",
                "Winsorize 截尾处理": "winsorize",
                "标记异常值字段": "mark",
            }
            operations.append(
                {
                    "type": "outlier",
                    "column": outlier_column,
                    "method": outlier_method_map[outlier_method],
                }
            )

    st.subheader("生成清洗数据集")
    if operations:
        st.caption(f"待执行处理步骤：{len(operations)} 个")
        st.caption("详细处理内容已在上方清洗计划摘要中展示；点击按钮会生成独立的 cleaned_dataset.csv。")
    else:
        st.caption("当前没有待执行处理步骤，可以直接保留当前数据集。")

    if st.button(
        "生成清洗数据集",
        type="primary",
        key=f"project_quality_create_cleaned_{project_id}",
    ):
        try:
            metadata = create_cleaned_dataset(project_id, operations)
            st.session_state.project_quality_message = (
                f"已生成 cleaned_dataset.csv：{metadata['before_rows']:,} 行 -> {metadata['after_rows']:,} 行。"
            )
            st.rerun()
        except Exception as exc:
            st.error(f"清洗数据集生成失败：{exc}")

    message = st.session_state.pop("project_quality_message", None)
    if message:
        st.success(message)

    metadata = get_cleaned_dataset_metadata(project_id)
    if metadata:
        st.markdown("#### 清洗结果摘要")
        result_cards = st.columns(4)
        result_cards[0].metric("处理前行数", f"{metadata.get('before_rows', 0):,}")
        result_cards[1].metric("处理后行数", f"{metadata.get('after_rows', 0):,}")
        result_cards[2].metric("处理前列数", metadata.get("before_columns", 0))
        result_cards[3].metric("处理后列数", metadata.get("after_columns", 0))
        st.caption(f"生成时间：{metadata.get('created_at', '-')}")
        st.caption(f"保存位置：{metadata.get('file_path', '-')}")
        try:
            cleaned_df = load_cleaned_dataset(project_id)
            st.download_button(
                "下载清洗数据集 CSV",
                data=cleaned_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                file_name="cleaned_dataset.csv",
                mime="text/csv",
                key=f"project_quality_download_cleaned_{project_id}",
            )
            render_dataset_preview(
                cleaned_df,
                "cleaned_dataset.csv",
                show_download=False,
                key_prefix=f"quality_after_preview_{project_id}_cleaned_dataset",
            )
            if st.button(
                "设为当前分析数据集",
                type="primary",
                key=f"project_quality_set_cleaned_current_{project_id}",
            ):
                set_cleaned_dataset_as_current(project_id)
                clear_active_analysis()
                st.session_state.project_quality_message = "已将 cleaned_dataset.csv 设为当前分析数据集。"
                st.rerun()
        except Exception as exc:
            st.warning(f"清洗数据集暂不可用：{exc}")


def render_project_data_quality_tab(project_id: str) -> None:
    render_module_intro(
        "shield-check",
        "Quality center",
        "数据质量中心",
        "数据质量中心用于在正式建模和分析前检查缺失值、重复值和异常值，并生成不覆盖原始文件的清洗数据集。",
    )

    try:
        current_dataset = get_current_analysis_dataset(project_id)
        quality_df = load_current_analysis_dataframe(project_id)
    except Exception as exc:
        if str(exc) == NO_CURRENT_ANALYSIS_DATASET_MESSAGE:
            st.info(NO_CURRENT_ANALYSIS_DATASET_MESSAGE)
        else:
            st.error(f"当前分析数据集读取失败：{exc}")
        return

    if not current_dataset:
        st.info(NO_CURRENT_ANALYSIS_DATASET_MESSAGE)
        return

    def _missing_summary(df: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for column in df.columns:
            missing_count = int(df[column].isna().sum())
            rows.append(
                {
                    "字段名": column,
                    "数据类型": str(df[column].dtype),
                    "缺失值数量": missing_count,
                    "缺失率": round(missing_count / max(len(df), 1) * 100, 2),
                }
            )
        return pd.DataFrame(rows).sort_values("缺失率", ascending=False, ignore_index=True)

    def _missing_preview(df: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
        preview = df.loc[df.isna().any(axis=1)].head(limit).copy()
        if preview.empty:
            return preview
        preview.insert(0, "原始行索引", preview.index)
        return preview.reset_index(drop=True)

    def _outlier_summary(df: pd.DataFrame) -> pd.DataFrame:
        rows = []
        numeric_columns_for_summary = get_iqr_numeric_measure_columns(df)
        for column in numeric_columns_for_summary:
            bounds = calculate_iqr_bounds(df, column)
            series = pd.to_numeric(df[column], errors="coerce")
            if pd.isna(bounds["lower_bound"]) or pd.isna(bounds["upper_bound"]):
                mask = pd.Series(False, index=df.index)
            else:
                mask = (series < bounds["lower_bound"]) | (series > bounds["upper_bound"])
            valid_count = int(series.notna().sum())
            rows.append(
                {
                    "字段名": column,
                    "Q1": bounds["q1"],
                    "Q3": bounds["q3"],
                    "IQR": bounds["iqr"],
                    "下界": bounds["lower_bound"],
                    "上界": bounds["upper_bound"],
                    "异常值数量": int(mask.sum()),
                    "异常值比例": round(int(mask.sum()) / max(valid_count, 1) * 100, 2),
                }
            )
        return pd.DataFrame(rows)

    def _outlier_mask(df: pd.DataFrame, column: str, bounds: dict | None = None) -> pd.Series:
        bounds = bounds or calculate_iqr_bounds(df, column)
        series = pd.to_numeric(df[column], errors="coerce")
        if pd.isna(bounds["lower_bound"]) or pd.isna(bounds["upper_bound"]):
            return pd.Series(False, index=df.index)
        return (series < bounds["lower_bound"]) | (series > bounds["upper_bound"])

    def _outlier_preview(df: pd.DataFrame, column: str, mask: pd.Series, limit: int = 50) -> pd.DataFrame:
        preview = df.loc[mask].head(limit).copy()
        if preview.empty:
            return preview
        preview.insert(0, "原始行索引", preview.index)
        context_columns = [column] + [c for c in df.columns if c != column][:8]
        return preview[["原始行索引"] + [c for c in context_columns if c in preview.columns]].reset_index(drop=True)

    def _numeric_compare(before: pd.DataFrame, after: pd.DataFrame, column: str) -> pd.DataFrame:
        def stats(frame: pd.DataFrame) -> dict:
            series = pd.to_numeric(frame[column], errors="coerce").dropna()
            bounds = calculate_iqr_bounds(frame, column)
            mask = _outlier_mask(frame, column, bounds)
            return {
                "行数": len(frame),
                "异常值数量": int(mask.sum()),
                "均值": series.mean(),
                "中位数": series.median(),
                "最大值": series.max(),
                "最小值": series.min(),
                "标准差": series.std(),
                "偏度": series.skew(),
                "峰度": series.kurt(),
            }

        before_stats = stats(before)
        after_stats = stats(after)
        return pd.DataFrame(
            [
                {"指标": metric, "处理前": before_stats[metric], "处理后": after_stats[metric]}
                for metric in before_stats
            ]
        ).round(3)

    def _format_number(value: object) -> str:
        if pd.isna(value):
            return "-"
        try:
            return f"{float(value):,.2f}"
        except (TypeError, ValueError):
            return str(value)

    def _operation_label(operation: dict) -> str:
        op_type = operation.get("type")
        if op_type == "drop_missing_rows":
            return "删除含缺失值的行"
        if op_type == "drop_high_missing_columns":
            return f"删除缺失率超过 {operation.get('threshold', 0.8):.0%} 的字段"
        if op_type == "fill_missing":
            method_labels = {
                "zero": "填 0",
                "mean": "填均值",
                "median": "填中位数",
                "mode": "填众数",
                "unknown": "填“未知”",
                "custom": "自定义填充值",
            }
            return f"{operation.get('column', '-')}：{method_labels.get(operation.get('method'), operation.get('method'))}"
        if op_type == "drop_duplicates":
            return "删除完全重复行（每组保留第一条）"
        if op_type == "outlier":
            method_labels = {
                "drop_rows": "删除异常值行",
                "winsorize": "Winsorize 截尾到上下界",
                "mark": "新增标记列",
            }
            return f"{operation.get('column', '-')}：{method_labels.get(operation.get('method'), operation.get('method'))}"
        return str(operation)

    auto_identifier_columns = detect_quality_identifier_columns(quality_df)
    if st.session_state.get("manual_id_columns_project_id") != project_id:
        st.session_state.manual_id_columns_project_id = project_id
        st.session_state.manual_id_columns = []
        st.session_state.manual_non_id_columns = []
    manual_id_columns = [
        column
        for column in st.session_state.setdefault("manual_id_columns", [])
        if column in quality_df.columns
    ]
    manual_non_id_columns = [
        column
        for column in st.session_state.setdefault("manual_non_id_columns", [])
        if column in quality_df.columns
    ]
    st.session_state.manual_id_columns = manual_id_columns
    st.session_state.manual_non_id_columns = manual_non_id_columns
    identifier_columns = get_final_id_columns(
        quality_df,
        auto_identifier_columns,
        manual_id_columns,
        manual_non_id_columns,
    )
    invalid_columns = detect_quality_invalid_columns(quality_df)
    outlier_summary = summarize_iqr_outliers_for_quality(quality_df, identifier_columns)
    quality_overview = summarize_quality_overview(
        quality_df,
        identifier_columns=identifier_columns,
        invalid_columns=invalid_columns,
        outlier_summary=outlier_summary,
    )
    duplicate_summary = summarize_duplicates_for_quality(quality_df)

    missing_summary = summarize_missing_values_for_quality(quality_df)
    missing_preview = _missing_preview(quality_df)
    repair_suggestions = generate_data_repair_suggestions_for_quality(
        quality_df,
        identifier_columns,
        invalid_columns,
        outlier_summary,
    )
    outlier_field_count = (
        int((outlier_summary["异常值数量"] > 0).sum())
        if not outlier_summary.empty
        else 0
    )
    outlier_fields = (
        outlier_summary.loc[outlier_summary["异常值数量"] > 0, "字段名"].astype(str).tolist()
        if not outlier_summary.empty
        else []
    )
    if st.session_state.get("missing_value_plan_project_id") != project_id:
        st.session_state.missing_value_plan_project_id = project_id
        st.session_state.missing_value_plan = []
    missing_value_plan = st.session_state.setdefault("missing_value_plan", [])
    if st.session_state.get("duplicate_handling_plan_project_id") != project_id:
        st.session_state.duplicate_handling_plan_project_id = project_id
        st.session_state.duplicate_handling_plan = {"method": "none"}
    duplicate_handling_plan = st.session_state.setdefault(
        "duplicate_handling_plan",
        {"method": "none"},
    )
    operations: list[dict] = [
        *missing_value_plan_to_operations(missing_value_plan),
        *duplicate_handling_plan_to_operations(duplicate_handling_plan),
    ]

    overview_tab, missing_tab, duplicate_tab, id_tab, outlier_tab, repair_tab = st.tabs(
        ["总览", "缺失值", "重复值", "ID识别", "异常值", "数据修复"]
    )

    with overview_tab:
        overview_top = st.columns(5)
        overview_top[0].metric("当前分析数据集", current_dataset.get("dataset_name", "-"))
        overview_top[1].metric("数据来源类型", current_dataset.get("dataset_type", "-"))
        overview_top[2].metric("行数", f"{len(quality_df):,}")
        overview_top[3].metric("列数", len(quality_df.columns))
        overview_top[4].metric("数据质量评分", f"{quality_overview['score']} / 100")
        overview_bottom = st.columns(6)
        overview_bottom[0].metric("缺失值总数", f"{quality_overview['missing_values']:,}")
        overview_bottom[1].metric("重复行数量", f"{quality_overview['duplicate_rows']:,}")
        overview_bottom[2].metric("最终排除ID字段数", quality_overview["identifier_column_count"])
        overview_bottom[3].metric("异常字段数量", quality_overview["suspicious_column_count"])
        overview_bottom[4].metric("异常值字段数", outlier_field_count)
        overview_bottom[5].metric("异常值数量", f"{quality_overview['outlier_count']:,}")
        st.caption(f"保存路径：{current_dataset.get('file_path', '-')}")

        conclusion_lines = []
        if quality_overview["missing_values"] == 0:
            conclusion_lines.append("未检测到缺失值。")
        else:
            conclusion_lines.append(f"检测到 {quality_overview['missing_values']:,} 个缺失值，请优先查看缺失值诊断。")
        if quality_overview["duplicate_rows"] == 0:
            conclusion_lines.append("未检测到完全重复行。")
        else:
            conclusion_lines.append(f"检测到 {quality_overview['duplicate_rows']:,} 行完全重复记录。")
        if identifier_columns:
            conclusion_lines.append(f"识别到疑似 ID 字段：{', '.join(map(str, identifier_columns))}。")
        if outlier_fields:
            conclusion_lines.append(f"检测到存在 IQR 异常值的字段：{', '.join(outlier_fields)}；异常值不一定是错误数据，请结合业务场景判断。")
        elif not outlier_summary.empty:
            conclusion_lines.append("当前可分析数值字段未检测到 IQR 异常值。")
        with st.container(border=True):
            st.markdown("#### 数据质量结论")
            for line in conclusion_lines[:4]:
                st.markdown(f"- {line}")

        st.markdown("#### 数据修复建议")
        if not repair_suggestions.empty:
            suggestion_columns = [
                column
                for column in ["问题类型", "涉及字段", "严重程度", "影响", "推荐操作", "建议处理位置"]
                if column in repair_suggestions.columns
            ]
            st.dataframe(
                repair_suggestions[suggestion_columns],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("当前未发现需要优先处理的数据质量问题。")

    with missing_tab:
        st.markdown("#### 缺失值诊断")
        missing_cards = st.columns(3)
        missing_cards[0].metric("缺失值总数", f"{quality_overview['missing_values']:,}")
        if missing_summary.empty:
            missing_cards[1].metric("存在缺失的字段数", 0)
            missing_cards[2].metric("高缺失字段数", 0)
            st.info("当前数据集没有可诊断字段。")
        else:
            missing_cards[1].metric("存在缺失的字段数", int((missing_summary["缺失值数量"] > 0).sum()))
            missing_cards[2].metric("高缺失字段数", int((missing_summary["缺失值比例"] >= 80).sum()))
            st.dataframe(missing_summary, use_container_width=True, hide_index=True)
        with st.expander("缺失样例预览", expanded=not missing_preview.empty):
            if missing_preview.empty:
                st.success("当前未检测到包含缺失值的记录。")
            else:
                st.dataframe(missing_preview, use_container_width=True, hide_index=True)

        st.markdown("#### 缺失值处理")
        missing_columns = [column for column in quality_df.columns if quality_df[column].isna().any()]
        if not missing_columns:
            st.info("当前没有可处理的缺失字段。")
        else:
            missing_column = st.selectbox(
                "选择缺失字段",
                missing_columns,
                key=f"project_quality_missing_plan_column_{project_id}",
            )
            selected_series = quality_df[missing_column]
            method_options = ["不处理", "删除字段", "删除含缺失值的行", "众数填充", "固定值填充"]
            if pd.api.types.is_numeric_dtype(selected_series):
                method_options[3:3] = ["均值填充", "中位数填充"]
            missing_method = st.selectbox(
                "处理方式",
                method_options,
                key=f"project_quality_missing_plan_method_{project_id}",
            )
            method_map = {
                "不处理": "none",
                "删除字段": "drop_column",
                "删除含缺失值的行": "drop_rows",
                "均值填充": "mean",
                "中位数填充": "median",
                "众数填充": "mode",
                "固定值填充": "custom",
            }
            fill_value = ""
            if missing_method == "固定值填充":
                fill_value = st.text_input(
                    "固定填充值",
                    key=f"project_quality_missing_plan_fill_value_{project_id}",
                )
            if st.button(
                "加入处理计划",
                type="primary",
                key=f"project_quality_add_missing_plan_{project_id}",
            ):
                st.session_state.missing_value_plan = upsert_missing_value_plan_item(
                    st.session_state.get("missing_value_plan", []),
                    {
                        "column": missing_column,
                        "method": method_map[missing_method],
                        "fill_value": fill_value,
                    },
                )
                st.rerun()

        st.markdown("#### 当前缺失值处理计划")
        plan_table = format_missing_value_plan(
            st.session_state.get("missing_value_plan", []),
            quality_df,
        )
        if plan_table.empty:
            st.info("尚未添加缺失值处理步骤。")
        else:
            st.dataframe(plan_table, use_container_width=True, hide_index=True)
            remove_column = st.selectbox(
                "选择要移除的计划字段",
                [step["column"] for step in st.session_state.get("missing_value_plan", [])],
                key=f"project_quality_remove_missing_plan_column_{project_id}",
            )
            if st.button(
                "移除处理步骤",
                key=f"project_quality_remove_missing_plan_{project_id}",
            ):
                st.session_state.missing_value_plan = remove_missing_value_plan_item(
                    st.session_state.get("missing_value_plan", []),
                    remove_column,
                )
                st.rerun()

        st.markdown("#### 处理后预览")
        if not st.session_state.get("missing_value_plan"):
            st.info("尚未添加缺失值处理步骤。")
        else:
            try:
                missing_effect = summarize_missing_value_plan_effect(
                    quality_df,
                    st.session_state.get("missing_value_plan", []),
                )
                effect_cards = st.columns(6)
                effect_cards[0].metric("处理前缺失值总数", f"{missing_effect['before_missing_values']:,}")
                effect_cards[1].metric("预计处理后缺失值总数", f"{missing_effect['after_missing_values']:,}")
                effect_cards[2].metric("处理前行数", f"{missing_effect['before_rows']:,}")
                effect_cards[3].metric("预计处理后行数", f"{missing_effect['after_rows']:,}")
                effect_cards[4].metric("处理前列数", missing_effect["before_columns"])
                effect_cards[5].metric("预计处理后列数", missing_effect["after_columns"])
                st.caption("以下预览基于当前缺失值处理计划生成，不会覆盖原始数据。")
                missing_preview_after = apply_missing_value_plan_preview(
                    quality_df,
                    st.session_state.get("missing_value_plan", []),
                )
                st.dataframe(missing_preview_after.head(20), use_container_width=True)
            except Exception as exc:
                st.warning(f"暂时无法生成缺失值处理后预览：{exc}")

    with duplicate_tab:
        st.markdown("#### 重复值诊断")
        duplicate_cols = st.columns(2)
        duplicate_cols[0].metric("重复组涉及行数", f"{duplicate_summary['duplicate_group_rows']:,}")
        duplicate_cols[1].metric("重复行占比", f"{duplicate_summary['duplicate_ratio']:.2f}%")
        duplicate_preview = duplicate_summary["preview"].copy()
        if not duplicate_preview.empty:
            duplicate_preview.insert(0, "原始行索引", duplicate_preview.index)
        with st.expander("重复行预览", expanded=duplicate_summary["duplicate_count"] > 0):
            st.caption("以下展示所有处于重复组中的记录，系统会按照完整行内容判断重复。")
            if duplicate_preview.empty:
                st.success("当前未检测到完全重复行。")
            else:
                st.dataframe(duplicate_preview, use_container_width=True, hide_index=True)

        st.markdown("#### 重复值处理")
        duplicate_method = st.selectbox(
            "重复值处理方式",
            ["不处理", "删除完全重复行（每组保留第一条）", "删除选中重复行"],
            key=f"project_quality_duplicate_method_v3_{project_id}",
        )
        if duplicate_method == "不处理":
            if st.button(
                "清空重复值处理计划",
                key=f"project_quality_duplicate_plan_none_{project_id}",
            ):
                st.session_state.duplicate_handling_plan = upsert_duplicate_handling_plan(
                    st.session_state.get("duplicate_handling_plan"),
                    {"method": "none"},
                )
                st.rerun()
        elif duplicate_method == "删除完全重复行（每组保留第一条）":
            st.caption("该方式会对每组完全相同的记录保留第一条，删除其余重复记录。")
            if st.button(
                "加入重复值处理计划",
                type="primary",
                key=f"project_quality_duplicate_plan_all_{project_id}",
            ):
                st.session_state.duplicate_handling_plan = upsert_duplicate_handling_plan(
                    st.session_state.get("duplicate_handling_plan"),
                    {"method": "drop_all_duplicates"},
                )
                st.rerun()
        elif duplicate_method == "删除选中重复行":
            st.caption("该方式仅删除你在重复行预览中选中的原始行索引。")
            if duplicate_preview.empty:
                st.info("当前没有可选择删除的重复行。")
            else:
                editable_duplicate_preview = duplicate_preview.copy()
                editable_duplicate_preview.insert(0, "删除", False)
                edited_duplicate_preview = st.data_editor(
                    editable_duplicate_preview,
                    use_container_width=True,
                    hide_index=True,
                    disabled=[
                        column
                        for column in editable_duplicate_preview.columns
                        if column != "删除"
                    ],
                    key=f"project_quality_duplicate_selected_rows_{project_id}",
                )
                if st.button(
                    "按选中行加入处理计划",
                    type="primary",
                    key=f"project_quality_duplicate_plan_selected_{project_id}",
                ):
                    if "原始行索引" not in edited_duplicate_preview.columns:
                        st.warning("缺少稳定的原始行索引，无法按选中行删除。")
                    else:
                        selected_rows = edited_duplicate_preview[
                            edited_duplicate_preview["删除"].astype(bool)
                        ]
                        selected_indices = selected_rows["原始行索引"].tolist()
                        if not selected_indices:
                            st.warning("请先勾选要删除的重复行。")
                        else:
                            st.session_state.duplicate_handling_plan = upsert_duplicate_handling_plan(
                                st.session_state.get("duplicate_handling_plan"),
                                {
                                    "method": "drop_selected_rows",
                                    "row_indices": selected_indices,
                                },
                            )
                            st.rerun()

        st.markdown("#### 当前重复值处理计划")
        duplicate_plan_table = format_duplicate_handling_plan(
            st.session_state.get("duplicate_handling_plan"),
            quality_df,
        )
        if duplicate_plan_table.empty:
            st.info("尚未添加重复值处理步骤。")
        else:
            st.dataframe(duplicate_plan_table, use_container_width=True, hide_index=True)
            if st.button(
                "移除重复值处理步骤",
                key=f"project_quality_duplicate_plan_remove_{project_id}",
            ):
                st.session_state.duplicate_handling_plan = upsert_duplicate_handling_plan(
                    st.session_state.get("duplicate_handling_plan"),
                    {"method": "none"},
                )
                st.rerun()

        st.markdown("#### 处理结果预览")
        if not duplicate_handling_plan_to_operations(st.session_state.get("duplicate_handling_plan")):
            st.info("尚未添加重复值处理步骤。")
        else:
            try:
                duplicate_effect = summarize_duplicate_handling_effect(
                    quality_df,
                    st.session_state.get("duplicate_handling_plan"),
                )
                duplicate_effect_cards = st.columns(5)
                duplicate_effect_cards[0].metric("处理前总行数", f"{duplicate_effect['before_rows']:,}")
                duplicate_effect_cards[1].metric("预计处理后总行数", f"{duplicate_effect['after_rows']:,}")
                duplicate_effect_cards[2].metric("重复组涉及行数", f"{duplicate_effect['duplicate_group_rows']:,}")
                duplicate_effect_cards[3].metric("预计删除重复行数", f"{duplicate_effect['removed_rows']:,}")
                duplicate_effect_cards[4].metric("处理后剩余重复行数", f"{duplicate_effect['after_duplicate_group_rows']:,}")
                duplicate_group_preview_after = apply_duplicate_group_preview(
                    quality_df,
                    st.session_state.get("duplicate_handling_plan"),
                )
                duplicate_preview_after = apply_duplicate_handling_plan_preview(
                    quality_df,
                    st.session_state.get("duplicate_handling_plan"),
                )
                st.markdown("##### 重复组处理后预览")
                st.caption("以下仅展示原重复组在应用当前重复值处理计划后的剩余记录。")
                if duplicate_group_preview_after.empty:
                    st.success("应用当前重复值处理计划后，原重复组中没有剩余记录。")
                else:
                    st.dataframe(duplicate_group_preview_after.head(20), use_container_width=True)
                st.markdown("##### 全表处理后预览")
                st.caption("以下展示全量数据应用当前重复值处理计划后的前 20 行，不会修改原始数据。")
                st.dataframe(duplicate_preview_after.head(20), use_container_width=True)
            except Exception as exc:
                st.warning(f"暂时无法生成重复值处理后预览：{exc}")

    with id_tab:
        st.markdown("#### ID字段识别")
        st.caption("ID字段通常用于定位记录，不适合做均值、偏度、异常值检测、相关性分析、箱线图或数值分布图。")
        identifier_summary = summarize_identifier_columns(quality_df, auto_identifier_columns)
        if identifier_summary.empty:
            st.info("当前未自动识别到疑似 ID 字段。")
        else:
            status_map = {}
            for column in auto_identifier_columns:
                if column in manual_non_id_columns:
                    status_map[column] = "已人工取消ID"
                elif column in manual_id_columns:
                    status_map[column] = "已人工标记为ID"
                else:
                    status_map[column] = "自动识别为ID"
            identifier_summary["当前状态"] = identifier_summary["字段名"].map(status_map).fillna("自动识别为ID")
            st.dataframe(identifier_summary, use_container_width=True, hide_index=True)

        st.markdown("#### 人工调整 ID 字段")
        adjustment_cols = st.columns([2, 2, 1])
        selected_id_column = adjustment_cols[0].selectbox(
            "选择字段",
            list(quality_df.columns),
            key=f"project_quality_id_override_column_{project_id}",
        )
        selected_id_action = adjustment_cols[1].selectbox(
            "操作",
            ["标记为 ID 字段", "取消 ID 标记"],
            key=f"project_quality_id_override_action_{project_id}",
        )
        if adjustment_cols[2].button(
            "应用调整",
            type="primary",
            key=f"project_quality_apply_id_override_{project_id}",
        ):
            action = "mark_id" if selected_id_action == "标记为 ID 字段" else "mark_non_id"
            manual_ids, manual_non_ids = update_id_override_state(
                quality_df,
                st.session_state.get("manual_id_columns", []),
                st.session_state.get("manual_non_id_columns", []),
                selected_id_column,
                action,
            )
            st.session_state.manual_id_columns = manual_ids
            st.session_state.manual_non_id_columns = manual_non_ids
            st.rerun()

        final_id_rows = []
        for column in identifier_columns:
            if column in manual_id_columns:
                source = "人工标记"
            else:
                source = "自动识别"
            final_id_rows.append({"字段名": column, "来源": source, "状态": "最终排除"})
        st.markdown("#### 当前最终排除字段")
        if final_id_rows:
            st.dataframe(pd.DataFrame(final_id_rows), use_container_width=True, hide_index=True)
        else:
            st.info("当前没有最终排除的 ID 字段。")

        cancelled_auto_ids = [
            column for column in manual_non_id_columns if column in auto_identifier_columns
        ]
        st.markdown("#### 已人工取消 ID 标记字段")
        if cancelled_auto_ids:
            st.dataframe(
                pd.DataFrame(
                    [
                        {"字段名": column, "来源": "自动识别后人工取消", "状态": "参与数值分析"}
                        for column in cancelled_auto_ids
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("暂无人工取消的 ID 标记字段。")

        cancelled_still_excluded_from_iqr = [
            column
            for column in manual_non_id_columns
            if column in quality_df.columns
            and pd.api.types.is_numeric_dtype(quality_df[column])
            and column not in get_iqr_numeric_measure_columns(quality_df, identifier_columns)
        ]
        if cancelled_still_excluded_from_iqr:
            st.caption(
                "以下字段已取消 ID 标记，但字段名仍命中工号、编号、单号等排除规则，"
                f"不会进入异常值字段下拉框：{', '.join(map(str, cancelled_still_excluded_from_iqr))}"
            )

        if st.button(
            "重置人工调整",
            key=f"project_quality_reset_id_override_{project_id}",
        ):
            manual_ids, manual_non_ids = reset_id_override_state()
            st.session_state.manual_id_columns = manual_ids
            st.session_state.manual_non_id_columns = manual_non_ids
            st.rerun()

        if invalid_columns:
            st.warning(f"检测到疑似无效字段：{', '.join(map(str, invalid_columns))}。建议确认业务含义后处理。")

    with outlier_tab:
        st.markdown("#### 异常值诊断与处理")
        st.caption("使用 IQR 方法识别统计异常值。异常值不一定是错误数据，请结合业务场景判断。")
        if outlier_summary.empty:
            st.info("当前没有可用于 IQR 异常值检测的数值字段。")
        else:
            st.dataframe(outlier_summary, use_container_width=True, hide_index=True)
            if identifier_columns:
                st.info(f"已排除疑似 ID 字段：{', '.join(map(str, identifier_columns))}。这些字段不参与异常值检测和处理。")

        numeric_columns = get_iqr_numeric_measure_columns(quality_df, identifier_columns)
        selected_outlier_column = None
        selected_outlier_operation = None
        if not numeric_columns:
            st.info("当前没有可用于异常值分析的数值字段。")
        else:
            selected_outlier_column = st.selectbox(
                "选择数值字段查看 IQR 异常值分析",
                numeric_columns,
                key=f"project_quality_outlier_column_v2_{project_id}",
            )
            st.caption("IQR 是一种统计检测方法。超过上下界的数据会被标记为统计异常值，但异常值不一定是错误数据，请结合业务场景判断。")
            bounds = calculate_iqr_bounds(quality_df, selected_outlier_column)
            mask = _outlier_mask(quality_df, selected_outlier_column, bounds)
            valid_count = int(pd.to_numeric(quality_df[selected_outlier_column], errors="coerce").notna().sum())
            outlier_count = int(mask.sum())
            iqr_cols = st.columns(7)
            iqr_cols[0].metric("Q1", _format_number(bounds["q1"]))
            iqr_cols[1].metric("Q3", _format_number(bounds["q3"]))
            iqr_cols[2].metric("IQR", _format_number(bounds["iqr"]))
            iqr_cols[3].metric("下界", _format_number(bounds["lower_bound"]))
            iqr_cols[4].metric("上界", _format_number(bounds["upper_bound"]))
            iqr_cols[5].metric("异常值数量", f"{outlier_count:,}")
            iqr_cols[6].metric("异常值占比", f"{outlier_count / max(valid_count, 1) * 100:.2f}%")

            render_outlier_visualization(
                quality_df,
                selected_outlier_column,
                {"bounds": bounds, "mask": mask},
                key_prefix=f"project_quality_{project_id}_{selected_outlier_column}",
            )

            outlier_preview = _outlier_preview(quality_df, selected_outlier_column, mask)
            with st.expander("异常值样例表", expanded=not outlier_preview.empty):
                if outlier_preview.empty:
                    st.success("当前字段未检测到 IQR 异常值。")
                else:
                    st.dataframe(outlier_preview, use_container_width=True, hide_index=True)
                    st.download_button(
                        "下载异常值样例 CSV",
                        data=outlier_preview.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                        file_name=f"outlier_preview_{selected_outlier_column}.csv",
                        mime="text/csv",
                        key=f"project_quality_outlier_preview_download_{project_id}_{selected_outlier_column}",
                    )

            st.markdown("#### 异常值处理")
            outlier_method = st.selectbox(
                "异常值处理方式",
                ["不处理", "删除异常值行", "Winsorize 截尾到上下界", "新增标记列"],
                key=f"project_quality_outlier_method_v2_{project_id}",
            )
            outlier_method_map = {
                "删除异常值行": "drop_rows",
                "Winsorize 截尾到上下界": "winsorize",
                "新增标记列": "mark",
            }
            if outlier_method != "不处理":
                selected_outlier_operation = {
                    "type": "outlier",
                    "column": selected_outlier_column,
                    "method": outlier_method_map[outlier_method],
                }
                operations.append(selected_outlier_operation)
                try:
                    preview_after_df, _ = apply_quality_operations(
                        quality_df,
                        [selected_outlier_operation],
                    )
                    st.markdown("#### 处理前后对比")
                    st.dataframe(
                        _numeric_compare(quality_df, preview_after_df, selected_outlier_column),
                        use_container_width=True,
                        hide_index=True,
                    )
                    comparison_cols = st.columns(2)
                    before_values = pd.to_numeric(quality_df[selected_outlier_column], errors="coerce").dropna()
                    after_values = pd.to_numeric(preview_after_df[selected_outlier_column], errors="coerce").dropna()
                    before_fig = px.histogram(
                        before_values.to_frame(name=selected_outlier_column),
                        x=selected_outlier_column,
                        title="处理前分布图",
                        color_discrete_sequence=["#2563EB"],
                    )
                    after_fig = px.histogram(
                        after_values.to_frame(name=selected_outlier_column),
                        x=selected_outlier_column,
                        title="处理后分布图",
                        color_discrete_sequence=["#16A34A"],
                    )
                    for fig in (before_fig, after_fig):
                        fig.update_layout(
                            height=300,
                            template="plotly_white",
                            margin={"l": 24, "r": 24, "t": 54, "b": 40},
                        )
                        fig.update_xaxes(separatethousands=True)
                    comparison_cols[0].plotly_chart(
                        before_fig,
                        use_container_width=True,
                        key=f"project_quality_before_distribution_{project_id}_{selected_outlier_column}",
                    )
                    comparison_cols[1].plotly_chart(
                        after_fig,
                        use_container_width=True,
                        key=f"project_quality_after_distribution_{project_id}_{selected_outlier_column}",
                    )
                except Exception as exc:
                    st.warning(f"暂时无法生成处理前后对比：{exc}")

        with st.expander("AI / 规则洞察", expanded=False):
            st.info("当前数据质量中心使用规则型诊断与 IQR 检测；AI 洞察未在此区域默认展开。")

    with repair_tab:
        st.markdown("#### 清洗计划总览")
        missing_plan_table = format_missing_value_plan(
            st.session_state.get("missing_value_plan", []),
            quality_df,
        )
        st.markdown("##### 缺失值处理步骤")
        if missing_plan_table.empty:
            st.info("暂无缺失值处理步骤。")
        else:
            st.dataframe(missing_plan_table, use_container_width=True, hide_index=True)

        st.markdown("##### ID字段调整")
        id_adjustment_rows = [
            {
                "配置项": "最终排除字段",
                "字段": ", ".join(map(str, identifier_columns)) if identifier_columns else "无",
            },
            {
                "配置项": "人工标记为ID",
                "字段": ", ".join(map(str, manual_id_columns)) if manual_id_columns else "无",
            },
            {
                "配置项": "人工取消ID标记",
                "字段": ", ".join(map(str, manual_non_id_columns)) if manual_non_id_columns else "无",
            },
        ]
        if manual_id_columns or manual_non_id_columns:
            st.dataframe(pd.DataFrame(id_adjustment_rows), use_container_width=True, hide_index=True)
        else:
            st.info("暂无人工 ID 字段调整。")

        duplicate_plan_table = format_duplicate_handling_plan(
            st.session_state.get("duplicate_handling_plan"),
            quality_df,
        )
        st.markdown("##### 重复值处理步骤")
        if duplicate_plan_table.empty:
            st.info("暂无重复值处理步骤。")
        else:
            st.dataframe(duplicate_plan_table, use_container_width=True, hide_index=True)

        outlier_steps = [operation for operation in operations if operation.get("type") == "outlier"]
        st.markdown("##### 异常值处理步骤")
        if outlier_steps:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "处理步骤": _operation_label(step),
                            "预计影响": "按当前异常值处理方式生成清洗结果",
                            "状态": "待执行",
                        }
                        for step in outlier_steps
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("暂无异常值处理步骤。")

        st.markdown("#### 预计处理影响")
        try:
            preview_after_df, preview_steps = apply_quality_operations(quality_df, operations)
            preview_cards = st.columns(4)
            preview_cards[0].metric("处理前行数", f"{len(quality_df):,}")
            preview_cards[1].metric("处理后预计行数", f"{len(preview_after_df):,}")
            preview_cards[2].metric("处理前列数", len(quality_df.columns))
            preview_cards[3].metric("处理后预计列数", len(preview_after_df.columns))
            st.metric("预计剩余缺失值数量", f"{int(preview_after_df.isna().sum().sum()):,}")
            if preview_steps:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "处理步骤": _operation_label(step),
                                "处理前行数": step.get("before_rows"),
                                "处理后行数": step.get("after_rows"),
                                "处理前列数": step.get("before_columns"),
                                "处理后列数": step.get("after_columns"),
                            }
                            for step in preview_steps
                        ]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("当前没有待执行处理步骤，可以直接保留当前数据集。")
            st.markdown("#### 最终处理后预览")
            st.caption("以下预览基于当前清洗计划生成，不会覆盖原始数据或当前数据。")
            st.dataframe(preview_after_df.head(20), use_container_width=True)
        except Exception as exc:
            st.warning(f"暂时无法生成处理前后预计对比：{exc}")

        st.markdown("#### 生成清洗数据集")
        st.info("所有处理都会生成 cleaned_dataset.csv，不覆盖原始上传文件、合并数据集或分析数据集。")
        if operations:
            st.caption(f"待执行处理步骤：{len(operations)} 个")
            st.caption("详细处理内容已在上方清洗计划总览和预计处理影响中展示；点击按钮会生成独立的 cleaned_dataset.csv。")
        else:
            st.caption("当前没有待执行处理步骤，可以直接保留当前数据集。")

        if st.button(
            "生成清洗数据集",
            type="primary",
            key=f"project_quality_create_cleaned_v2_{project_id}",
        ):
            try:
                metadata = create_cleaned_dataset(project_id, operations)
                st.session_state.project_quality_message = (
                    f"已生成 cleaned_dataset.csv：{metadata['before_rows']:,} 行 -> {metadata['after_rows']:,} 行。"
                )
                st.rerun()
            except Exception as exc:
                st.error(f"清洗数据集生成失败：{exc}")

        message = st.session_state.pop("project_quality_message", None)
        if message:
            st.success(message)

        metadata = get_cleaned_dataset_metadata(project_id)
        if metadata:
            st.markdown("#### 清洗结果摘要")
            result_cards = st.columns(4)
            result_cards[0].metric("处理前行数", f"{metadata.get('before_rows', 0):,}")
            result_cards[1].metric("处理后行数", f"{metadata.get('after_rows', 0):,}")
            result_cards[2].metric("处理前列数", metadata.get("before_columns", 0))
            result_cards[3].metric("处理后列数", metadata.get("after_columns", 0))
            st.caption(f"生成时间：{metadata.get('created_at', '-')}")
            st.caption(f"保存位置：{metadata.get('file_path', '-')}")
            try:
                cleaned_df = load_cleaned_dataset(project_id)
                st.download_button(
                    "下载清洗数据集 CSV",
                    data=cleaned_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                    file_name="cleaned_dataset.csv",
                    mime="text/csv",
                    key=f"project_quality_download_cleaned_v2_{project_id}",
                )
                render_dataset_preview(
                    cleaned_df,
                    "cleaned_dataset.csv",
                    show_download=False,
                    key_prefix=f"quality_after_preview_{project_id}_cleaned_dataset",
                )
                if st.button(
                    "设为当前分析数据集",
                    type="primary",
                    key=f"project_quality_set_cleaned_current_v2_{project_id}",
                ):
                    set_cleaned_dataset_as_current(project_id)
                    clear_active_analysis()
                    st.session_state.project_quality_message = "已将 cleaned_dataset.csv 设为当前分析数据集。"
                    st.rerun()
            except Exception as exc:
                st.warning(f"清洗数据集暂不可用：{exc}")


def render_field_mapping_tab(project_id: str, dataframe: pd.DataFrame | None = None) -> None:
    render_module_intro(
        "sparkles",
        "Field understanding",
        "字段映射",
        "使用规则识别字段业务含义，并由用户确认后保存为当前项目配置。",
    )
    try:
        dataframe = load_current_analysis_dataframe(project_id)
    except Exception:
        st.info(NO_CURRENT_ANALYSIS_DATASET_MESSAGE)
        return
    try:
        existing_mappings = load_field_mappings(project_id)
    except ValueError as exc:
        st.error(str(exc))
        existing_mappings = []

    mappings = merge_existing_mappings(dataframe, existing_mappings)
    new_fields = get_new_fields(dataframe, existing_mappings)
    missing_fields = get_missing_historical_fields(dataframe, existing_mappings)

    if existing_mappings and not new_fields and not missing_fields:
        st.success("已加载项目字段映射，当前数据字段与历史映射一致。")
    elif existing_mappings:
        st.info("已加载已有字段映射，并对当前数据中的新字段进行自动识别。")
    else:
        st.info("当前项目尚未保存字段映射，以下结果由本地规则自动识别。")
    if new_fields:
        st.info(f"检测到新字段：{', '.join(new_fields)}。请确认自动识别结果。")
    if missing_fields:
        st.warning(f"部分历史字段在当前数据中不存在：{', '.join(missing_fields)}。")

    editor_rows = pd.DataFrame(
        [
            {
                "原始字段名": item["column_name"],
                "pandas类型": item["pandas_dtype"],
                "识别业务类型": item["inferred_type"],
                "置信度": round(float(item["confidence"]) * 100, 1),
                "推断依据": item["reason"],
                "用户确认类型": item["confirmed_type"],
            }
            for item in mappings
        ]
    )
    edited_rows = st.data_editor(
        editor_rows,
        use_container_width=True,
        hide_index=True,
        disabled=[
            "原始字段名",
            "pandas类型",
            "识别业务类型",
            "置信度",
            "推断依据",
        ],
        column_config={
            "用户确认类型": st.column_config.SelectboxColumn(
                "用户确认类型",
                options=list(FIELD_TYPES),
                required=True,
            ),
            "置信度": st.column_config.NumberColumn(
                "置信度",
                format="%.1f%%",
            ),
        },
        key=f"field_mapping_editor_{project_id}",
    )
    if st.button(
        "保存字段映射",
        type="primary",
        key=f"save_field_mappings_{project_id}",
    ):
        confirmed_mappings = []
        mapping_by_column = {
            item["column_name"]: item
            for item in mappings
        }
        for row in edited_rows.to_dict("records"):
            original = mapping_by_column[row["原始字段名"]]
            confirmed_mappings.append(
                {
                    **original,
                    "confirmed_type": row["用户确认类型"],
                }
            )
        current_columns = set(dataframe.columns)
        confirmed_mappings.extend(
            item
            for item in existing_mappings
            if item.get("column_name") not in current_columns
        )
        save_field_mappings(project_id, confirmed_mappings)
        st.session_state.field_mapping_message = "字段映射已保存到当前项目。"
        st.rerun()

    message = st.session_state.pop("field_mapping_message", None)
    if message:
        st.success(message)
    st.caption(
        "字段映射保存在 config/field_mappings.json，并同步写入 project.json。"
    )


@st.cache_data(show_spinner=False)
def cached_relationship_candidates(
    project_id: str,
    project_updated_at: str,
) -> list[dict]:
    return discover_project_relationships(project_id)


def merge_relationship_records(existing: list[dict], additions: list[dict]) -> list[dict]:
    merged = {
        (
            item["table_a_id"],
            item["field_a"],
            item["table_b_id"],
            item["field_b"],
        ): item
        for item in existing
    }
    for item in additions:
        merged[
            (
                item["table_a_id"],
                item["field_a"],
                item["table_b_id"],
                item["field_b"],
            )
        ] = item
    return list(merged.values())


def replace_relationship_record(
    existing: list[dict],
    relationship_id: str,
    replacement: dict,
) -> list[dict]:
    return [
        replacement if item.get("relationship_id") == relationship_id else item
        for item in existing
    ]


def relationship_used_in_analysis_dataset(
    project_id: str,
    relationship_ids: set[str],
) -> bool:
    try:
        metadata = get_dataset_metadata(project_id)
    except Exception:
        return False
    if not metadata:
        return False
    relationship_ids = {str(item) for item in relationship_ids if item}
    for section_name in ("join_plan", "applied_relationships"):
        for item in metadata.get(section_name, []) or []:
            if str(item.get("relationship_id", "")) in relationship_ids:
                return True
    return False


def render_table_relationship_tab(project_id: str) -> None:
    render_module_intro(
        "git-merge",
        "Table Relationship Engine",
        "表关系",
        "帮助 Agent 理解项目中多个数据表之间的业务关联。",
    )
    st.info(
        "表关系用于帮助 Agent 理解多个数据表之间的关联。保存关系不会修改原始数据，"
        "不会执行 JOIN，仅用于后续分析、业务问答和 KPI 计算。"
    )
    tables = list_project_tables(project_id)
    if len(tables) < 2:
        st.info("当前项目至少需要两个数据表，才能发现和确认表关系。")
        return

    st.subheader("项目数据表")
    st.dataframe(
        [
            {
                "数据表": table["table_name"],
                "文件名": table["file_name"],
                "Sheet": table["sheet_name"],
                "行数": table["rows"],
                "列数": table["columns"],
            }
            for table in tables
        ],
        use_container_width=True,
        hide_index=True,
    )

    try:
        saved_relationships = load_table_relationships(project_id)
    except ValueError as exc:
        st.error(str(exc))
        saved_relationships = []
    relationship_by_id = {
        item["relationship_id"]: item
        for item in saved_relationships
        if item.get("relationship_id")
    }
    editing_key = f"editing_relationship_id_{project_id}"
    pending_delete_key = f"pending_delete_relationship_id_{project_id}"
    pending_clear_key = f"pending_clear_relationships_{project_id}"
    editing_relationship_id = st.session_state.get(editing_key)
    editing_relationship = relationship_by_id.get(editing_relationship_id)
    if saved_relationships:
        st.success(f"已加载项目表关系，共 {len(saved_relationships)} 条。")
        st.markdown("#### 已保存关系")
        header_columns = st.columns([1.2, 1, 0.2, 1.2, 1, 0.9, 0.8, 1.4])
        for column, label in zip(
            header_columns,
            ["表A", "连接字段A", "↔", "表B", "连接字段B", "关系类型", "来源", "操作"],
        ):
            column.markdown(f"**{label}**")
        for index, item in enumerate(saved_relationships):
            with st.container(border=True):
                row_columns = st.columns([1.2, 1, 0.2, 1.2, 1, 0.9, 0.8, 1.4])
                row_columns[0].write(item["table_a_name"])
                row_columns[1].write(item["field_a"])
                row_columns[2].write("↔")
                row_columns[3].write(item["table_b_name"])
                row_columns[4].write(item["field_b"])
                row_columns[5].write(item["relationship_type"])
                row_columns[6].write("自动推荐" if item["source"] == "auto" else "手动")
                action_columns = row_columns[7].columns(2)
                if action_columns[0].button(
                    "编辑",
                    key=f"edit_relationship_{project_id}_{item['relationship_id']}",
                    use_container_width=True,
                ):
                    st.session_state[editing_key] = item["relationship_id"]
                    st.session_state.relationship_message = "已进入关系编辑模式，请在下方修改后保存。"
                    st.rerun()
                if action_columns[1].button(
                    "删除",
                    key=f"request_delete_relationship_{project_id}_{item['relationship_id']}",
                    use_container_width=True,
                ):
                    st.session_state[pending_delete_key] = item["relationship_id"]
                    st.rerun()

                if st.session_state.get(pending_delete_key) == item["relationship_id"]:
                    st.warning(
                        "确认删除该表关系？删除后不会影响原始数据，但后续分析数据集需要重新生成。"
                    )
                    confirm_columns = st.columns([1, 1, 4])
                    if confirm_columns[0].button(
                        "确认删除",
                        type="primary",
                        key=f"do_delete_relationship_{project_id}_{item['relationship_id']}",
                        use_container_width=True,
                    ):
                        was_used = relationship_used_in_analysis_dataset(
                            project_id,
                            {item["relationship_id"]},
                        )
                        delete_table_relationship(project_id, item["relationship_id"])
                        if st.session_state.get(editing_key) == item["relationship_id"]:
                            st.session_state.pop(editing_key, None)
                        st.session_state.pop(pending_delete_key, None)
                        st.session_state.relationship_message = (
                            "表关系已删除。表关系已变更，请重新生成分析数据集。"
                            if was_used
                            else "表关系已删除，请重新生成分析数据集。"
                        )
                        st.rerun()
                    if confirm_columns[1].button(
                        "取消",
                        key=f"cancel_delete_relationship_{project_id}_{item['relationship_id']}",
                        use_container_width=True,
                    ):
                        st.session_state.pop(pending_delete_key, None)
                        st.rerun()

        st.markdown("#### 批量操作")
        if st.button(
            "清空全部关系",
            key=f"request_clear_relationships_{project_id}",
        ):
            st.session_state[pending_clear_key] = True
            st.rerun()
        if st.session_state.get(pending_clear_key):
            st.warning(
                "确认清空全部表关系？删除后不会影响原始数据，但后续分析数据集需要重新生成。"
            )
            clear_columns = st.columns([1, 1, 4])
            if clear_columns[0].button(
                "确认清空",
                type="primary",
                key=f"do_clear_relationships_{project_id}",
            ):
                was_used = relationship_used_in_analysis_dataset(
                    project_id,
                    {item["relationship_id"] for item in saved_relationships},
                )
                clear_table_relationships(project_id)
                st.session_state.pop(editing_key, None)
                st.session_state.pop(pending_delete_key, None)
                st.session_state.pop(pending_clear_key, None)
                st.session_state.relationship_message = (
                    "全部表关系已清空。表关系已变更，请重新生成分析数据集。"
                    if was_used
                    else "全部表关系已清空，请重新生成分析数据集。"
                )
                st.rerun()
            if clear_columns[1].button(
                "取消",
                key=f"cancel_clear_relationships_{project_id}",
            ):
                st.session_state.pop(pending_clear_key, None)
                st.rerun()

    st.subheader("推荐关系")
    project = get_project(project_id)
    with st.spinner("正在根据字段名称、字段映射类型、数据类型和唯一值比例生成推荐..."):
        candidates = cached_relationship_candidates(
            project_id,
            project.get("updated_at", project.get("last_modified", "")),
        )
    if candidates:
        st.dataframe(
            [
                {
                    "推荐": "✓",
                    "表A": item["table_a_name"],
                    "连接字段A": item["field_a"],
                    "↔": "↔",
                    "表B": item["table_b_name"],
                    "连接字段B": item["field_b"],
                    "置信度": f"{item['confidence']:.0f}%",
                    "推荐依据": item["reason"],
                }
                for item in candidates
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("暂未发现评分达到 70 分的推荐关系，你仍可以手动配置。")

    candidate_options = ["manual"] + [item["relationship_id"] for item in candidates]
    candidate_by_id = {item["relationship_id"]: item for item in candidates}
    selected_candidate_id = st.selectbox(
        "选择推荐关系或手动配置",
        candidate_options,
        format_func=lambda value: (
            "手动配置"
            if value == "manual"
            else (
                f"{candidate_by_id[value]['table_a_name']}."
                f"{candidate_by_id[value]['field_a']} ↔ "
                f"{candidate_by_id[value]['table_b_name']}."
                f"{candidate_by_id[value]['field_b']} "
                f"({candidate_by_id[value]['confidence']:.0f}%)"
            )
        ),
        key=f"relationship_candidate_{project_id}",
    )
    selected_candidate = candidate_by_id.get(selected_candidate_id)
    recommendation_actions = st.columns(2)
    if recommendation_actions[0].button(
        "接受当前推荐",
        disabled=selected_candidate is None,
        type="primary",
        use_container_width=True,
        key=f"accept_current_relationship_{project_id}",
    ):
        save_table_relationships(
            project_id,
            merge_relationship_records(saved_relationships, [selected_candidate]),
        )
        st.session_state.relationship_message = "当前推荐关系已保存到项目。"
        st.rerun()
    if recommendation_actions[1].button(
        "一键接受全部推荐",
        disabled=not candidates,
        use_container_width=True,
        key=f"accept_all_relationships_{project_id}",
    ):
        save_table_relationships(
            project_id,
            merge_relationship_records(saved_relationships, candidates),
        )
        st.session_state.relationship_message = f"已保存 {len(candidates)} 条推荐关系。"
        st.rerun()

    st.subheader("手动配置")
    st.caption("手动配置默认仅展示 ID、日期和高唯一值字段；金额等业务指标不会作为关系推荐。")
    if editing_relationship:
        st.info(
            f"正在编辑：{editing_relationship['table_a_name']}.{editing_relationship['field_a']} ↔ "
            f"{editing_relationship['table_b_name']}.{editing_relationship['field_b']}"
        )
        if st.button(
            "取消编辑",
            key=f"cancel_edit_relationship_{project_id}",
        ):
            st.session_state.pop(editing_key, None)
            st.rerun()
    table_by_id = {table["table_id"]: table for table in tables}
    table_ids = list(table_by_id)
    active_relationship = selected_candidate or editing_relationship
    table_a_default = (
        active_relationship["table_a_id"]
        if active_relationship and active_relationship["table_a_id"] in table_ids
        else table_ids[0]
    )
    table_b_default = (
        active_relationship["table_b_id"]
        if active_relationship and active_relationship["table_b_id"] in table_ids
        else table_ids[1]
    )
    control_key = selected_candidate_id if selected_candidate else (editing_relationship_id or "manual")
    relationship_columns = st.columns([1, 1, 0.25, 1, 1])
    table_a_id = relationship_columns[0].selectbox(
        "表A",
        table_ids,
        index=table_ids.index(table_a_default),
        format_func=lambda value: (
            f"{table_by_id[value]['table_name']} · {table_by_id[value]['file_name']}"
        ),
        key=f"relationship_table_a_{project_id}_{control_key}",
    )
    fields_a = get_project_table_columns(project_id, table_a_id, connectable_only=True)
    field_a_default = (
        active_relationship["field_a"]
        if active_relationship
        and active_relationship["table_a_id"] == table_a_id
        and active_relationship["field_a"] in fields_a
        else fields_a[0]
    )
    field_a = relationship_columns[1].selectbox(
        "连接字段",
        fields_a,
        index=fields_a.index(field_a_default),
        key=f"relationship_field_a_{project_id}_{control_key}_{table_a_id}",
    )
    relationship_columns[2].markdown("<div style='text-align:center;padding-top:38px;font-size:28px'>↔</div>", unsafe_allow_html=True)
    table_b_id = relationship_columns[3].selectbox(
        "表B",
        table_ids,
        index=table_ids.index(table_b_default),
        format_func=lambda value: (
            f"{table_by_id[value]['table_name']} · {table_by_id[value]['file_name']}"
        ),
        key=f"relationship_table_b_{project_id}_{control_key}",
    )
    fields_b = get_project_table_columns(project_id, table_b_id, connectable_only=True)
    field_b_default = (
        active_relationship["field_b"]
        if active_relationship
        and active_relationship["table_b_id"] == table_b_id
        and active_relationship["field_b"] in fields_b
        else fields_b[0]
    )
    field_b = relationship_columns[4].selectbox(
        "连接字段",
        fields_b,
        index=fields_b.index(field_b_default),
        key=f"relationship_field_b_{project_id}_{control_key}_{table_b_id}",
    )
    relationship_type_labels = {
        "one_to_one": "One-to-One",
        "one_to_many": "One-to-Many",
        "many_to_one": "Many-to-One",
        "many_to_many": "Many-to-Many",
    }
    selected_relationship_type = st.selectbox(
        "关系类型",
        list(RELATIONSHIP_TYPES),
        index=list(RELATIONSHIP_TYPES).index(
            active_relationship.get("relationship_type", "many_to_one")
            if active_relationship
            else "many_to_one"
        ),
        format_func=lambda value: relationship_type_labels[value],
        key=f"relationship_type_{project_id}_{control_key}",
    )

    if st.button(
        "确认并保存关系",
        type="primary",
        key=f"save_table_relationship_{project_id}",
    ):
        if table_a_id == table_b_id:
            st.error("表A和表B不能是同一个数据表。")
        else:
            table_a = table_by_id[table_a_id]
            table_b = table_by_id[table_b_id]
            relationship = {
                "relationship_id": (
                    editing_relationship["relationship_id"]
                    if editing_relationship
                    else selected_candidate["relationship_id"]
                    if selected_candidate
                    else ""
                ),
                "table_a_id": table_a_id,
                "table_a_name": table_a["table_name"],
                "table_a_file_id": table_a["file_id"],
                "table_a_file_name": table_a["file_name"],
                "table_a_sheet_name": table_a["sheet_name"],
                "field_a": field_a,
                "table_b_id": table_b_id,
                "table_b_name": table_b["table_name"],
                "table_b_file_id": table_b["file_id"],
                "table_b_file_name": table_b["file_name"],
                "table_b_sheet_name": table_b["sheet_name"],
                "field_b": field_b,
                "relationship_type": selected_relationship_type,
                "confidence": (
                    selected_candidate["confidence"]
                    if selected_candidate
                    else editing_relationship.get("confidence", 0)
                    if editing_relationship
                    else 0
                ),
                "score_breakdown": (
                    selected_candidate.get("score_breakdown", {})
                    if selected_candidate
                    else editing_relationship.get("score_breakdown", {})
                    if editing_relationship
                    else {}
                ),
                "reason": (
                    selected_candidate["reason"]
                    if selected_candidate
                    else "用户手动编辑"
                    if editing_relationship
                    else "用户手动确认"
                ),
                "source": (
                    "auto"
                    if selected_candidate
                    else editing_relationship.get("source", "manual")
                    if editing_relationship
                    else "manual"
                ),
            }
            if editing_relationship:
                save_table_relationships(
                    project_id,
                    replace_relationship_record(
                        saved_relationships,
                        editing_relationship["relationship_id"],
                        relationship,
                    ),
                )
                st.session_state.pop(editing_key, None)
                stale_message = (
                    "表关系已变更，请重新生成分析数据集。"
                    if relationship_used_in_analysis_dataset(
                        project_id,
                        {editing_relationship["relationship_id"]},
                    )
                    else ""
                )
                st.session_state.relationship_message = (
                    f"表关系已更新。{stale_message}".strip()
                )
            else:
                save_table_relationships(
                    project_id,
                    merge_relationship_records(saved_relationships, [relationship]),
                )
                st.session_state.relationship_message = "表关系已保存到当前项目。"
            st.rerun()

    message = st.session_state.pop("relationship_message", None)
    if message:
        st.success(message)
    st.caption(
        "关系保存在 config/table_relationships.json，并同步写入 project.json。保存关系只记录元数据，不执行 JOIN。"
    )


def render_kpi_center_tab(
    project_id: str,
    dataframe: pd.DataFrame,
    show_intro: bool = True,
) -> None:
    if show_intro:
        render_module_intro(
            "target",
            "KPI Definition Engine",
            "指标计算规则",
            "定义项目中的核心业务指标计算方式，并保存为后续探索分析、业务分析、报告和问答的统一指标口径。",
        )
        st.info(
            "指标计算规则用于定义项目中的核心业务指标怎么算。后续探索分析、业务分析、周报、月报、Dashboard、AI问答都会优先使用这里定义的规则。"
        )

    try:
        existing_kpis = load_kpi_definitions(project_id)
        candidate_kpis = generate_project_kpi_candidates(project_id)
        current_kpis = merged_project_kpis(project_id)
    except ValueError as exc:
        st.error(str(exc))
        existing_kpis = []
        candidate_kpis = []
        current_kpis = []

    summary_columns = st.columns(4)
    summary_columns[0].metric("计算规则", len(current_kpis))
    summary_columns[1].metric("已启用", len([item for item in current_kpis if item.get("enabled")]))
    summary_columns[2].metric("自动候选", len(candidate_kpis))
    summary_columns[3].metric("已保存", len(existing_kpis))

    if not candidate_kpis and not current_kpis:
        st.warning("当前项目还没有可生成指标计算规则的字段映射。请先在“字段映射”中确认金额、ID、日期、区域、产品或人员字段。")

    st.subheader("指标计算规则")
    st.caption("这里管理指标“怎么算”：聚合方式、来源字段、字段类型、启用状态和创建方式。")
    source_field_options = ["项目级预留"] + [str(column) for column in dataframe.columns]
    kpi_rows = pd.DataFrame(
        [
            {
                "_kpi_id": item["kpi_id"],
                "_description": item["description"],
                "启用状态": bool(item["enabled"]),
                "指标名称": item["kpi_name"],
                "分类": item["category"],
                "聚合方式": item["aggregation"],
                "来源字段": item["source_field"] or "项目级预留",
                "字段类型": item["field_type"],
                "创建方式": "自动候选" if item.get("created_by") == "auto" else "用户定义",
            }
            for item in current_kpis
        ],
        columns=[
            "_kpi_id",
            "_description",
            "启用状态",
            "指标名称",
            "分类",
            "聚合方式",
            "来源字段",
            "字段类型",
            "创建方式",
        ],
    )
    edited_rows = st.data_editor(
        kpi_rows,
        use_container_width=True,
        hide_index=True,
        column_order=["指标名称", "分类", "聚合方式", "来源字段", "字段类型", "启用状态", "创建方式"],
        disabled=["创建方式"],
        column_config={
            "启用状态": st.column_config.CheckboxColumn("启用状态"),
            "分类": st.column_config.SelectboxColumn("分类", options=list(KPI_CATEGORIES)),
            "聚合方式": st.column_config.SelectboxColumn(
                "聚合方式",
                options=list(SUPPORTED_AGGREGATIONS) + [RESERVED_AGGREGATION],
            ),
            "来源字段": st.column_config.SelectboxColumn(
                "来源字段",
                options=source_field_options,
            ),
            "字段类型": st.column_config.SelectboxColumn(
                "字段类型",
                options=["amount", "id", "date", "region", "product", "person", "custom"],
            ),
        },
        key=f"kpi_definition_editor_{project_id}",
    )

    if st.button("保存指标计算规则", type="primary", key=f"save_kpis_{project_id}"):
        definitions = []
        for index, row in enumerate(edited_rows.to_dict("records")):
            original_item = current_kpis[index] if index < len(current_kpis) else {}
            definitions.append(
                {
                    "kpi_id": row.get("_kpi_id") or original_item.get("kpi_id"),
                    "kpi_name": row["指标名称"],
                    "category": row["分类"],
                    "aggregation": row["聚合方式"],
                    "source_field": "" if row["来源字段"] == "项目级预留" else row["来源字段"],
                    "field_type": row["字段类型"],
                    "description": row.get("_description", original_item.get("description", "")),
                    "enabled": row["启用状态"],
                    "created_by": "auto" if row["创建方式"] == "自动候选" else "user",
                }
            )
        save_kpi_definitions(project_id, definitions)
        st.session_state.kpi_center_message = "指标计算规则已保存到当前项目。"
        st.rerun()

    message = st.session_state.pop("kpi_center_message", None)
    if message:
        st.success(message)

    st.subheader("新增指标计算规则")
    st.caption("V1 支持 SUM、COUNT、AVG、MAX、MIN。客单价等复杂公式会在后续公式引擎中支持。")
    with st.form(f"add_kpi_form_{project_id}"):
        add_columns = st.columns(5)
        new_name = add_columns[0].text_input("指标名称", placeholder="例如：客单价")
        new_category = add_columns[1].selectbox("分类", list(KPI_CATEGORIES))
        new_aggregation = add_columns[2].selectbox("聚合方式", list(SUPPORTED_AGGREGATIONS))
        new_source_field = add_columns[3].selectbox("来源字段", [str(column) for column in dataframe.columns])
        new_field_type = add_columns[4].selectbox(
            "字段类型",
            ["amount", "id", "date", "region", "product", "person", "custom"],
        )
        new_description = st.text_input("描述", placeholder="说明这个 KPI 的业务含义")
        submitted = st.form_submit_button("新增指标计算规则", type="primary")
        if submitted:
            if not new_name.strip():
                st.error("指标名称不能为空。")
            else:
                add_kpi_definition(
                    project_id,
                    {
                        "kpi_name": new_name,
                        "category": new_category,
                        "aggregation": new_aggregation,
                        "source_field": new_source_field,
                        "field_type": new_field_type,
                        "description": new_description,
                        "enabled": True,
                        "created_by": "user",
                    },
                )
                st.session_state.kpi_center_message = "新指标计算规则已添加。"
                st.rerun()

    st.subheader("删除指标计算规则")
    saved_kpis = load_kpi_definitions(project_id)
    if saved_kpis:
        delete_options = {item["kpi_id"]: f"{item['kpi_name']} · {item['source_field'] or '项目级预留'}" for item in saved_kpis}
        delete_kpi_id = st.selectbox(
            "选择要删除的指标计算规则",
            list(delete_options),
            format_func=lambda value: delete_options[value],
            key=f"delete_kpi_select_{project_id}",
        )
        if st.button("删除所选指标计算规则", key=f"delete_kpi_{project_id}"):
            delete_kpi_definition(project_id, delete_kpi_id)
            st.session_state.kpi_center_message = "指标计算规则已删除。"
            st.rerun()
    else:
        st.info("当前还没有已保存的指标计算规则。保存候选或新增规则后，可在这里删除。")

    enabled_kpis = list_enabled_kpis(project_id)
    st.caption(
        f"指标计算规则保存在 config/kpi_definitions.json，并同步写入 project.json。当前启用 {len(enabled_kpis)} 条规则。"
    )


def render_metric_dictionary_tab(project_id: str, show_intro: bool = True) -> None:
    if show_intro:
        render_module_intro(
            "book-open",
            "Business Metric Dictionary",
            "指标语义字典",
            "把不同企业、不同表里的字段叫法统一成项目级业务指标，并关联到 KPI 定义。",
        )
        st.info(
            "指标语义字典用于管理业务指标名称、业务定义、常见别名和关联计算规则。后续探索分析、业务分析、Dashboard、AI问答会优先读取这里的统一口径。"
        )

    try:
        existing_metrics = load_metric_dictionary(project_id)
        candidate_metrics = generate_project_metric_candidates(project_id)
        current_metrics = merged_project_metrics(project_id)
        project_kpis = merged_project_kpis(project_id)
    except ValueError as exc:
        st.error(str(exc))
        existing_metrics = []
        candidate_metrics = []
        current_metrics = []
        project_kpis = []

    no_linked_rule_label = "不关联指标计算规则"
    kpi_options = [no_linked_rule_label] + _unique_values(
        [str(item.get("kpi_name", "")) for item in project_kpis if item.get("kpi_name")]
    )
    kpi_id_by_name = {
        str(item.get("kpi_name", "")): str(item.get("kpi_id", ""))
        for item in project_kpis
        if item.get("kpi_name")
    }

    summary_columns = st.columns(4)
    summary_columns[0].metric("指标定义", len(current_metrics))
    summary_columns[1].metric("已启用", len([item for item in current_metrics if item.get("enabled")]))
    summary_columns[2].metric("自动候选", len(candidate_metrics))
    summary_columns[3].metric("别名数量", sum(len(item.get("aliases", [])) for item in current_metrics))

    if not candidate_metrics and not current_metrics:
        st.warning("当前项目还没有可生成指标语义字典的计算规则。请先在“指标中心”的“指标计算规则”中保存或新增规则。")

    st.subheader("指标语义字典")
    st.caption("这里管理指标“叫什么”：业务定义、别名、指标类型，以及关联哪条指标计算规则。")
    metric_rows = pd.DataFrame(
        [
            {
                "_metric_id": item["metric_id"],
                "启用状态": bool(item["enabled"]),
                "指标名称": item["metric_name"],
                "指标类型": item["metric_type"],
                "业务定义": item["business_definition"],
                "别名": "，".join(item.get("aliases", [])),
                "关联指标计算规则": item.get("linked_kpi_name") or no_linked_rule_label,
                "创建方式": "自动候选" if item.get("created_by") == "auto" else "用户定义",
            }
            for item in current_metrics
        ],
        columns=[
            "_metric_id",
            "启用状态",
            "指标名称",
            "指标类型",
            "业务定义",
            "别名",
            "关联指标计算规则",
            "创建方式",
        ],
    )
    edited_rows = st.data_editor(
        metric_rows,
        use_container_width=True,
        hide_index=True,
        column_order=["指标名称", "指标类型", "业务定义", "别名", "关联指标计算规则", "启用状态", "创建方式"],
        disabled=["创建方式"],
        column_config={
            "启用状态": st.column_config.CheckboxColumn("启用状态"),
            "指标类型": st.column_config.SelectboxColumn("指标类型", options=list(METRIC_CATEGORIES)),
            "关联指标计算规则": st.column_config.SelectboxColumn("关联指标计算规则", options=kpi_options),
            "别名": st.column_config.TextColumn(
                "别名",
                help="多个别名可用逗号、顿号、分号或换行分隔，例如 GMV，Revenue，成交金额。",
            ),
        },
        key=f"metric_dictionary_editor_{project_id}",
    )

    if st.button("保存指标语义字典", type="primary", key=f"save_metric_dictionary_{project_id}"):
        metrics = []
        for index, row in enumerate(edited_rows.to_dict("records")):
            original_item = current_metrics[index] if index < len(current_metrics) else {}
            linked_kpi_name = "" if row["关联指标计算规则"] == no_linked_rule_label else row["关联指标计算规则"]
            metrics.append(
                {
                    "metric_id": row.get("_metric_id") or original_item.get("metric_id"),
                    "metric_name": row["指标名称"],
                    "metric_type": row["指标类型"],
                    "business_definition": row["业务定义"],
                    "aliases": row["别名"],
                    "linked_kpi_name": linked_kpi_name,
                    "linked_kpi_id": kpi_id_by_name.get(linked_kpi_name, ""),
                    "enabled": row["启用状态"],
                    "created_by": "auto" if row["创建方式"] == "自动候选" else "user",
                }
            )
        save_metric_dictionary(project_id, metrics)
        st.session_state.metric_dictionary_message = "指标语义字典已保存到当前项目。"
        st.rerun()

    message = st.session_state.pop("metric_dictionary_message", None)
    if message:
        st.success(message)

    st.subheader("新增指标")
    with st.form(f"add_metric_form_{project_id}"):
        add_columns = st.columns(4)
        new_metric_name = add_columns[0].text_input("指标名称", placeholder="例如：销售额")
        new_metric_type = add_columns[1].selectbox("指标类型", list(METRIC_CATEGORIES))
        new_linked_kpi = add_columns[2].selectbox("关联指标计算规则", kpi_options)
        new_enabled = add_columns[3].checkbox("启用", value=True)
        new_definition = st.text_input("业务定义", placeholder="说明这个指标的统一业务含义")
        new_aliases = st.text_area(
            "别名",
            placeholder="例如：GMV，Revenue，订单金额，成交金额",
            height=90,
        )
        submitted = st.form_submit_button("新增指标", type="primary")
        if submitted:
            if not new_metric_name.strip():
                st.error("指标名称不能为空。")
            else:
                linked_kpi_name = "" if new_linked_kpi == no_linked_rule_label else new_linked_kpi
                add_metric_definition(
                    project_id,
                    {
                        "metric_name": new_metric_name,
                        "metric_type": new_metric_type,
                        "business_definition": new_definition,
                        "aliases": new_aliases,
                        "linked_kpi_name": linked_kpi_name,
                        "linked_kpi_id": kpi_id_by_name.get(linked_kpi_name, ""),
                        "enabled": new_enabled,
                        "created_by": "user",
                    },
                )
                st.session_state.metric_dictionary_message = "新指标已添加。"
                st.rerun()

    st.subheader("删除指标")
    saved_metrics = load_metric_dictionary(project_id)
    if saved_metrics:
        delete_options = {
            item["metric_id"]: f"{item['metric_name']} · {item.get('metric_type', '核心指标')}"
            for item in saved_metrics
        }
        delete_metric_id = st.selectbox(
            "选择要删除的指标",
            list(delete_options),
            format_func=lambda value: delete_options[value],
            key=f"delete_metric_select_{project_id}",
        )
        if st.button("删除所选指标", key=f"delete_metric_{project_id}"):
            delete_metric_definition(project_id, delete_metric_id)
            st.session_state.metric_dictionary_message = "指标已删除。"
            st.rerun()
    else:
        st.info("当前还没有已保存的指标。保存候选或新增指标后，可在这里删除。")

    enabled_metrics = list_enabled_metrics(project_id)
    st.caption(
        f"指标语义字典保存在 config/metric_dictionary.json，并同步写入 project.json。当前启用 {len(enabled_metrics)} 个业务指标。"
    )


def render_metric_center_tab(project_id: str, dataframe: pd.DataFrame) -> None:
    render_module_intro(
        "target",
        "Metric Center",
        "指标中心",
        "指标中心用于管理项目中的业务指标，包括“怎么算”和“叫什么”。后续探索分析、业务分析、Dashboard和报告都会优先使用这里的指标定义。",
    )
    st.info(
        "指标中心用于管理项目中的业务指标，包括“怎么算”和“叫什么”。后续探索分析、业务分析、Dashboard和报告都会优先使用这里的指标定义。"
    )

    metric_tabs = st.tabs(["指标计算规则", "指标语义字典"])
    with metric_tabs[0]:
        render_kpi_center_tab(project_id, dataframe, show_intro=False)
    with metric_tabs[1]:
        render_metric_dictionary_tab(project_id, show_intro=False)


def render_analysis_dataset_tab(project_id: str) -> None:
    render_module_intro(
        "blocks",
        "Analysis Dataset Builder",
        "分析数据集",
        "根据数据源、字段映射、表关系和指标中心定义生成项目级分析数据集副本。",
    )
    st.info(
        "分析数据集会保存为项目副本，不覆盖原始文件。本轮只生成数据集、JOIN计划和健康检查，不切换探索分析或业务分析的数据来源。"
    )

    build_message = st.session_state.pop("analysis_dataset_message", None)
    if build_message:
        st.success(build_message)

    try:
        join_plan = generate_join_plan(project_id)
    except ValueError as exc:
        st.error(str(exc))
        join_plan = []

    metadata = get_dataset_metadata(project_id)
    summary_columns = st.columns(4)
    summary_columns[0].metric("已确认 JOIN", len(join_plan))
    summary_columns[1].metric("已生成数据集", "是" if metadata else "否")
    summary_columns[2].metric("数据集行数", f"{metadata.get('rows', 0):,}" if metadata else "-")
    summary_columns[3].metric("数据集列数", metadata.get("columns", "-") if metadata else "-")

    st.subheader("JOIN计划")
    if join_plan:
        plan_df = pd.DataFrame(join_plan)
        visible_columns = [
            "表A",
            "字段A",
            "JOIN",
            "表B",
            "字段B",
            "关系类型",
            "预计匹配率",
            "预计扩张倍数",
            "风险",
            "风险说明",
        ]
        st.dataframe(plan_df[visible_columns], use_container_width=True, hide_index=True)
        high_risk_count = int((plan_df["风险"] == "高").sum())
        medium_risk_count = int((plan_df["风险"] == "中").sum())
        if high_risk_count:
            st.warning(f"检测到 {high_risk_count} 个高风险 JOIN，请确认后再生成分析数据集。")
        elif medium_risk_count:
            st.info(f"检测到 {medium_risk_count} 个中风险 JOIN，建议检查匹配率和扩张倍数。")
        else:
            st.success("JOIN计划风险较低，可以生成分析数据集。")
    else:
        st.warning("当前项目还没有可用的表关系。请先在“表关系”中保存关系，再生成分析数据集。")

    if st.button(
        "生成分析数据集",
        type="primary",
        disabled=not bool(join_plan),
        key=f"build_analysis_dataset_{project_id}",
    ):
        try:
            with st.spinner("正在生成分析数据集..."):
                result = build_analysis_dataset(project_id)
            st.session_state.analysis_dataset_message = (
                f"分析数据集已生成：{result['rows']:,} 行，{result['columns']} 列。"
            )
            st.rerun()
        except Exception as exc:
            st.error(f"分析数据集生成失败：{exc}")

    st.subheader("数据集预览")
    metadata = get_dataset_metadata(project_id)
    if not metadata:
        st.info("当前项目尚未生成分析数据集。")
        return

    preview_columns = st.columns(5)
    preview_columns[0].metric("行数", f"{metadata.get('rows', 0):,}")
    preview_columns[1].metric("列数", metadata.get("columns", 0))
    preview_columns[2].metric("来源表", len(metadata.get("source_tables", [])))
    preview_columns[3].metric("JOIN数量", metadata.get("join_count", 0))
    preview_columns[4].metric("数据大小", _format_file_size(int(metadata.get("file_size", 0))))
    st.caption(f"保存位置：workspace/projects/{project_id}/analysis/{metadata.get('file_name', 'analysis_dataset.csv')}")

    source_tables = metadata.get("source_tables", [])
    if source_tables:
        st.markdown("**来源表**")
        st.dataframe(
            pd.DataFrame(source_tables)[["table_name", "file_name", "sheet_name", "rows", "columns"]],
            use_container_width=True,
            hide_index=True,
        )

    health_checks = metadata.get("health_checks", [])
    if health_checks:
        st.markdown("**健康检查**")
        st.dataframe(pd.DataFrame(health_checks), use_container_width=True, hide_index=True)

    try:
        preview = preview_analysis_dataset(project_id)
        st.markdown("**字段列表**")
        st.dataframe(pd.DataFrame(preview["fields"]), use_container_width=True, hide_index=True)
        st.markdown("**前20行预览**")
        st.dataframe(preview["preview"], use_container_width=True)
    except Exception as exc:
        st.error(f"分析数据集预览失败：{exc}")


def render_business_question_tab(project_id: str) -> None:
    render_module_intro(
        "messages-square",
        "Business Question Engine",
        "业务问题",
        "将自然语言业务问题解析为结构化分析意图，为后续业务问答、AI分析和自动报表做准备。",
    )
    st.info(
        "业务问题引擎用于将自然语言问题解析为结构化分析意图。本阶段不会调用 AI，不会执行 SQL，不会生成最终答案。"
    )

    st.subheader("问题解析")
    example_text = (
        "例如：最近哪个区域销售额最高？\n"
        "例如：成交金额最高的5个产品是什么？\n"
        "例如：华东区订单数环比增长多少？\n"
        "例如：哪个销售员成交客户数最多？"
    )
    question = st.text_area(
        "请输入业务问题",
        placeholder=example_text,
        height=120,
        key=f"business_question_input_{project_id}",
    )
    if st.button("解析问题", type="primary", key=f"parse_business_question_{project_id}"):
        if not question.strip():
            st.error("请输入业务问题。")
        else:
            try:
                st.session_state.business_question_result = parse_question_for_project(
                    project_id,
                    question,
                )
                st.session_state.business_question_message = "业务问题已解析，并保存到项目历史。"
                st.rerun()
            except Exception as exc:
                st.error(f"业务问题解析失败：{exc}")

    message = st.session_state.pop("business_question_message", None)
    if message:
        st.success(message)

    result = st.session_state.get("business_question_result")
    if result:
        st.subheader("结构化解析结果")
        result_columns = st.columns(4)
        result_columns[0].metric("识别意图", result.get("intent_type", "unknown"))
        result_columns[1].metric("识别指标", result.get("metric") or "未识别")
        result_columns[2].metric("识别维度", result.get("dimension") or "未识别")
        result_columns[3].metric("置信度", f"{result.get('confidence', 0):.0%}")

        detail_rows = [
            {"项目": "原始问题", "结果": result.get("original_question", "")},
            {"项目": "命中的指标别名", "结果": result.get("metric_alias_matched", "") or "-"},
            {"项目": "时间范围", "结果": result.get("time_range", "") or "-"},
            {"项目": "同比/环比", "结果": result.get("comparison", "") or "-"},
            {"项目": "排序方式", "结果": result.get("sort", "") or "-"},
            {"项目": "Top N", "结果": result.get("top_n") if result.get("top_n") is not None else "-"},
            {"项目": "聚合方式", "结果": result.get("aggregation", "") or "-"},
        ]
        st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)

        filters = result.get("filters", [])
        st.markdown("**过滤条件**")
        if filters:
            st.dataframe(pd.DataFrame(filters), use_container_width=True, hide_index=True)
        else:
            st.caption("未识别到过滤条件。")

        warnings = result.get("warnings", [])
        if warnings:
            for warning in warnings:
                st.warning(warning)
        else:
            st.success("未发现解析警告。")

        st.markdown("**JSON 结构化结果**")
        st.json(result)

        st.subheader("Analysis Result")
        if st.button("执行分析", type="primary", key=f"execute_analysis_{project_id}"):
            try:
                st.session_state.business_analysis_execution_result = execute_analysis(
                    project_id,
                    result,
                )
                st.session_state.business_analysis_execution_message = "分析已执行，结果已保存。"
                st.rerun()
            except Exception as exc:
                st.error(f"分析执行失败：{exc}")

        execution_message = st.session_state.pop("business_analysis_execution_message", None)
        if execution_message:
            st.success(execution_message)
        execution_result = st.session_state.get("business_analysis_execution_result")
        if execution_result:
            result_summary = execution_result.get("summary", {})
            summary_columns = st.columns(4)
            summary_columns[0].metric("执行状态", "成功" if execution_result.get("success") else "失败")
            summary_columns[1].metric("过滤后行数", result_summary.get("filtered_rows", "-"))
            summary_columns[2].metric("结果行数", result_summary.get("result_rows", "-"))
            summary_columns[3].metric("聚合方式", result_summary.get("aggregation", "-"))
            summary_rows = [
                {"项目": "问题", "结果": result.get("original_question", "")},
                {"项目": "指标", "结果": result_summary.get("metric", result.get("metric", ""))},
                {"项目": "指标字段", "结果": result_summary.get("metric_field", "-") or "-"},
                {"项目": "维度", "结果": result_summary.get("dimension", result.get("dimension", "")) or "-"},
                {"项目": "维度字段", "结果": result_summary.get("dimension_field", "-") or "-"},
                {"项目": "时间范围", "结果": result_summary.get("time_range", result.get("time_range", "")) or "-"},
            ]
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
            rows = execution_result.get("rows", [])
            st.markdown("**结果表格**")
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info("当前分析没有返回结果行。")
            for warning in execution_result.get("warnings", []):
                st.warning(warning)

    st.subheader("解析历史")
    try:
        history = load_question_parse_history(project_id)
    except ValueError as exc:
        st.error(str(exc))
        history = []
    if history:
        history_rows = [
            {
                "问题": item.get("original_question", ""),
                "意图": item.get("parsed_intent", {}).get("intent_type", ""),
                "指标": item.get("parsed_intent", {}).get("metric", ""),
                "维度": item.get("parsed_intent", {}).get("dimension", ""),
                "置信度": item.get("parsed_intent", {}).get("confidence", 0),
                "解析时间": item.get("created_at", ""),
            }
            for item in history[:20]
        ]
        st.dataframe(pd.DataFrame(history_rows), use_container_width=True, hide_index=True)
    else:
        st.info("当前项目还没有业务问题解析历史。")


def render_rule_based_eda_report(project_id: str) -> None:
    st.subheader("自动探索报告")
    st.caption("基于 Analysis Dataset 自动执行字段级探索性分析，包含数值、类别、相关性、异常值、规则洞察和风险提示。")
    try:
        report = generate_eda_report(project_id)
    except Exception as exc:
        st.error(f"自动探索报告生成失败：{exc}")
        return

    overview = report.get("overview", {})
    warnings = report.get("warnings", [])
    if not overview:
        st.info("请先在「分析数据集」Tab 生成 Analysis Dataset，然后再查看自动探索报告。")
        for warning in warnings:
            st.warning(warning.get("message", warning) if isinstance(warning, dict) else warning)
        return

    overview_columns = st.columns(5)
    overview_columns[0].metric("数据行数", f"{overview.get('row_count', 0):,}")
    overview_columns[1].metric("字段数", overview.get("column_count", 0))
    overview_columns[2].metric("数值字段", overview.get("numeric_column_count", 0))
    overview_columns[3].metric("类别字段", overview.get("categorical_column_count", 0))
    overview_columns[4].metric("日期字段", overview.get("date_column_count", 0))

    st.markdown("#### 数值字段分析")
    numeric_analysis = report.get("numeric_analysis", [])
    if numeric_analysis:
        st.dataframe(pd.DataFrame(numeric_analysis), use_container_width=True, hide_index=True)
    else:
        st.info("当前 Analysis Dataset 未检测到数值字段。")

    st.markdown("#### 类别字段分析")
    categorical_analysis = report.get("categorical_analysis", [])
    if categorical_analysis:
        categorical_rows = []
        for item in categorical_analysis:
            top_values = item.get("top5_values", [])
            top1 = top_values[0] if top_values else {}
            categorical_rows.append(
                {
                    "column": item.get("column", ""),
                    "unique_count": item.get("unique_count", 0),
                    "top1": top1.get("value", ""),
                    "top1_ratio": top1.get("ratio", 0),
                    "top5_ratio": item.get("top5_ratio", 0),
                    "missing_rate": item.get("missing_rate", 0),
                }
            )
        st.dataframe(pd.DataFrame(categorical_rows), use_container_width=True, hide_index=True)
        with st.expander("查看类别字段 Top5 明细"):
            for item in categorical_analysis:
                st.markdown(f"**{item.get('column', '')}**")
                st.dataframe(pd.DataFrame(item.get("top5_values", [])), use_container_width=True, hide_index=True)
    else:
        st.info("当前 Analysis Dataset 未检测到类别字段。")

    st.markdown("#### 相关性分析")
    correlation_analysis = report.get("correlation_analysis", [])
    if correlation_analysis:
        st.dataframe(pd.DataFrame(correlation_analysis), use_container_width=True, hide_index=True)
    else:
        st.info("未发现绝对值大于 0.7 的 Pearson 相关字段对。")

    st.markdown("#### IQR 异常值分析")
    outlier_analysis = report.get("outlier_analysis", [])
    if outlier_analysis:
        st.dataframe(pd.DataFrame(outlier_analysis), use_container_width=True, hide_index=True)
    else:
        st.info("当前 Analysis Dataset 未检测到可用于异常值分析的数值字段。")

    st.markdown("#### 自动洞察")
    insights = report.get("insights", [])
    if insights:
        for insight in insights[:12]:
            st.write(f"- {insight.get('message', insight)}" if isinstance(insight, dict) else f"- {insight}")
    else:
        st.info("当前数据暂未生成规则型洞察。")

    st.markdown("#### 风险警告")
    if warnings:
        for warning in warnings:
            message = warning.get("message", warning) if isinstance(warning, dict) else warning
            severity = warning.get("severity", "") if isinstance(warning, dict) else ""
            if severity == "high":
                st.error(message)
            elif severity == "low":
                st.info(message)
            else:
                st.warning(message)
    else:
        st.success("未检测到高缺失率、高集中度、高异常率或强相关字段。")
    return

    st.markdown("#### 核心指标")
    kpis = report.get("kpis", [])
    if kpis:
        st.dataframe(pd.DataFrame(kpis), use_container_width=True, hide_index=True)
    else:
        st.info("当前项目还没有可计算的启用 KPI。")

    st.markdown("#### 趋势分析")
    trends = report.get("trends", [])
    if trends:
        st.dataframe(pd.DataFrame(trends), use_container_width=True, hide_index=True)
    else:
        st.info("未生成趋势分析，通常是因为缺少日期字段或可用 KPI。")

    st.markdown("#### 维度分析")
    dimensions = report.get("dimensions", [])
    if dimensions:
        dimension_rows = []
        for item in dimensions:
            top5 = item.get("top5", [])
            top1 = top5[0] if top5 else {}
            dimension_rows.append(
                {
                    "维度类型": item.get("dimension_type", ""),
                    "维度字段": item.get("dimension_field", ""),
                    "指标": item.get("metric_name", ""),
                    "Top1": next(
                        (
                            value
                            for key, value in top1.items()
                            if key not in {"value", "share"}
                        ),
                        "",
                    ),
                    "Top1占比": f"{item.get('top1_share', 0):.2f}%",
                    "最大/最小倍数": item.get("max_min_ratio", ""),
                }
            )
        st.dataframe(pd.DataFrame(dimension_rows), use_container_width=True, hide_index=True)
        with st.expander("查看各维度 Top5 明细"):
            for item in dimensions:
                st.markdown(f"**{item.get('dimension_field', '')} · {item.get('metric_name', '')}**")
                st.dataframe(pd.DataFrame(item.get("top5", [])), use_container_width=True, hide_index=True)
    else:
        st.info("未检测到区域、产品、人员或客户等可用于 Top5 的维度字段。")

    st.markdown("#### 自动洞察")
    insights = report.get("insights", [])
    if insights:
        for insight in insights[:12]:
            st.write(f"- {insight.get('message', insight)}" if isinstance(insight, dict) else f"- {insight}")
    else:
        st.info("当前数据暂未生成规则型洞察。")

    st.markdown("#### 风险警告")
    if warnings:
        for warning in warnings:
            message = warning.get("message", warning) if isinstance(warning, dict) else warning
            severity = warning.get("severity", "") if isinstance(warning, dict) else ""
            if severity == "high":
                st.error(message)
            elif severity == "low":
                st.info(message)
            else:
                st.warning(message)
    else:
        st.success("未检测到集中度、差异、下降或高缺失率风险。")


def render_dashboard_tab(project_id: str) -> None:
    render_module_intro(
        "layout-dashboard",
        "Dashboard Engine",
        "Dashboard",
        "将 EDA 与分析结果整理成可视化卡片、趋势图、TopN 图和风险提示。本阶段不接入 AI，也不导出 PPT/Word。",
    )
    try:
        dashboard = generate_project_dashboard(project_id)
    except Exception as exc:
        st.error(f"Dashboard 生成失败：{exc}")
        return

    overview_cards = dashboard.get("overview_cards", [])
    if overview_cards:
        card_columns = st.columns(len(overview_cards))
        for index, card in enumerate(overview_cards):
            card_columns[index].metric(card.get("title", ""), card.get("value", ""))
            if card.get("description"):
                card_columns[index].caption(card["description"])
    else:
        st.info("请先生成探索性分析报告 eda_report.json。")

    st.markdown("#### 趋势图")
    trend_charts = dashboard.get("trend_charts", [])
    if trend_charts:
        for chart in trend_charts:
            st.markdown(f"**{chart.get('title', '趋势图')}**")
            chart_df = pd.DataFrame(
                {
                    "x": chart.get("x", []),
                    "y": chart.get("y", []),
                }
            )
            if chart_df.empty:
                st.info("当前趋势图暂无数据。")
            else:
                st.line_chart(chart_df.set_index("x"))
    else:
        st.info("当前 eda_report.json 中没有可展示的趋势分析。")

    st.markdown("#### TopN 图")
    topn_charts = dashboard.get("topn_charts", [])
    if topn_charts:
        chart_columns = st.columns(2)
        for index, chart in enumerate(topn_charts):
            with chart_columns[index % 2]:
                st.markdown(f"**{chart.get('title', 'TopN')}**")
                chart_df = pd.DataFrame(
                    {
                        "label": chart.get("labels", []),
                        "value": chart.get("values", []),
                    }
                )
                if chart_df.empty:
                    st.info("当前 TopN 图暂无数据。")
                else:
                    st.bar_chart(chart_df.set_index("label"))
    else:
        st.info("当前 eda_report.json 中没有可展示的 TopN 分析。")

    st.markdown("#### 风险提示")
    risk_cards = dashboard.get("risk_cards", [])
    if risk_cards:
        for risk in risk_cards:
            message = risk.get("message", "")
            risk_level = risk.get("risk_level", "medium")
            if risk_level == "high":
                st.error(message)
            elif risk_level == "low":
                st.info(message)
            else:
                st.warning(message)
    else:
        st.success("当前没有需要展示的风险提示。")


def render_rule_based_business_analysis(project_id: str) -> None:
    st.subheader("Business Analysis Engine")
    st.caption("基于最近一次 Analysis Engine 结果和 EDA warnings 生成规则型商业解读，不调用 AI。")
    analysis_result = (
        st.session_state.get("business_analysis_execution_result")
        or _load_latest_analysis_result(project_id)
    )
    if not analysis_result:
        st.info("请先在「业务问题」Tab 解析并执行一个业务问题，生成 analysis_result.json。")
        return
    try:
        business_analysis = generate_rule_business_analysis(project_id, analysis_result)
    except Exception as exc:
        st.error(f"商业解读生成失败：{exc}")
        return

    st.markdown("#### Summary")
    st.info(business_analysis.get("summary", "暂无总结。"))

    columns = st.columns(3)
    with columns[0]:
        st.markdown("#### Findings")
        findings = business_analysis.get("findings", [])
        if findings:
            for item in findings:
                st.write(f"- {item}")
        else:
            st.caption("暂无明确发现。")
    with columns[1]:
        st.markdown("#### Risks")
        risks = business_analysis.get("risks", [])
        if risks:
            for item in risks:
                st.warning(item)
        else:
            st.success("暂无明显风险。")
    with columns[2]:
        st.markdown("#### Recommendations")
        recommendations = business_analysis.get("recommendations", [])
        if recommendations:
            for item in recommendations:
                st.write(f"- {item}")
        else:
            st.caption("暂无推荐动作。")

    comparisons = business_analysis.get("comparisons", [])
    if comparisons:
        st.markdown("#### Comparisons")
        for item in comparisons:
            st.write(f"- {item}")


def _load_latest_analysis_result(project_id: str) -> dict:
    analysis_path = get_project_path(project_id) / "analysis" / "analysis_result.json"
    if not analysis_path.is_file():
        return {}
    try:
        payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        return payload.get("analysis_result", payload)
    return {}


def _unique_values(values: list[str]) -> list[str]:
    unique = []
    seen = set()
    for value in values:
        clean_value = str(value).strip()
        if clean_value and clean_value not in seen:
            unique.append(clean_value)
            seen.add(clean_value)
    return unique


def _format_file_size(file_size: int) -> str:
    if file_size < 1024:
        return f"{file_size} B"
    if file_size < 1024**2:
        return f"{file_size / 1024:.1f} KB"
    return f"{file_size / 1024**2:.2f} MB"


def render_project_setup_navigation(project_id: str) -> None:
    def render_requires_dataset_notice() -> None:
        st.info(NO_CURRENT_ANALYSIS_DATASET_MESSAGE)

    setup_groups = st.tabs(["项目数据", "数据建模", "指标配置", "分析工作台", "交付导出"])
    with setup_groups[0]:
        project_data_tabs = st.tabs(["数据源", "数据合并", "数据质量"])
        with project_data_tabs[0]:
            render_data_source_tab(project_id)
        with project_data_tabs[1]:
            render_append_tables_tab(project_id)
        with project_data_tabs[2]:
            render_requires_dataset_notice()
    with setup_groups[1]:
        modeling_tabs = st.tabs(["字段映射", "表关系", "分析数据集"])
        with modeling_tabs[0]:
            render_requires_dataset_notice()
        with modeling_tabs[1]:
            render_requires_dataset_notice()
        with modeling_tabs[2]:
            render_requires_dataset_notice()
    with setup_groups[2]:
        metric_tabs = st.tabs(["指标中心"])
        with metric_tabs[0]:
            render_requires_dataset_notice()
    with setup_groups[3]:
        analysis_tabs = st.tabs(["业务问题", "探索性分析", "Dashboard", "业务分析"])
        with analysis_tabs[0]:
            render_requires_dataset_notice()
        with analysis_tabs[1]:
            render_requires_dataset_notice()
        with analysis_tabs[2]:
            render_requires_dataset_notice()
        with analysis_tabs[3]:
            render_requires_dataset_notice()
    with setup_groups[4]:
        delivery_tabs = st.tabs(["报告导出"])
        with delivery_tabs[0]:
            render_requires_dataset_notice()


@st.cache_data(show_spinner=False)
def build_generated_dashboard_export(
    current_df: pd.DataFrame,
    field_config: dict,
) -> bytes:
    return create_excel_dashboard(
        current_df,
        output_path=None,
        field_config=field_config,
    )


@st.cache_data(show_spinner=False)
def build_word_template_export(current_df, template_source, context) -> bytes:
    return export_word_from_template(
        current_df,
        template_file=template_source,
        output_path=None,
        context=context,
    )


@st.cache_data(show_spinner=False)
def build_ppt_template_export(current_df, template_source, context) -> bytes:
    return export_ppt_from_template(
        current_df,
        template_file=template_source,
        output_path=None,
        context=context,
    )


active_project_id = st.session_state.get("active_project_id")
if not active_project_id:
    render_project_center()
    st.stop()

try:
    active_project = get_project(active_project_id)
except Exception:
    st.session_state.pop("active_project_id", None)
    clear_active_analysis()
    st.warning("当前项目不存在或无法读取，请重新选择项目。")
    render_project_center()
    st.stop()


with st.sidebar:
    st.header("当前项目")
    st.markdown(f"**{active_project['project_name']}**")
    st.caption(f"项目 ID：{active_project['project_id']}")
    st.caption(f"位置：{get_project_path(active_project_id)}")
    if st.button("返回 Project Center", use_container_width=True):
        st.session_state.pop("active_project_id", None)
        clear_active_analysis()
        st.rerun()

    st.divider()
    st.header("1. 数据源概览")
    project_data_files = list_project_data_files(active_project_id)
    current_analysis_dataset = get_current_analysis_dataset(active_project_id)
    st.metric("项目数据文件", len(project_data_files))
    if current_analysis_dataset:
        dataset_name = current_analysis_dataset.get("dataset_name", "-")
        sheet_name = current_analysis_dataset.get("sheet_name")
        if current_analysis_dataset.get("dataset_type") == "appended":
            st.caption(f"当前分析数据：合并数据集 {dataset_name}")
        else:
            st.caption(
                "当前分析数据："
                f"{dataset_name}"
                f"{f' / {sheet_name}' if sheet_name else ''}"
            )
    else:
        st.info(NO_CURRENT_ANALYSIS_DATASET_MESSAGE)

    st.divider()
    st.header("2. AI 接入")
    st.caption("API Key 仅保存在当前浏览器会话中，不会写入文件。")
    ai_preset_name = st.selectbox(
        "选择模型",
        [*AI_MODEL_PRESETS.keys(), "自定义"],
        index=2,
        key="ai_model_preset",
    )
    api_key = st.text_input("API Key", type="password", placeholder="sk-...")
    if ai_preset_name == "自定义":
        ai_model = st.text_input("自定义模型名称", placeholder="例如：your-model-name")
        ai_base_url = st.text_input("自定义 API 地址", placeholder="https://example.com/v1")
    else:
        ai_preset = AI_MODEL_PRESETS[ai_preset_name]
        ai_model = ai_preset["model"]
        ai_base_url = ai_preset["base_url"]
        st.caption(f"模型名称：{ai_model}")
        st.caption(f"API 地址：{ai_base_url}")
    ai_config_signature = hash((api_key, ai_model, ai_base_url))
    ai_config_complete = bool(api_key.strip() and ai_model.strip() and ai_base_url.strip())
    if ai_preset_name == "自定义" and (not ai_model.strip() or not ai_base_url.strip()):
        st.info("选择自定义模型时，请补全模型名称和 API 地址。")
    if not api_key:
        st.caption("请输入 API Key 后测试连接。")
    if st.button("测试 AI 连接", disabled=not ai_config_complete, use_container_width=True):
        try:
            with st.spinner("正在测试 AI 接口..."):
                test_ai_connection(api_key, ai_model, ai_base_url)
            st.session_state.ai_connection_status = {
                "signature": ai_config_signature,
                "success": True,
                "message": "接入成功，AI功能可用。",
            }
        except Exception as exc:
            st.session_state.ai_connection_status = {
                "signature": ai_config_signature,
                "success": False,
                "message": f"接入失败：{exc}",
            }
    connection_status = st.session_state.get("ai_connection_status")
    if connection_status and connection_status["signature"] == ai_config_signature:
        if connection_status["success"]:
            st.success(connection_status["message"])
        else:
            st.error(connection_status["message"])
    elif connection_status:
        st.info("AI 配置已更改，请重新测试连接。")

active_project = get_project(active_project_id)
current_analysis_dataset = get_current_analysis_dataset(active_project_id)
render_project_status_bar(active_project, current_analysis_dataset, len(project_data_files))
if not current_analysis_dataset:
    render_project_setup_navigation(active_project_id)
    st.stop()

try:
    selected_dataframe = load_current_analysis_dataframe(active_project_id)
    analysis_key = (
        f"{active_project_id}-"
        f"{current_analysis_dataset.get('dataset_id', '')}-"
        f"{current_analysis_dataset.get('sheet_name') or ''}-"
        f"{current_analysis_dataset.get('created_at', '')}"
    )
    reset_for_dataframe(
        selected_dataframe,
        current_analysis_dataset.get("dataset_name", "current_dataset"),
        analysis_key,
    )
    st.session_state.original_df = selected_dataframe.copy()
    st.session_state.current_df = selected_dataframe.copy()
    st.session_state.working_df = selected_dataframe.copy()
except Exception as exc:
    clear_active_analysis()
    st.error(f"当前分析数据读取失败：{exc}")
    st.info(NO_CURRENT_ANALYSIS_DATASET_MESSAGE)
    render_project_setup_navigation(active_project_id)
    st.stop()

df = st.session_state.current_df
df, field_types = detect_and_parse_types(df)
st.session_state.current_df = df
st.session_state.working_df = df
st.session_state.field_types = field_types
numeric_columns = field_types["numeric"]
category_columns = field_types["categorical"]
date_columns = field_types["datetime"]
invalid_columns = suspicious_columns(df)
try:
    saved_field_mappings = load_field_mappings(active_project_id)
except ValueError as exc:
    st.warning(f"{exc} 当前分析暂时使用自动字段识别。")
    saved_field_mappings = []
confirmed_identifier_columns = confirmed_columns_by_type(
    saved_field_mappings,
    "ID字段",
)
confirmed_date_columns = confirmed_columns_by_type(
    saved_field_mappings,
    "日期字段",
)
confirmed_type_by_column = {
    item["column_name"]: item.get("confirmed_type")
    for item in saved_field_mappings
    if item.get("column_name") in df.columns
}
automatically_detected_identifiers = detect_identifier_columns(
    df,
    invalid_columns,
)
identifier_columns = list(
    dict.fromkeys(
        [
            column
            for column in automatically_detected_identifiers
            if column not in confirmed_type_by_column
            or confirmed_type_by_column[column] == "ID字段"
        ]
        + [
            column
            for column in confirmed_identifier_columns
            if column in df.columns and column not in invalid_columns
        ]
    )
)
date_columns = list(
    dict.fromkeys(
        [
            column
            for column in date_columns
            if column not in confirmed_type_by_column
            or confirmed_type_by_column[column] == "日期字段"
        ]
        + [
            column
            for column in confirmed_date_columns
            if column in df.columns and column not in invalid_columns
        ]
    )
)
eda_numeric_columns = [
    column
    for column in get_analysis_numeric_columns(df, identifier_columns)
    if column not in invalid_columns and column not in date_columns
]
eda_category_columns = [
    column
    for column in get_analysis_categorical_columns(df, identifier_columns)
    if column not in invalid_columns
]
eda_outliers = summarize_outliers(df, eda_numeric_columns, identifier_columns)
quality_summary = data_quality_summary(df, invalid_columns, identifier_columns, eda_numeric_columns)

info = basic_info(df)
metric_columns = st.columns(4)
metric_columns[0].metric("行数", f"{info['rows']:,}")
metric_columns[1].metric("列数", info["columns"])
metric_columns[2].metric("重复行", info["duplicate_rows"])
metric_columns[3].metric("内存占用", f"{info['memory_mb']} MB")

workflow_tabs = st.tabs(["项目数据", "数据建模", "指标配置", "分析工作台", "交付导出"])

with workflow_tabs[0]:
    project_data_tabs = st.tabs(["数据源", "数据合并", "数据质量"])

with workflow_tabs[1]:
    modeling_tabs = st.tabs(["字段映射", "表关系", "分析数据集"])

with workflow_tabs[2]:
    metric_config_tabs = st.tabs(["指标中心"])

with workflow_tabs[3]:
    workbench_tabs = st.tabs(["业务问题", "探索性分析", "Dashboard", "业务分析"])

with workflow_tabs[4]:
    delivery_tabs = st.tabs(["报告导出"])

with project_data_tabs[0]:
    render_data_source_tab(active_project_id)

with project_data_tabs[1]:
    render_append_tables_tab(active_project_id)

with project_data_tabs[2]:
    render_project_data_quality_tab(active_project_id)

with modeling_tabs[0]:
    render_field_mapping_tab(active_project_id, df)

with modeling_tabs[1]:
    render_table_relationship_tab(active_project_id)

with modeling_tabs[2]:
    render_analysis_dataset_tab(active_project_id)

with metric_config_tabs[0]:
    render_metric_center_tab(active_project_id, df)

with workbench_tabs[0]:
    render_business_question_tab(active_project_id)

if False:
    render_module_intro(
        "shield-check",
        "Quality control",
        "数据质量中心",
        "集中诊断缺失值、重复行、标识字段与异常值，并在不覆盖原始文件的前提下完成修复。",
    )
    st.subheader("数据质量总览")
    quality_action_message = st.session_state.pop("quality_action_message", None)
    if quality_action_message:
        st.success(quality_action_message)
    quality_cards = st.columns(6)
    with quality_cards[0].container(border=True):
        st.metric("数据质量评分", f"{quality_summary['score']} / 100")
        st.caption(quality_stars(quality_summary["score"]))
    with quality_cards[1].container(border=True):
        st.metric("缺失值", f"{quality_summary['missing_values']:,}")
    with quality_cards[2].container(border=True):
        st.metric("重复值", f"{quality_summary['duplicate_rows']:,}")
    with quality_cards[3].container(border=True):
        st.metric("疑似 ID 字段", quality_summary["identifier_column_count"])
    with quality_cards[4].container(border=True):
        st.metric("异常字段", quality_summary["suspicious_column_count"])
    with quality_cards[5].container(border=True):
        st.metric("异常值", f"{quality_summary['outlier_count']:,}")
    st.caption("评分根据缺失值、重复值、异常字段和异常值综合计算。疑似 ID 字段不参与数值统计和异常值分析。")

    st.subheader("缺失值诊断")
    missing_summary = summarize_missing_values(df)
    st.dataframe(missing_summary, use_container_width=True, hide_index=True)
    high_missing_columns = missing_summary.loc[missing_summary["缺失值比例"] >= 80, "字段名"].tolist()
    if high_missing_columns:
        st.warning(f"高缺失字段：{', '.join(map(str, high_missing_columns))}。建议删除字段或重新获取数据源。")
    else:
        st.info("当前未检测到缺失率达到 80% 的高缺失字段。")

    st.markdown("#### 缺失值处理")
    st.warning("所有处理仅修改当前会话中的 current_df，不会覆盖 original_df。")
    missing_fields = [column for column in df.columns if df[column].isna().any()]
    missing_action_columns = st.columns(2)
    if missing_action_columns[0].button(
        "删除高缺失字段",
        disabled=not high_missing_columns,
        key="quality_drop_high_missing",
        use_container_width=True,
    ):
        before = df.copy()
        after = drop_high_missing_columns(df)
        set_current_data(after, before)
        clear_outlier_treatment_result()
        st.session_state.quality_action_message = (
            f"已删除 {len(high_missing_columns)} 个高缺失字段，当前数据已更新。"
        )
        st.rerun()
    if missing_action_columns[1].button(
        "删除含缺失值的行",
        disabled=not missing_fields,
        key="quality_drop_missing_rows",
        use_container_width=True,
    ):
        before = df.copy()
        after = df.dropna().reset_index(drop=True)
        set_current_data(after, before)
        clear_outlier_treatment_result()
        st.session_state.quality_action_message = (
            f"已删除 {len(before) - len(after):,} 行含缺失值的数据，当前数据已更新。"
        )
        st.rerun()

    if missing_fields:
        missing_fix_column = st.selectbox(
            "选择需要填充的字段",
            missing_fields,
            key="quality_missing_fix_column",
        )
        selected_missing_series = df[missing_fix_column]
        missing_fix_buttons = st.columns(3)
        if missing_fix_buttons[0].button(
            "均值填充",
            disabled=not pd.api.types.is_numeric_dtype(selected_missing_series),
            key="quality_fill_mean",
            use_container_width=True,
        ):
            before = df.copy()
            after = apply_missing_value_fix(df, missing_fix_column, "均值填充")
            set_current_data(after, before)
            clear_outlier_treatment_result()
            st.session_state.quality_action_message = f"已对字段“{missing_fix_column}”执行均值填充。"
            st.rerun()
        if missing_fix_buttons[1].button(
            "中位数填充",
            disabled=not pd.api.types.is_numeric_dtype(selected_missing_series),
            key="quality_fill_median",
            use_container_width=True,
        ):
            before = df.copy()
            after = apply_missing_value_fix(df, missing_fix_column, "中位数填充")
            set_current_data(after, before)
            clear_outlier_treatment_result()
            st.session_state.quality_action_message = f"已对字段“{missing_fix_column}”执行中位数填充。"
            st.rerun()
        if missing_fix_buttons[2].button(
            "众数填充",
            disabled=pd.api.types.is_datetime64_any_dtype(selected_missing_series),
            key="quality_fill_mode",
            use_container_width=True,
        ):
            before = df.copy()
            after = apply_missing_value_fix(df, missing_fix_column, "众数填充")
            set_current_data(after, before)
            clear_outlier_treatment_result()
            st.session_state.quality_action_message = f"已对字段“{missing_fix_column}”执行众数填充。"
            st.rerun()
    else:
        st.info("当前数据没有需要处理的缺失值。")

    st.subheader("重复值诊断")
    duplicate_summary = summarize_duplicates(df)
    duplicate_cards = st.columns(2)
    duplicate_cards[0].metric("重复行数量", f"{duplicate_summary['duplicate_count']:,}")
    duplicate_cards[1].metric("重复行占比", f"{duplicate_summary['duplicate_ratio']:.2f}%")
    if duplicate_summary["preview"].empty:
        st.info("当前未检测到重复行。")
    else:
        st.dataframe(duplicate_summary["preview"].head(100), use_container_width=True)
    if st.button(
        "删除重复行",
        disabled=duplicate_summary["duplicate_count"] == 0,
        key="quality_drop_duplicates",
        use_container_width=True,
    ):
        before = df.copy()
        after = drop_duplicate_rows(df)
        st.session_state.duplicate_comparison = {
            "处理前行数": len(before),
            "处理后行数": len(after),
            "删除重复行数量": len(before) - len(after),
        }
        set_current_data(after, before)
        clear_outlier_treatment_result()
        st.session_state.quality_action_message = (
            f"已删除 {len(before) - len(after):,} 行重复数据，当前数据已更新。"
        )
        st.rerun()
    if st.session_state.get("duplicate_comparison"):
        duplicate_comparison = st.session_state.duplicate_comparison
        duplicate_comparison_cards = st.columns(3)
        duplicate_comparison_cards[0].metric("处理前行数", f"{duplicate_comparison['处理前行数']:,}")
        duplicate_comparison_cards[1].metric("处理后行数", f"{duplicate_comparison['处理后行数']:,}")
        duplicate_comparison_cards[2].metric(
            "删除重复行数量",
            f"{duplicate_comparison['删除重复行数量']:,}",
        )

    st.subheader("ID 字段识别")
    st.caption("ID字段通常只用于定位记录，不适合做均值、偏度、异常值检测和相关性分析。")
    identifier_summary = summarize_identifier_columns(df, identifier_columns)
    if identifier_summary.empty:
        st.info("当前未识别到疑似 ID 字段。")
    else:
        st.dataframe(identifier_summary, use_container_width=True, hide_index=True)

    if invalid_columns:
        st.warning(f"检测到疑似无效或近乎空字段：{', '.join(map(str, invalid_columns))}。建议删除。")
        st.caption("请先确认字段业务含义，再决定是否处理。")

    st.subheader("异常值诊断与处理")
    st.markdown("#### 异常值统计表")
    st.dataframe(eda_outliers, use_container_width=True, hide_index=True)
    if identifier_columns:
        st.info(f"已排除疑似 ID 字段：{', '.join(map(str, identifier_columns))}。这些字段不参与异常值检测和处理。")

    if not eda_numeric_columns:
        st.info("当前数据没有适合进行异常值分析的数值字段。")
    else:
        st.markdown("#### 选择字段")
        outlier_column = st.selectbox("选择需要诊断的数值字段", eda_numeric_columns, key="eda_outlier_column")

        if outlier_column in identifier_columns:
            st.warning("该字段被识别为ID字段，不适合进行异常值分析。")
        else:
            bounds = calculate_iqr_bounds(df, outlier_column)
            outlier_rows = detect_outliers_iqr(df, outlier_column)
            outlier_count = len(outlier_rows)
            valid_count = int(df[outlier_column].notna().sum())
            outlier_ratio = outlier_count / max(valid_count, 1) * 100

            st.markdown("#### 异常值判定依据")
            st.caption("IQR是一种统计检测方法。超过上下界的数据会被标记为统计异常值，但异常值不一定是错误数据，请结合业务场景判断。")
            boundary_cards = st.columns(4)
            boundary_cards[0].metric("Q1", f"{bounds['q1']:.3f}")
            boundary_cards[1].metric("Q3", f"{bounds['q3']:.3f}")
            boundary_cards[2].metric("IQR", f"{bounds['iqr']:.3f}")
            boundary_cards[3].metric("异常值数量", f"{outlier_count:,}")
            boundary_cards = st.columns(3)
            boundary_cards[0].metric("下界", f"{bounds['lower_bound']:.3f}")
            boundary_cards[1].metric("上界", f"{bounds['upper_bound']:.3f}")
            boundary_cards[2].metric("异常值占比", f"{outlier_ratio:.2f}%")

            st.markdown("#### 异常值预览表格")
            if outlier_rows.empty:
                st.info("当前字段未检测到 IQR 异常值。")
            else:
                outlier_preview = create_outlier_preview(
                    df,
                    outlier_column,
                    date_columns,
                    eda_category_columns,
                    identifier_columns,
                )
                st.dataframe(outlier_preview, use_container_width=True, hide_index=True)

            st.markdown("#### 异常值可视化")
            st.plotly_chart(
                px.box(df, y=outlier_column, points="outliers", title=f"{outlier_column} 箱型图"),
                use_container_width=True,
                key="quality_outlier_box",
            )
            if not outlier_rows.empty:
                st.plotly_chart(
                    px.histogram(
                        outlier_rows,
                        x=outlier_column,
                        nbins=30,
                        title=f"{outlier_column} 异常值分布直方图",
                    ),
                    use_container_width=True,
                    key="quality_outlier_histogram",
                )
                if date_columns:
                    outlier_date_column = st.selectbox(
                        "异常值时间分布日期字段",
                        date_columns,
                        key="outlier_date_column",
                    )
                    date_distribution = outlier_rows[[outlier_date_column]].dropna().copy()
                    date_distribution[outlier_date_column] = pd.to_datetime(
                        date_distribution[outlier_date_column], errors="coerce"
                    ).dt.date
                    date_distribution = (
                        date_distribution.dropna()
                        .groupby(outlier_date_column)
                        .size()
                        .reset_index(name="异常值数量")
                    )
                    if not date_distribution.empty:
                        st.plotly_chart(
                            px.line(
                                date_distribution,
                                x=outlier_date_column,
                                y="异常值数量",
                                markers=True,
                                title=f"{outlier_column} 异常值时间分布",
                            ),
                            use_container_width=True,
                            key="quality_outlier_time",
                        )

            st.markdown("#### 下载异常值")
            outlier_download = create_outlier_download(df, outlier_column)
            st.download_button(
                "下载当前字段异常值",
                data=outlier_download.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"outliers_{outlier_column}.csv",
                mime="text/csv",
                disabled=outlier_download.empty,
            )

            st.info("异常值不一定是错误数据，请查看明细并结合业务判断后再决定是否处理。")

            st.markdown("#### 异常值处理")
            st.warning("异常值不一定是错误数据，请结合业务判断后处理。")
            outlier_treatment_method = st.selectbox(
                "处理方式",
                ["保留异常值", "删除异常值所在行", "Winsorize 截断", "替换为中位数", "替换为指定分位数"],
                key="quality_outlier_treatment_method",
            )
            lower_quantile = 0.01
            upper_quantile = 0.99
            if outlier_treatment_method == "替换为指定分位数":
                quantile_columns = st.columns(2)
                lower_quantile = quantile_columns[0].number_input(
                    "下侧异常值替换分位数",
                    min_value=0.0,
                    max_value=0.49,
                    value=0.01,
                    step=0.01,
                    key="quality_lower_quantile",
                )
                upper_quantile = quantile_columns[1].number_input(
                    "上侧异常值替换分位数",
                    min_value=0.51,
                    max_value=1.0,
                    value=0.99,
                    step=0.01,
                    key="quality_upper_quantile",
                )
            if st.button(
                "应用异常值处理",
                disabled=outlier_rows.empty and outlier_treatment_method != "保留异常值",
                type="primary",
                key="quality_apply_outlier_treatment",
            ):
                before_outlier_treatment = df.copy()
                if outlier_treatment_method == "保留异常值":
                    after_outlier_treatment = before_outlier_treatment.copy()
                elif outlier_treatment_method == "删除异常值所在行":
                    after_outlier_treatment = remove_outliers(before_outlier_treatment, outlier_column)
                elif outlier_treatment_method == "Winsorize 截断":
                    after_outlier_treatment = winsorize_outliers(before_outlier_treatment, outlier_column)
                elif outlier_treatment_method == "替换为中位数":
                    after_outlier_treatment = replace_outliers_with_median(before_outlier_treatment, outlier_column)
                else:
                    after_outlier_treatment = replace_outliers_with_quantile(
                        before_outlier_treatment,
                        outlier_column,
                        lower_quantile,
                        upper_quantile,
                    )
                set_current_data(after_outlier_treatment, before_outlier_treatment)
                st.session_state.last_outlier_comparison = compare_before_after_outlier_treatment(
                    before_outlier_treatment,
                    after_outlier_treatment,
                    outlier_column,
                )
                st.session_state.last_outlier_before_df = before_outlier_treatment
                st.session_state.last_outlier_after_df = after_outlier_treatment
                st.session_state.last_outlier_column = outlier_column
                st.session_state.quality_action_message = "已完成异常值处理，当前数据已更新。"
                st.rerun()

            if st.session_state.get("last_outlier_comparison") is not None:
                st.markdown("#### 处理前后对比")
                st.dataframe(
                    st.session_state.last_outlier_comparison,
                    use_container_width=True,
                    hide_index=True,
                )
                outlier_comparison_charts = st.columns(2)
                outlier_comparison_charts[0].plotly_chart(
                    px.box(
                        st.session_state.last_outlier_before_df,
                        y=st.session_state.last_outlier_column,
                        points="outliers",
                        title=f"{st.session_state.last_outlier_column} 处理前",
                    ),
                    use_container_width=True,
                    key="quality_outlier_before_treatment",
                )
                outlier_comparison_charts[1].plotly_chart(
                    px.box(
                        st.session_state.last_outlier_after_df,
                        y=st.session_state.last_outlier_column,
                        points="outliers",
                        title=f"{st.session_state.last_outlier_column} 处理后",
                    ),
                    use_container_width=True,
                    key="quality_outlier_after_treatment",
                )
    st.subheader("数据修复建议")
    repair_suggestions = generate_data_repair_suggestions(df, invalid_columns, identifier_columns, eda_outliers)
    if repair_suggestions.empty:
        st.success("当前未发现需要优先修复的数据质量问题。")
    else:
        st.dataframe(repair_suggestions, use_container_width=True, hide_index=True)
        st.caption("数据质量页展示诊断结果与推荐处理方案。")

    if quality_summary["outlier_count"] > 0:
        st.info("检测到异常值：请在上方“异常值诊断与处理”区域查看明细，再决定保留、截断、替换或删除。")
    if identifier_columns:
        st.caption("疑似 ID 字段已自动从数值统计、相关性分析和异常值检测中排除，无需删除。")

    st.subheader("最近一次处理前后对比")
    if st.session_state.get("last_comparison") is not None:
        st.dataframe(st.session_state.last_comparison, use_container_width=True, hide_index=True)
    else:
        st.info("执行缺失值、重复值、异常字段或异常值处理后，将在这里显示前后变化。")

    st.subheader("恢复原始数据")
    st.warning("恢复后，current_df 将重置为上传时的 original_df；原始上传文件始终不会被覆盖。")
    if st.button("恢复原始数据", type="primary", key="quality_restore_original"):
        before = df.copy()
        set_current_data(st.session_state.original_df.copy(), before)
        clear_outlier_treatment_result()
        st.session_state.duplicate_comparison = None
        st.session_state.quality_action_message = "已恢复原始数据，current_df 已重置。"
        st.rerun()

    st.subheader("导出当前处理后数据")
    st.caption("导出基于 current_df，不会覆盖上传后的 original_df。")
    try:
        processed_data_excel = export_processed_data_excel(
            df,
            st.session_state.get("original_df"),
            quality_summary,
            repair_suggestions,
        )
        st.download_button(
            "下载 processed_data.xlsx",
            data=processed_data_excel,
            file_name="processed_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            key="quality_export_processed_data",
        )
    except Exception as exc:
        st.error(f"处理后数据导出失败：{exc}")

with workbench_tabs[1]:
    render_module_intro(
        "chart",
        "Exploration",
        "探索性分析",
        "从数值分布、类别结构与相关关系理解数据特征，所有统计均自动排除疑似 ID 字段。",
    )
    st.caption("数据质量问题请前往「数据质量」tab 处理。疑似 ID 字段已从探索分析中排除。")
    render_rule_based_eda_report(active_project_id)
    st.divider()
    exploration_tabs = st.tabs(["数值分析", "类别分析", "相关分析", "AI 探索洞察"])

    with exploration_tabs[0]:
        st.subheader("数值分析")
        if not eda_numeric_columns:
            st.info("当前数据没有可用于数值分析的字段。")
        else:
            selected_numeric = st.selectbox(
                "选择数值字段",
                eda_numeric_columns,
                key="exploration_numeric_column",
            )
            st.markdown("#### 数值字段总览")
            st.dataframe(
                summarize_numeric_columns(df, eda_numeric_columns),
                use_container_width=True,
                hide_index=True,
            )

            st.markdown(f"#### {selected_numeric} 数值画像")
            selected_numeric_profile = numeric_profile(df, selected_numeric)
            numeric_cards = st.columns(5)
            numeric_cards[0].metric("均值", f"{selected_numeric_profile['均值']:.3f}")
            numeric_cards[1].metric("中位数", f"{selected_numeric_profile['中位数']:.3f}")
            numeric_cards[2].metric("标准差", f"{selected_numeric_profile['标准差']:.3f}")
            numeric_cards[3].metric("最小值", f"{selected_numeric_profile['最小值']:.3f}")
            numeric_cards[4].metric("最大值", f"{selected_numeric_profile['最大值']:.3f}")
            numeric_cards = st.columns(4)
            numeric_cards[0].metric("偏度", f"{selected_numeric_profile['偏度']:.3f}")
            numeric_cards[1].metric("峰度", f"{selected_numeric_profile['峰度']:.3f}")
            numeric_cards[2].metric("缺失率", f"{selected_numeric_profile['缺失率']:.2f}%")
            numeric_cards[3].metric("异常值比例", f"{selected_numeric_profile['异常值比例']:.2f}%")
            st.info(interpret_numeric_distribution(df[selected_numeric]))

            numeric_charts = st.columns(2)
            numeric_charts[0].plotly_chart(
                histogram(df, selected_numeric),
                use_container_width=True,
                key="exploration_numeric_histogram",
            )
            numeric_charts[1].plotly_chart(
                box_plot(df, selected_numeric),
                use_container_width=True,
                key="exploration_numeric_box",
            )

    with exploration_tabs[1]:
        st.subheader("类别分析")
        if not eda_category_columns:
            st.info("当前数据没有可用于类别分析的字段。")
        else:
            selected_category = st.selectbox(
                "选择类别字段",
                eda_category_columns,
                key="exploration_category_column",
            )
            st.markdown("#### 类别字段总览")
            st.dataframe(
                summarize_categorical_columns(df, eda_category_columns),
                use_container_width=True,
                hide_index=True,
            )

            st.markdown(f"#### {selected_category} 类别画像")
            selected_category_profile = categorical_profile(df[selected_category])
            category_cards = st.columns(5)
            category_cards[0].metric("唯一值数量", selected_category_profile["唯一值数量"])
            category_cards[1].metric("Top 1 类别", str(selected_category_profile["Top 1 类别"]))
            category_cards[2].metric("Top 1 占比", f"{selected_category_profile['Top 1 占比']:.2f}%")
            category_cards[3].metric("Top 5 类别覆盖率", f"{selected_category_profile['Top 5 类别覆盖率']:.2f}%")
            category_cards[4].metric("集中程度", selected_category_profile["集中程度"])
            st.info(interpret_categorical_distribution(df[selected_category], selected_category))

            unique_count = selected_category_profile["唯一值数量"]
            if unique_count > 50:
                st.warning("该字段唯一值过多，可能更像ID或自由文本，不建议直接做类别分布分析。")
            if unique_count <= 1:
                category_top_n = 1
                st.caption("当前字段仅有一个有效类别。")
            else:
                category_top_n = st.slider(
                    "Top N",
                    min_value=1,
                    max_value=min(30, unique_count),
                    value=min(10, unique_count),
                    key="exploration_category_top_n",
                )
            category_distribution = categorical_distribution_table(df[selected_category], category_top_n)
            category_charts = st.columns(2)
            category_charts[0].plotly_chart(
                px.bar(
                    category_distribution,
                    x="类别",
                    y="数量",
                    title=f"{selected_category} Top {category_top_n} 类别",
                ),
                use_container_width=True,
                key="exploration_category_bar",
            )
            category_charts[1].plotly_chart(
                px.pie(
                    category_distribution,
                    names="类别",
                    values="数量",
                    title=f"{selected_category} Top {category_top_n} 占比",
                ),
                use_container_width=True,
                key="exploration_category_pie",
            )

    with exploration_tabs[2]:
        st.subheader("相关分析")
        st.caption("相关性仅表示变量共同变化关系，不代表因果关系。")
        if len(eda_numeric_columns) < 2:
            st.info("当前可用于相关性分析的数值字段少于2个。")
        else:
            st.plotly_chart(
                correlation_heatmap(df, eda_numeric_columns),
                use_container_width=True,
                key="eda_correlation",
            )
            st.markdown("#### 高相关字段对")
            correlation_pairs = calculate_correlation_pairs(df, eda_numeric_columns)
            st.dataframe(correlation_pairs, use_container_width=True, hide_index=True)

    with exploration_tabs[3]:
        render_module_intro(
            "sparkles",
            "AI copilot",
            "AI 探索洞察",
            "基于探索结果提炼关键发现、业务含义与下一步分析问题，不重复数据质量内容。",
        )
        st.subheader("AI 探索洞察")
        st.caption("AI 仅基于数值统计、类别统计和相关分析生成洞察，不重复数据质量内容。")
        if not api_key:
            st.info("在左侧填写 API Key 后，可生成关键发现、业务含义和建议进一步分析的问题。")
        if st.button("生成 AI 探索洞察", disabled=not api_key, type="primary"):
            try:
                with st.spinner("AI 正在分析探索结果..."):
                    payload = build_analysis_payload(df, eda_numeric_columns, eda_category_columns)
                    st.session_state.ai_exploration_result = request_ai_insights(payload, api_key, ai_model, ai_base_url)
                st.session_state.ai_connection_status = {
                    "signature": ai_config_signature,
                    "success": True,
                    "message": "接入成功，AI 探索洞察已生成。",
                }
            except Exception as exc:
                st.session_state.ai_connection_status = {
                    "signature": ai_config_signature,
                    "success": False,
                    "message": f"接入失败：{exc}",
                }
                st.error(f"AI 探索洞察生成失败：{exc}")
        if st.session_state.get("ai_exploration_result"):
            st.markdown(st.session_state.ai_exploration_result)

with workbench_tabs[2]:
    render_dashboard_tab(active_project_id)

with workbench_tabs[3]:
    render_module_intro(
        "layout-dashboard",
        "Business intelligence",
        "业务分析",
        "围绕经营指标、时间趋势、维度贡献和业务问题生成可直接支持决策的分析结果。",
    )
    render_rule_based_business_analysis(active_project_id)
    st.divider()
    business_tabs = st.tabs(["报表仪表盘", "维度对比分析", "业务问答"])
    business_fields = identify_business_fields(
        df,
        date_columns,
        category_columns,
        numeric_columns,
        identifier_columns,
    )
    business_fields = prioritize_business_fields(
        df,
        saved_field_mappings,
        business_fields,
    )
    business_metrics = business_metric_options(business_fields)
    business_dimensions = business_fields["dimensions"]

    with business_tabs[0]:
        st.subheader("报表仪表盘")
        date_column = business_fields["date_column"]
        if not date_column:
            st.info("未检测到时间字段，无法生成趋势报表。")
        else:
            dashboard_controls = st.columns(2)
            dashboard_period = dashboard_controls[0].radio(
                "分析周期",
                ["日报", "周报", "月报", "季报", "年报"],
                horizontal=True,
                key="business_dashboard_period",
            )
            selected_date_column = dashboard_controls[1].selectbox(
                "时间字段",
                date_columns,
                index=date_columns.index(date_column),
                key="business_dashboard_date",
            )

            business_dates = pd.to_datetime(df[selected_date_column], errors="coerce")
            available_years = sorted(business_dates.dropna().dt.year.unique().astype(int).tolist())
            slice_columns = st.columns(3)
            selected_year = slice_columns[0].selectbox(
                "年份",
                ["全部"] + available_years,
                key="business_year",
            )
            year_dates = business_dates if selected_year == "全部" else business_dates.loc[business_dates.dt.year == selected_year]
            available_quarters = sorted(year_dates.dropna().dt.quarter.unique().astype(int).tolist())
            selected_quarter = slice_columns[1].selectbox(
                "季度",
                ["全部"] + available_quarters,
                key="business_quarter",
            )
            quarter_dates = year_dates if selected_quarter == "全部" else year_dates.loc[year_dates.dt.quarter == selected_quarter]
            available_months = sorted(quarter_dates.dropna().dt.month.unique().astype(int).tolist())
            selected_month = slice_columns[2].selectbox(
                "月份",
                ["全部"] + available_months,
                key="business_month",
            )
            dashboard_df = filter_time_slice(
                df,
                selected_date_column,
                None if selected_year == "全部" else selected_year,
                None if selected_quarter == "全部" else selected_quarter,
                None if selected_month == "全部" else selected_month,
            )
            dashboard = generate_dashboard(
                dashboard_df,
                selected_date_column,
                dashboard_period,
                business_fields,
                comparison_df=df,
            )

            if dashboard["current_period"] is None:
                st.info("当前时间筛选条件下没有可生成报表的数据。")
            else:
                st.caption(f"当前报表周期：{dashboard['current_period']}")
                kpi_cards = st.columns(4)
                for index, metric in enumerate(["成交金额", "订单数", "客户数", "客单价"]):
                    value = dashboard["kpi"].get(metric)
                    display_value = "暂无数据" if value is None else f"{value:,.2f}"
                    mom = dashboard["mom"].get(metric)
                    kpi_cards[index].metric(
                        f"本期{metric}",
                        display_value,
                        None if mom is None else f"环比 {mom:+.1f}%",
                    )
                    yoy = dashboard["yoy"].get(metric)
                    kpi_cards[index].caption("暂无同比数据" if yoy is None else f"同比 {yoy:+.1f}%")

                st.markdown("#### 经营趋势")
                trend = dashboard["trend"]
                trend_metrics = [metric for metric in ["成交金额", "订单数", "客户数", "客单价"] if metric in trend and trend[metric].notna().any()]
                if trend_metrics:
                    trend_chart_columns = st.columns(2)
                    for index, metric in enumerate(trend_metrics):
                        trend_chart_columns[index % 2].plotly_chart(
                            px.line(
                                trend,
                                x="周期",
                                y=metric,
                                markers=True,
                                title=f"{metric}{dashboard_period}趋势",
                            ),
                            use_container_width=True,
                            key=f"business_dashboard_trend_{metric}",
                        )

                if st.button(f"生成AI{dashboard_period}", disabled=not api_key, type="primary"):
                    try:
                        top_context = {}
                        for label, hints in {
                            "Top区域": ("区域", "地区", "省份", "region", "province"),
                            "Top产品": ("产品", "商品", "product"),
                            "Top人员": ("销售工号", "销售人员", "业务员", "salesperson", "employee"),
                        }.items():
                            dimension = next(
                                (column for column in business_dimensions if any(hint in str(column) for hint in hints)),
                                None,
                            )
                            if dimension and business_metrics:
                                top_context[label] = generate_top_n(
                                    dashboard["current_df"],
                                    dimension,
                                    business_metrics[0],
                                    business_fields,
                                    5,
                                ).to_dict("records")
                        report_payload = {
                            "周期": dashboard["current_period"],
                            "KPI": dashboard["kpi"],
                            "环比": dashboard["mom"],
                            "同比": dashboard["yoy"],
                            "趋势": dashboard["trend"].tail(12).to_dict("records"),
                            **top_context,
                        }
                        with st.spinner("AI 正在生成管理层报表总结..."):
                            st.session_state.ai_business_report = request_management_summary(
                                report_payload,
                                api_key,
                                ai_model,
                                ai_base_url,
                            )
                    except Exception as exc:
                        st.error(f"AI 报表总结生成失败：{exc}")
                if st.session_state.get("ai_business_report"):
                    st.markdown(st.session_state.ai_business_report)

    with business_tabs[1]:
        st.subheader("维度对比分析")
        if not business_dimensions or not business_metrics:
            st.info("当前数据缺少可用于业务维度对比的分类字段或业务指标。")
        else:
            dimension_controls = st.columns(3)
            business_dimension = dimension_controls[0].selectbox(
                "分析维度",
                business_dimensions,
                key="business_dimension",
            )
            business_metric = dimension_controls[1].selectbox(
                "分析指标",
                business_metrics,
                key="business_metric",
            )
            business_top_n = dimension_controls[2].selectbox(
                "Top N",
                [5, 10, 20],
                index=1,
                key="business_top_n",
            )

            top_result = generate_top_n(df, business_dimension, business_metric, business_fields, business_top_n)
            share_result = generate_share_analysis(df, business_dimension, business_metric, business_fields)

            st.markdown(f"#### {business_metric} Top {business_top_n} {business_dimension}")
            st.dataframe(top_result, use_container_width=True, hide_index=True)
            comparison_charts = st.columns(2)
            comparison_charts[0].plotly_chart(
                px.bar(
                    top_result,
                    x=business_metric,
                    y=business_dimension,
                    orientation="h",
                    title=f"{business_dimension} vs {business_metric}",
                ),
                use_container_width=True,
                key="business_dimension_bar",
            )
            comparison_charts[1].plotly_chart(
                px.pie(
                    share_result.head(business_top_n),
                    names=business_dimension,
                    values=business_metric,
                    hole=0.45,
                    title=f"各{business_dimension}{business_metric}占比",
                ),
                use_container_width=True,
                key="business_dimension_share",
            )

            st.markdown("#### 维度趋势分析")
            if business_fields["date_column"]:
                dimension_trend = generate_dimension_trend(
                    df,
                    business_fields["date_column"],
                    business_dimension,
                    business_metric,
                    business_fields,
                    period="月报",
                    top_n=5,
                )
                if not dimension_trend.empty:
                    st.plotly_chart(
                        px.line(
                            dimension_trend,
                            x="周期",
                            y=business_metric,
                            color=business_dimension,
                            markers=True,
                            title=f"Top 5 {business_dimension}{business_metric}趋势",
                        ),
                        use_container_width=True,
                        key="business_dimension_trend",
                    )
            else:
                st.info("未检测到时间字段，无法生成维度趋势分析。")

    with business_tabs[2]:
        st.subheader("业务问答")
        st.caption("系统只执行结构化分组查询，不生成或执行 AI 代码。")
        business_question = st.text_input(
            "请输入业务问题",
            placeholder="例如：成交金额最高的5个销售人员是谁",
            key="business_question",
        )
        if st.button("分析业务问题", disabled=not business_question):
            try:
                plan = parse_business_question(
                    business_question,
                    business_dimensions,
                    business_metrics,
                    api_key or None,
                    ai_model,
                    ai_base_url,
                )
                result = execute_business_query(df, plan, business_fields)
                st.session_state.business_query_plan = plan
                st.session_state.business_query_result = result
                st.session_state.business_query_explanation = generate_business_explanation(
                    result,
                    plan["dimension"],
                    plan["metric"],
                )
            except Exception as exc:
                st.error(f"业务问题分析失败：{exc}")
        if st.session_state.get("business_query_plan"):
            st.markdown("#### 结构化查询")
            st.json(st.session_state.business_query_plan)
            result = st.session_state.business_query_result
            plan = st.session_state.business_query_plan
            result_metric = "增长率" if "增长率" in result.columns else plan["metric"]
            st.markdown("#### 查询结果")
            st.dataframe(result, use_container_width=True, hide_index=True)
            st.plotly_chart(
                px.bar(
                    result,
                    x=plan["dimension"],
                    y=result_metric,
                    title=f"{plan['metric']} Top {plan['limit']} {plan['dimension']}",
                ),
                use_container_width=True,
                key="business_question_chart",
            )
            st.info(st.session_state.business_query_explanation)

if False:
    st.subheader("数据清洗中心")
    st.info("所有操作只修改当前会话中的 current_df，不会覆盖上传后的 original_df。")

    st.markdown("### 1. 缺失值处理")
    missing_fields = [column for column in df.columns if df[column].isna().any()]
    if not missing_fields:
        st.info("当前数据没有缺失值。")
    else:
        missing_clean_columns = st.columns(2)
        cleaning_missing_column = missing_clean_columns[0].selectbox(
            "选择缺失字段",
            missing_fields,
            key="cleaning_missing_column",
        )
        cleaning_missing_method = missing_clean_columns[1].selectbox(
            "选择处理方式",
            ["删除所有含缺失值的行", "删除该字段缺失行", "均值填充", "中位数填充", "众数填充"],
            key="cleaning_missing_method",
        )
        if st.button("应用缺失值处理", type="primary", key="cleaning_apply_missing"):
            try:
                before = df.copy()
                if cleaning_missing_method == "删除所有含缺失值的行":
                    after = df.dropna().reset_index(drop=True)
                elif cleaning_missing_method == "删除该字段缺失行":
                    after = df.dropna(subset=[cleaning_missing_column]).reset_index(drop=True)
                else:
                    after = apply_missing_value_fix(df, cleaning_missing_column, cleaning_missing_method)
                set_current_data(after, before)
                clear_outlier_treatment_result()
                st.rerun()
            except Exception as exc:
                st.error(f"缺失值处理失败：{exc}")

    problem_columns = list(dict.fromkeys(high_missing_columns + invalid_columns))
    if problem_columns:
        st.markdown("#### 谨慎删除问题字段")
        st.warning("删除字段会直接影响后续分析。请确认业务含义后，仅删除明确不再需要的字段。")
        problem_column = st.selectbox(
            "选择需要删除的问题字段",
            problem_columns,
            key="cleaning_problem_column",
        )
        if st.button("删除选定问题字段", key="cleaning_drop_problem_column"):
            before = df.copy()
            set_current_data(df.drop(columns=[problem_column]), before)
            clear_outlier_treatment_result()
            st.rerun()

    st.markdown("### 2. 重复值处理")
    cleaning_duplicates = summarize_duplicates(df)
    duplicate_cards = st.columns(2)
    duplicate_cards[0].metric("重复行数量", f"{cleaning_duplicates['duplicate_count']:,}")
    duplicate_cards[1].metric("重复行占比", f"{cleaning_duplicates['duplicate_ratio']:.2f}%")
    if cleaning_duplicates["preview"].empty:
        st.info("当前未检测到重复行。")
    else:
        st.dataframe(cleaning_duplicates["preview"].head(100), use_container_width=True)
    if st.button(
        "删除重复行",
        disabled=cleaning_duplicates["duplicate_count"] == 0,
        key="cleaning_drop_duplicates",
    ):
        before = df.copy()
        after = drop_duplicate_rows(df)
        set_current_data(after, before)
        clear_outlier_treatment_result()
        st.rerun()

    st.markdown("### 3. 异常值处理")
    if not eda_numeric_columns:
        st.info("当前没有适合进行异常值处理的非 ID 数值字段。")
    else:
        cleaning_outlier_column = st.selectbox(
            "选择异常值字段",
            eda_numeric_columns,
            key="cleaning_outlier_column",
        )
        cleaning_outliers = detect_outliers_iqr(df, cleaning_outlier_column)
        cleaning_bounds = calculate_iqr_bounds(df, cleaning_outlier_column)
        st.caption(
            f"IQR 下界：{cleaning_bounds['lower_bound']:.3f}；上界：{cleaning_bounds['upper_bound']:.3f}；"
            f"检测到异常值 {len(cleaning_outliers):,} 条。异常值不一定是错误数据，请结合业务判断。"
        )
        if cleaning_outliers.empty:
            st.info("当前字段未检测到 IQR 异常值。")
        else:
            st.dataframe(
                create_outlier_preview(
                    df,
                    cleaning_outlier_column,
                    date_columns,
                    eda_category_columns,
                    identifier_columns,
                ),
                use_container_width=True,
                hide_index=True,
            )
        cleaning_outlier_method = st.selectbox(
            "异常值处理方式",
            ["保留异常值", "删除异常值所在行", "Winsorize 截断", "替换为中位数", "替换为指定分位数"],
            key="cleaning_outlier_method",
        )
        cleaning_lower_quantile = 0.01
        cleaning_upper_quantile = 0.99
        if cleaning_outlier_method == "替换为指定分位数":
            quantile_columns = st.columns(2)
            cleaning_lower_quantile = quantile_columns[0].number_input(
                "下侧替换分位数",
                min_value=0.0,
                max_value=0.49,
                value=0.01,
                step=0.01,
                key="cleaning_lower_quantile",
            )
            cleaning_upper_quantile = quantile_columns[1].number_input(
                "上侧替换分位数",
                min_value=0.51,
                max_value=1.0,
                value=0.99,
                step=0.01,
                key="cleaning_upper_quantile",
            )
        if st.button("应用异常值处理", type="primary", key="cleaning_apply_outlier"):
            before_outlier_treatment = df.copy()
            if cleaning_outlier_method == "保留异常值":
                after_outlier_treatment = before_outlier_treatment.copy()
            elif cleaning_outlier_method == "删除异常值所在行":
                after_outlier_treatment = remove_outliers(before_outlier_treatment, cleaning_outlier_column)
            elif cleaning_outlier_method == "Winsorize 截断":
                after_outlier_treatment = winsorize_outliers(before_outlier_treatment, cleaning_outlier_column)
            elif cleaning_outlier_method == "替换为中位数":
                after_outlier_treatment = replace_outliers_with_median(before_outlier_treatment, cleaning_outlier_column)
            else:
                after_outlier_treatment = replace_outliers_with_quantile(
                    before_outlier_treatment,
                    cleaning_outlier_column,
                    cleaning_lower_quantile,
                    cleaning_upper_quantile,
                )
            set_current_data(after_outlier_treatment, before_outlier_treatment)
            st.session_state.last_outlier_comparison = compare_before_after_outlier_treatment(
                before_outlier_treatment,
                after_outlier_treatment,
                cleaning_outlier_column,
            )
            st.session_state.last_outlier_before_df = before_outlier_treatment
            st.session_state.last_outlier_after_df = after_outlier_treatment
            st.session_state.last_outlier_column = cleaning_outlier_column
            st.rerun()

        if st.session_state.get("last_outlier_comparison") is not None:
            st.markdown("#### 最近一次异常值处理对比")
            st.dataframe(st.session_state.last_outlier_comparison, use_container_width=True, hide_index=True)
            outlier_comparison_charts = st.columns(2)
            outlier_comparison_charts[0].plotly_chart(
                px.box(
                    st.session_state.last_outlier_before_df,
                    y=st.session_state.last_outlier_column,
                    points="outliers",
                    title=f"{st.session_state.last_outlier_column} 处理前",
                ),
                use_container_width=True,
                key="cleaning_outlier_before",
            )
            outlier_comparison_charts[1].plotly_chart(
                px.box(
                    st.session_state.last_outlier_after_df,
                    y=st.session_state.last_outlier_column,
                    points="outliers",
                    title=f"{st.session_state.last_outlier_column} 处理后",
                ),
                use_container_width=True,
                key="cleaning_outlier_after",
            )

    st.markdown("### 4. 变量转换")
    if not eda_numeric_columns:
        st.info("当前没有适合进行变量转换的非 ID 数值字段。")
    else:
        transform_columns = st.columns(3)
        transform_column = transform_columns[0].selectbox(
            "选择转换字段",
            eda_numeric_columns,
            key="cleaning_transform_column",
        )
        transform_method = transform_columns[1].selectbox(
            "转换方式",
            ["log1p 处理", "分箱处理"],
            key="cleaning_transform_method",
        )
        transform_bins = transform_columns[2].slider(
            "分箱数量",
            2,
            20,
            5,
            disabled=transform_method != "分箱处理",
            key="cleaning_transform_bins",
        )
        if st.button("应用变量转换", type="primary", key="cleaning_apply_transform"):
            try:
                before = df.copy()
                after = clean_data(df, transform_method, transform_column, transform_bins)
                set_current_data(after, before)
                clear_outlier_treatment_result()
                st.rerun()
            except Exception as exc:
                st.error(f"变量转换失败：{exc}")

    st.markdown("### 5. 处理前后对比")
    if st.session_state.last_comparison is not None:
        st.dataframe(st.session_state.last_comparison, use_container_width=True, hide_index=True)
    else:
        st.info("执行数据清洗后，将在这里显示行数、列数、缺失值总数和重复行数变化。")

    st.markdown("### 6. 恢复原始数据")
    st.warning("恢复后，当前会话中的所有清洗结果将被原始上传数据替换。")
    if st.button("恢复原始数据", type="primary", key="cleaning_restore_original"):
        set_current_data(st.session_state.original_df.copy(), df)
        clear_outlier_treatment_result()
        st.rerun()

    st.subheader("当前数据预览")
    st.dataframe(df.head(50), use_container_width=True)
    st.subheader("导出处理后数据")
    st.write("将当前会话中清洗后的完整数据下载为新文件。")
    export_format = st.selectbox("导出格式", list(EXPORT_OPTIONS), key="export_format")
    try:
        export_bytes = export_dataframe(df, export_format)
        extension, mime = EXPORT_OPTIONS[export_format]
        original_stem = Path(st.session_state.file_name).stem
        st.download_button(
            f"下载 {export_format} 文件",
            data=export_bytes,
            file_name=f"{original_stem}_处理后.{extension}",
            mime=mime,
            type="primary",
        )
        if export_format == "XLS":
            st.caption("传统 XLS 格式最多支持 65,535 行和 256 列；更大的数据请使用 XLSX 或 CSV。")
    except Exception as exc:
        st.error(f"生成导出文件失败：{exc}")

if False:
    st.subheader("规则式查询")
    if category_columns and numeric_columns:
        date_choice = st.selectbox("日期字段（可选）", ["不筛选日期"] + date_columns, key="query_date")
        value_choice = st.selectbox("数值字段", numeric_columns, key="query_value")
        category_choice = st.selectbox("类别字段", category_columns, key="query_category")
        agg_choice = st.selectbox("聚合方式", ["sum", "mean", "count", "max", "min"], key="query_agg")
        years = []
        if date_choice != "不筛选日期":
            years = sorted(df[date_choice].dropna().dt.year.unique().astype(int).tolist())
        year_choice = st.selectbox("筛选年份", ["全部年份"] + years, key="query_year")
        query_top_n = st.slider("Top N", 1, 30, 5, key="query_top_n")
        if st.button("运行查询", type="primary"):
            result = run_query(
                df,
                None if date_choice == "不筛选日期" else date_choice,
                value_choice,
                category_choice,
                agg_choice,
                None if year_choice == "全部年份" else year_choice,
                query_top_n,
            )
            period = "全部年份" if year_choice == "全部年份" else f"{year_choice}年"
            st.success(f"{period}按 {agg_choice} 排名最高的 {query_top_n} 个{category_choice}")
            st.dataframe(result, use_container_width=True, hide_index=True)
            y_column = "count" if agg_choice == "count" else value_choice
            st.plotly_chart(
                px.bar(result, x=category_choice, y=y_column, title="查询结果"),
                use_container_width=True,
                key="query_result_chart",
            )
    else:
        st.info("规则式查询至少需要一个类别字段和一个数值字段。")

with delivery_tabs[0]:
    st.subheader("报告导出中心")
    st.caption("将当前处理后的数据与分析结果整理为 Excel、Word、PPT 和 AI周期报告。所有导出均基于 current_df，不会覆盖 original_df。")
    word_template_source = None
    ppt_template_source = None
    st.markdown("### 报告模板设置")
    st.caption(
        "你可以上传公司 Word / PPT 模板，并在模板中使用占位符。系统会根据当前处理后的数据和分析结果自动替换内容。"
        "如果没有上传模板，将使用默认模板。"
    )
    st.radio(
        "模板模式",
        ["使用默认模板", "上传自定义模板"],
        horizontal=True,
        key="report_template_mode",
    )
    if st.session_state.report_template_mode == "上传自定义模板":
        uploaded_report_template = st.file_uploader(
            "上传模板",
            type=["docx", "pptx"],
            key="report_template_uploader",
            help="模板仅保存在当前浏览器会话中，不会覆盖项目内置默认模板。",
        )
        if uploaded_report_template is None:
            st.info("请选择一个 Word 或 PPT 模板。")
        else:
            uploaded_template_signature = (
                uploaded_report_template.name,
                uploaded_report_template.size,
            )
            if (
                st.session_state.get("uploaded_template_signature")
                != uploaded_template_signature
            ):
                try:
                    save_uploaded_template(uploaded_report_template)
                    st.session_state.uploaded_template_signature = (
                        uploaded_template_signature
                    )
                    st.success("自定义模板已加载，仅在当前浏览器会话中使用。")
                except Exception as exc:
                    st.error(f"模板读取失败：{exc}")
    else:
        st.info(
            "当前 Excel Dashboard 由系统代码直接生成；Word / PPT 使用系统默认简洁模板。"
        )

    if st.session_state.report_template_mode == "上传自定义模板":
        try:
            active_template = get_active_template()
            active_template_info = active_template["template_info"]
            template_info_columns = st.columns(2)
            template_info_columns[0].metric(
                "模板类型",
                active_template_info["template_type_label"],
            )
            template_info_columns[1].metric(
                "文件名",
                active_template_info["file_name"],
            )
            if active_template["workbook"] is not None:
                active_template["workbook"].close()
            if active_template_info["template_type"] == "word_template":
                word_template_source = active_template["file_bytes"]
            elif active_template_info["template_type"] == "ppt_template":
                ppt_template_source = active_template["file_bytes"]
        except Exception as exc:
            st.warning(f"当前模板暂不可用：{exc}")

    with st.expander("可用占位符说明"):
        placeholder_columns = st.columns(2)
        for index, placeholder in enumerate(REPORT_TEMPLATE_PLACEHOLDERS):
            placeholder_columns[index % 2].code(placeholder)

    report_route_columns = st.columns(5)
    for column, title, description in zip(
        report_route_columns,
        ["数据包导出", "Word分析报告", "PPT汇报材料", "AI周期报告", "管理层汇报"],
        ["Excel 数据包", "完整分析文档", "文字版演示稿", "周报至年报", "决策摘要与 PPT"],
    ):
        with column.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(description)
    report_tabs = st.tabs(["数据包导出", "Word分析报告", "PPT汇报材料", "AI周期报告", "管理层汇报"])

    report_numeric_summary = summarize_numeric_columns(df, eda_numeric_columns)
    report_categorical_summary = summarize_categorical_columns(df, eda_category_columns)
    report_business_result = st.session_state.get("business_query_result")
    if not isinstance(report_business_result, pd.DataFrame) or report_business_result.empty:
        if business_dimensions and business_metrics:
            report_business_result = generate_top_n(
                df,
                business_dimensions[0],
                business_metrics[0],
                business_fields,
                10,
            )
        else:
            report_business_result = None
    report_quality_summary = dict(quality_summary)
    if "repair_suggestions" in globals():
        if isinstance(repair_suggestions, pd.DataFrame):
            report_quality_summary["data_repair_suggestions"] = repair_suggestions.to_dict("records")
        elif isinstance(repair_suggestions, list):
            report_quality_summary["data_repair_suggestions"] = repair_suggestions
    report_trend = []
    if business_fields.get("date_column"):
        report_dashboard = generate_dashboard(
            df,
            business_fields["date_column"],
            "月报",
            business_fields,
            comparison_df=df,
        )
        report_trend = report_dashboard.get("trend", pd.DataFrame()).tail(12).to_dict("records")
    report_business_summary = {
        "核心 KPI": calculate_kpi(df, business_fields),
        "时间趋势": report_trend or "尚未生成",
        "维度对比 / Top N": (
            report_business_result.head(10).to_dict("records")
            if isinstance(report_business_result, pd.DataFrame) and not report_business_result.empty
            else "尚未生成"
        ),
        "字段映射优先项": mapping_business_summary(df, saved_field_mappings),
    }
    report_ai_summary = (
        st.session_state.get("ai_business_report")
        or st.session_state.get("ai_exploration_result")
        or "尚未生成 AI 总结。"
    )
    report_correlation_summary = calculate_correlation_pairs(df, eda_numeric_columns)
    report_template_context = {
        "report_title": "DataInsight Agent 数据分析报告",
        "quality_summary": report_quality_summary,
        "numeric_summary": report_numeric_summary,
        "categorical_summary": report_categorical_summary,
        "correlation_summary": report_correlation_summary,
        "business_summary": report_business_summary,
        "kpi_summary": calculate_kpi(df, business_fields),
        "trend_summary": report_trend,
        "topn_summary": report_business_result,
        "ai_insights": report_ai_summary,
        "risks": report_ai_summary,
        "recommendations": report_ai_summary,
    }

    with report_tabs[0]:
        st.markdown("### 下载 Excel 数据包")
        st.caption("包含处理后数据、数据质量摘要、数值统计、类别统计和业务分析结果。")
        try:
            full_excel = export_full_excel_report(
                df,
                report_quality_summary,
                report_numeric_summary,
                report_categorical_summary,
                report_business_result,
            )
            st.download_button(
                "下载 Excel 数据包",
                data=full_excel,
                file_name="data_insight_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                key="report_full_excel",
            )
        except Exception as exc:
            st.error(f"Excel 报告生成失败：{exc}")

        st.markdown("### Excel Dashboard 报告")
        st.caption(
            "基于 current_df 自动聚合并生成可直接查看的 Excel Dashboard，"
            "不依赖数据透视表、透视图或切片器刷新。"
        )
        st.markdown("#### Dashboard 字段设置")
        dashboard_detected_fields = prioritize_dashboard_fields(
            df,
            saved_field_mappings,
            detect_dashboard_fields(df),
        )
        dashboard_all_columns = list(df.columns)
        dashboard_numeric_options = [
            column
            for column in dashboard_all_columns
            if pd.api.types.is_numeric_dtype(df[column])
        ]

        def dashboard_field_index(options, detected_value):
            return options.index(detected_value) if detected_value in options else 0

        dashboard_date_options = ["不使用"] + dashboard_all_columns
        dashboard_amount_options = ["不使用"] + dashboard_numeric_options
        dashboard_customer_options = ["不使用"] + dashboard_numeric_options
        dashboard_dimension_options = ["不使用"] + dashboard_all_columns
        dashboard_field_columns = st.columns(5)
        dashboard_date_column = dashboard_field_columns[0].selectbox(
            "日期字段",
            dashboard_date_options,
            index=dashboard_field_index(
                dashboard_date_options,
                dashboard_detected_fields.get("date_column"),
            ),
            key="dashboard_export_date_column",
        )
        dashboard_amount_column = dashboard_field_columns[1].selectbox(
            "金额字段",
            dashboard_amount_options,
            index=dashboard_field_index(
                dashboard_amount_options,
                dashboard_detected_fields.get("amount_column"),
            ),
            key="dashboard_export_amount_column",
        )
        dashboard_customer_column = dashboard_field_columns[2].selectbox(
            "客户数字段",
            dashboard_customer_options,
            index=dashboard_field_index(
                dashboard_customer_options,
                dashboard_detected_fields.get("customer_count_column"),
            ),
            key="dashboard_export_customer_column",
        )
        dashboard_product_column = dashboard_field_columns[3].selectbox(
            "产品字段",
            dashboard_dimension_options,
            index=dashboard_field_index(
                dashboard_dimension_options,
                dashboard_detected_fields.get("product_column"),
            ),
            key="dashboard_export_product_column",
        )
        dashboard_region_column = dashboard_field_columns[4].selectbox(
            "地区字段",
            dashboard_dimension_options,
            index=dashboard_field_index(
                dashboard_dimension_options,
                dashboard_detected_fields.get("region_column"),
            ),
            key="dashboard_export_region_column",
        )
        dashboard_field_config = {
            "date_column": None if dashboard_date_column == "不使用" else dashboard_date_column,
            "amount_column": None if dashboard_amount_column == "不使用" else dashboard_amount_column,
            "customer_count_column": (
                None if dashboard_customer_column == "不使用" else dashboard_customer_column
            ),
            "product_column": (
                None if dashboard_product_column == "不使用" else dashboard_product_column
            ),
            "region_column": (
                None if dashboard_region_column == "不使用" else dashboard_region_column
            ),
            "order_id_column": dashboard_detected_fields.get("order_id_column"),
        }
        st.caption(
            "系统已自动选择最匹配的字段；如识别不准确，可在下载前手动调整。"
        )
        try:
            dashboard_excel = build_generated_dashboard_export(
                df,
                dashboard_field_config,
            )
            st.download_button(
                "下载 Excel Dashboard 报告",
                data=dashboard_excel,
                file_name="data_insight_dashboard.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="report_dashboard_excel",
            )
        except Exception as exc:
            st.error(f"Excel Dashboard 生成失败：{exc}")

    with report_tabs[1]:
        st.markdown("### 下载 Word 分析报告")
        st.caption("自动替换上传的 Word 模板占位符；未上传 Word 模板时使用系统默认报告结构。")
        try:
            word_report = build_word_template_export(
                df,
                word_template_source,
                report_template_context,
            )
            st.download_button(
                "下载 Word 分析报告",
                data=word_report,
                file_name="data_insight_report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="report_word",
            )
        except Exception as exc:
            st.error(f"Word 报告生成失败：{exc}")

    with report_tabs[2]:
        st.markdown("### 下载 PPT 汇报材料")
        st.info("自动替换上传的 PPT 模板占位符；未上传 PPT 模板时使用系统默认六页汇报结构。")
        try:
            ppt_report = build_ppt_template_export(
                df,
                ppt_template_source,
                report_template_context,
            )
            st.download_button(
                "下载 PPT 汇报材料",
                data=ppt_report,
                file_name="data_insight_presentation.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                type="primary",
                key="report_ppt",
            )
        except Exception as exc:
            st.error(f"PPT 报告生成失败：{exc}")

    with report_tabs[3]:
        st.markdown("### 生成周报 / 月报 / 季报 / 年报")
        if not api_key:
            st.info("请先在侧边栏完成 AI 接入。")
        if not date_columns:
            st.info("未检测到时间字段，无法生成周期报告。")
        elif not eda_numeric_columns:
            st.info("未检测到可用指标字段，无法生成周期报告。")
        else:
            periodic_controls = st.columns(2)
            periodic_type = periodic_controls[0].selectbox(
                "报告周期",
                ["周报", "月报", "季报", "年报"],
                key="export_periodic_type",
            )
            periodic_date = periodic_controls[1].selectbox(
                "日期字段",
                date_columns,
                key="export_periodic_date",
            )
            periodic_metrics = st.multiselect(
                "指标字段",
                eda_numeric_columns,
                default=eda_numeric_columns[: min(3, len(eda_numeric_columns))],
                key="export_periodic_metrics",
            )
            if st.button(
                f"生成 {periodic_type}",
                disabled=not api_key or not periodic_metrics,
                type="primary",
                key="generate_periodic_report",
            ):
                try:
                    with st.spinner(f"AI 正在生成{periodic_type}..."):
                        st.session_state.ai_periodic_report = generate_ai_periodic_report(
                            df,
                            {"季报": "季度报告", "年报": "年度报告"}.get(periodic_type, periodic_type),
                            periodic_date,
                            periodic_metrics,
                            api_key=api_key,
                            model=ai_model,
                            base_url=ai_base_url,
                        )
                except Exception as exc:
                    st.error(f"AI 周期报告生成失败：{exc}")
            if st.session_state.get("ai_periodic_report"):
                st.markdown(st.session_state.ai_periodic_report)

    with report_tabs[4]:
        st.markdown("### 管理层汇报")
        st.caption("聚焦管理层摘要、核心 KPI、增长亮点、主要风险和行动建议。")
        if not api_key:
            st.info("请先在侧边栏完成 AI 接入，再生成管理层摘要。")
        if st.button(
            "生成管理层摘要",
            disabled=not api_key,
            type="primary",
            key="generate_executive_summary",
        ):
            try:
                with st.spinner("AI 正在生成管理层摘要..."):
                    st.session_state.ai_executive_summary = request_management_summary(
                        report_business_summary,
                        api_key,
                        ai_model,
                        ai_base_url,
                    )
            except Exception as exc:
                st.error(f"管理层摘要生成失败：{exc}")
        if st.session_state.get("ai_executive_summary"):
            st.markdown(st.session_state.ai_executive_summary)
        st.info("管理层汇报PPT为预览功能，当前生成文字版摘要与文字版PPT。")
        try:
            executive_ppt = export_executive_ppt(
                df,
                calculate_kpi(df, business_fields),
                st.session_state.get("ai_executive_summary") or report_ai_summary,
            )
            st.download_button(
                "导出管理层汇报PPT",
                data=executive_ppt,
                file_name="executive_briefing.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                type="primary",
                key="report_executive_ppt",
            )
        except Exception as exc:
            st.error(f"管理层汇报 PPT 生成失败：{exc}")
