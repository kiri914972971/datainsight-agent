from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.eda_ai_complete import (
    build_analysis_payload,
    request_ai_insights,
)
from src.ai_connection import test_ai_connection
from src.business_analysis import (
    business_metric_options,
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
from src.export_service import EXPORT_OPTIONS, export_dataframe
from src.data_quality import (
    apply_missing_value_fix,
    data_quality_summary,
    detect_identifier_columns,
    drop_duplicate_rows,
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
from src.query_engine import run_query
from src.report_generator import generate_report
from src.type_detector import detect_and_parse_types, type_summary
from src.visualizer import box_plot, correlation_heatmap, histogram


st.set_page_config(page_title="DataInsight Agent", page_icon="📊", layout="wide")
st.markdown(
    """
    <style>
    html, body { font-size: 16px; }
    .stApp p,
    .stApp label,
    .stApp li,
    .stApp button,
    .stApp input,
    .stApp textarea { font-size: 16px !important; }
    [data-testid="stSidebar"][aria-expanded="true"] {
        min-width: 310px;
        max-width: 310px;
    }
    [data-testid="stSidebar"][aria-expanded="false"] {
        min-width: 0 !important;
        max-width: 0 !important;
        width: 0 !important;
    }
    [data-testid="stMainBlockContainer"] {
        width: 100%;
        max-width: 1600px;
        margin-left: auto !important;
        margin-right: auto !important;
    }
    [data-testid="stSidebar"] h2 { font-size: 20px !important; }
    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] p { font-size: 16px !important; }
    [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] div { font-size: 30px !important; }
    button[data-baseweb="tab"] p { font-size: 18px !important; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("DataInsight Agent")
st.caption("上传数据，自动完成探索、业务分析、清洗、查询与报告导出。")


def reset_for_file(uploaded_file) -> None:
    file_key = f"{uploaded_file.name}-{uploaded_file.size}"
    if st.session_state.get("file_key") != file_key:
        dataframe = load_data(uploaded_file)
        dataframe, detected = detect_and_parse_types(dataframe)
        st.session_state.file_key = file_key
        st.session_state.file_name = uploaded_file.name
        st.session_state.original_df = dataframe
        st.session_state.current_df = dataframe.copy()
        st.session_state.working_df = dataframe.copy()
        st.session_state.field_types = detected
        st.session_state.last_comparison = None
        st.session_state.ai_eda_result = None
        st.session_state.ai_exploration_result = None
        st.session_state.ai_business_report = None
        st.session_state.business_query_plan = None
        st.session_state.business_query_result = None
        st.session_state.business_query_explanation = None
        st.session_state.last_outlier_comparison = None
        st.session_state.last_outlier_before_df = None
        st.session_state.last_outlier_after_df = None
        st.session_state.last_outlier_column = None
        st.session_state.outlier_treatment_message = None
        st.session_state.duplicate_comparison = None


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


with st.sidebar:
    st.header("1. 上传文件")
    uploaded_file = st.file_uploader("拖拽或选择 CSV / XLSX / XLS", type=["csv", "xlsx", "xls"])
    st.divider()
    st.header("2. AI 接入")
    st.caption("API Key 仅保存在当前浏览器会话中，不会写入文件。")
    api_key = st.text_input("API Key", type="password", placeholder="sk-...")
    ai_model = st.text_input("模型", value="gpt-5.4-mini")
    ai_base_url = st.text_input("API 地址", value="https://api.openai.com/v1")
    ai_config_signature = hash((api_key, ai_model, ai_base_url))
    if st.button("测试 AI 连接", disabled=not api_key, use_container_width=True):
        try:
            with st.spinner("正在测试 AI 接口..."):
                reply = test_ai_connection(api_key, ai_model, ai_base_url)
            st.session_state.ai_connection_status = {
                "signature": ai_config_signature,
                "success": True,
                "message": f"接入成功。模型返回：{reply[:80]}",
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

if uploaded_file is None:
    st.info("请先在左侧上传一个数据文件。")
    st.markdown(
        """
        **支持的能力**
        - 自动识别数值、类别、日期与文本字段
        - 自动生成 EDA 表格与交互图表
        - 一键清洗、规则式查询和 Word 报告
        """
    )
    st.stop()

try:
    reset_for_file(uploaded_file)
except Exception as exc:
    st.error(f"文件读取失败：{exc}")
    st.stop()

if "current_df" not in st.session_state:
    st.session_state.current_df = st.session_state.working_df.copy()
df = st.session_state.current_df
df, field_types = detect_and_parse_types(df)
st.session_state.current_df = df
st.session_state.working_df = df
st.session_state.field_types = field_types
numeric_columns = field_types["numeric"]
category_columns = field_types["categorical"]
date_columns = field_types["datetime"]
invalid_columns = suspicious_columns(df)
identifier_columns = detect_identifier_columns(df, invalid_columns)
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

tabs = st.tabs(["数据预览", "数据质量", "探索性分析", "业务分析", "数据清洗", "简单查询", "报告导出"])

with tabs[0]:
    st.subheader("数据预览")
    st.dataframe(df.head(100), use_container_width=True)
    st.subheader("字段信息")
    st.dataframe(type_summary(df, field_types), use_container_width=True, hide_index=True)
    cols = st.columns(4)
    cols[0].write(f"**数值字段：** {len(numeric_columns)}")
    cols[1].write(f"**类别字段：** {len(category_columns)}")
    cols[2].write(f"**日期字段：** {len(date_columns)}")
    cols[3].write(f"**文本字段：** {len(field_types['text'])}")

with tabs[1]:
    st.subheader("数据质量总览")
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

    st.caption("请前往「数据清洗」tab 执行缺失值删除、填充或字段处理。")

    st.subheader("重复值诊断")
    duplicate_summary = summarize_duplicates(df)
    duplicate_cards = st.columns(2)
    duplicate_cards[0].metric("重复行数量", f"{duplicate_summary['duplicate_count']:,}")
    duplicate_cards[1].metric("重复行占比", f"{duplicate_summary['duplicate_ratio']:.2f}%")
    if duplicate_summary["preview"].empty:
        st.info("当前未检测到重复行。")
    else:
        st.dataframe(duplicate_summary["preview"].head(100), use_container_width=True)
    st.caption("请前往「数据清洗」tab 删除重复行。")

    st.subheader("ID 字段识别")
    st.caption("ID字段通常只用于定位记录，不适合做均值、偏度、异常值检测和相关性分析。")
    identifier_summary = summarize_identifier_columns(df, identifier_columns)
    if identifier_summary.empty:
        st.info("当前未识别到疑似 ID 字段。")
    else:
        st.dataframe(identifier_summary, use_container_width=True, hide_index=True)

    if invalid_columns:
        st.warning(f"检测到疑似无效或近乎空字段：{', '.join(map(str, invalid_columns))}。建议删除。")
        st.caption("请先确认字段业务含义，再前往「数据清洗」tab 处理。")

    st.subheader("异常值诊断")
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

            st.info("异常值不一定是错误数据。请查看明细并结合业务判断，再前往「数据清洗」tab 执行具体处理。")
    st.subheader("数据修复建议")
    repair_suggestions = generate_data_repair_suggestions(df, invalid_columns, identifier_columns, eda_outliers)
    if repair_suggestions.empty:
        st.success("当前未发现需要优先修复的数据质量问题。")
    else:
        st.dataframe(repair_suggestions, use_container_width=True, hide_index=True)
        st.caption("数据质量页仅提供诊断与建议。请前往「数据清洗」tab 执行具体处理。")

with tabs[2]:
    st.caption("数据质量问题请前往「数据质量」tab 处理。疑似 ID 字段已从探索分析中排除。")
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

with tabs[3]:
    business_tabs = st.tabs(["报表仪表盘", "维度对比分析", "业务问答"])
    business_fields = identify_business_fields(
        df,
        date_columns,
        category_columns,
        numeric_columns,
        identifier_columns,
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

with tabs[4]:
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

with tabs[5]:
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

with tabs[6]:
    st.subheader("导出 Word 分析报告")
    st.write("报告包含数据概览、缺失值、重复值、数值统计、偏度峰度、异常值和类别洞察。")
    try:
        report = generate_report(df, st.session_state.file_name, field_types)
        st.download_button(
            "下载 .docx 报告",
            data=report,
            file_name="DataInsight_Report.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
        )
    except Exception as exc:
        st.error(f"报告生成失败：{exc}")
