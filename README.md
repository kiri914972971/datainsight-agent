# DataInsight Agent

DataInsight Agent 是一个面向数据分析师和非技术用户的 Streamlit 数据分析 MVP。上传 CSV、XLSX 或 XLS 文件后，可以自动查看数据概览、EDA、交互图表、执行常用清洗、运行规则式查询并导出 Word 报告。

## 项目结构

```text
data_insight_agent/
├── app.py                    # Streamlit 主页面
├── requirements.txt          # Python 依赖
├── README.md                 # 使用说明
├── src/
│   ├── data_loader.py        # CSV / Excel 读取
│   ├── type_detector.py      # 字段识别与日期解析
│   ├── eda.py                # EDA 统计
│   ├── data_quality.py       # 数据质量评分、异常字段与 ID 识别
│   ├── eda_ai_complete.py    # EDA 业务洞察、截断检测与自动续写
│   ├── visualizer.py         # Plotly 图表
│   ├── cleaner.py            # 数据清洗
│   ├── export_service.py     # CSV / XLSX / XLS 导出
│   ├── ai_connection.py      # AI 接口连接测试
│   ├── query_engine.py       # 规则式查询
│   └── report_generator.py   # Word 报告
└── outputs/                  # 可选的本地输出目录
```

## Windows 安装与运行

请先确认电脑已经安装 Python 3.11 或 3.12。Python 3.13 可能与部分数据分析包存在兼容问题。

```powershell
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

如果 `py -3.12` 不可用，安装 Python 后，在安装界面勾选 **Add Python to PATH**。

## 功能测试

1. 上传一个包含数值、类别和日期字段的 CSV 或 Excel。
2. 在“数据预览”检查字段类型是否正确。
3. 在“探索性分析”检查缺失值、数值统计、异常值和智能洞察。
4. 在“可视化”切换不同交互图表。
5. 从左侧执行清洗，并在“数据清洗”检查处理前后对比。
6. 在“数据清洗”将处理后的数据导出为 CSV、XLSX 或 XLS。所有处理只修改当前会话副本，不会覆盖原始文件。
7. 在“简单查询”选择字段并运行 Top N 查询。
8. 在“报告导出”下载并打开 Word 报告。

## AI 深度分析

在左侧“AI 接入”区域填写自己的 API Key、模型和 API 地址，然后在“探索性分析”中点击“生成 AI 深度分析”。API Key 仅保存在当前浏览器会话中，不会写入项目文件。

点击“测试 AI 连接”后，页面会明确显示接入成功或失败原因。默认使用 OpenAI Responses API，若服务不支持则自动尝试 OpenAI 兼容的 Chat Completions API，因此也可配置 DeepSeek 等兼容接口。未填写 API Key 时，应用仍会基于偏度、峰度、异常值和类别频率自动生成本地分析建议。

## 常见问题

- **无法激活虚拟环境**：先运行 `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`，再激活。
- **提示找不到 Python / py**：重新安装 Python，并勾选添加到 PATH；然后重启 VS Code。
- **Excel 读取失败**：确认已安装 `openpyxl` 和 `xlrd`，并检查文件是否损坏。
- **CSV 中文乱码**：程序会依次尝试 UTF-8、GB18030 和 Latin-1；仍失败时请用 Excel 将文件另存为 UTF-8 CSV。
- **日期未被识别**：建议字段名包含 `date`、`time`、`日期` 或 `时间`，并确保至少 80% 的非空值可解析。
- **端口被占用**：运行 `streamlit run app.py --server.port 8502`。
