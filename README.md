# Biomedical NLP — 药物关系抽取 Pipeline

基于前司生产系统架构的重构版本，将内部 LLM 框架替换为 LangChain，用于从生物医学文献中自动抽取**药物–疾病**关联关系。

> 当前已迁移并可运行的 pipeline：`drug_disease`（药物–疾病）

---

## 技术栈

| 类别 | 工具 |
|---|---|
| 语言 | Python 3.11+ |
| LLM 调用 | LangChain + DeepSeek（兼容 OpenAI 接口，可替换任意 provider） |
| 数据格式 | JSON / JSONL（增量写入） |
| 工具库 | myutils（内部封装：日志、IO、参数解析） |

---

## Pipeline 架构

```
原始文献数据 (PubMed)
        │
        ▼
step01  载入原始数据
        │
        ▼
step02a [LLM] 识别疾病名称缩写，还原全称
step02b        应用还原结果，更新字段
        │
        ▼
step03a [LLM] 验证疾病实体是否为真实疾病
        │
        ▼
step04a [LLM] 识别药物名称缩写，还原全称
step04b        应用还原结果，更新字段
        │
        ▼
step05a [LLM] 验证药物实体是否为真实药物
        │
        ▼
step06a [LLM] 检测同一文献中的重复疾病实体
step06b        应用去重映射，合并重复实体
        │
        ▼
step07a [LLM] 检测联合疗法（多药物治疗同一疾病）
step07b        应用联合疗法结果，重构关系记录
        │
        ▼
step11  [LLM] 评估药物–疾病关系的新颖性
        │
        ▼
step12  [LLM] 分类关系类型（治疗 / 副作用 / 关联等）
        │
        ▼
结构化药物–疾病关系数据 (JSONL)
```

共 **8 次 LLM 调用**，每步均支持断点续跑与结果去重。

---

## 设计亮点

### 1. 统一 LLM 客户端（`biomedical_nlp/llm_client.py`）
- 封装 LangChain `BaseChatModel`，与具体 provider 解耦
- 指数退避重试（最多 5 次，间隔 5 → 10 → 20 → 40 → 80 秒）
- 自动提取 reasoning model 的链式思考内容（DeepSeek-reasoner / OpenAI o 系列）
- 统一清理 LLM 返回的 JSON markdown 代码块

### 2. 增量处理 + 断点续跑
- 每步输出写入 JSONL，按 batch 刷盘，避免中途中断丢失数据
- 启动时从已有输出文件重建已完成集合，跳过已处理记录
- 捕获 `KeyboardInterrupt`，确保优雅退出前完成最后一次写盘

### 3. 跨 pipeline 实体缓存预热
- 实体验证步骤（step02a、step03a）启动时优先读取 `drug_target` pipeline 的历史结果作为缓存
- 相同实体在不同 pipeline 中复用 LLM 结果，显著减少重复调用
- 当前仅drug_disease可用，跨pipeline缓存在多pipeline场景下生效

### 4. 运行时数据集切换
```bash
# 使用默认数据集（global_config.py 中配置）
python run_pipeline.py drug_disease

# 运行时指定数据集，无需修改配置文件
python run_pipeline.py drug_disease --dataset prod

# 强制重跑所有步骤
python run_pipeline.py drug_disease --dataset test --force_overwrite
```

---

## 项目结构

```
biomedical-nlp/
├── biomedical_nlp/
│   ├── global_config.py          # 全局配置：路径、API Key、数据集名称
│   ├── llm_client.py             # 统一 LLM 调用封装
│   └── drug_disease/
│       ├── config.py             # Pipeline 级路径配置
│       ├── prompt/               # 各步骤 LLM 提示词（Markdown）
│       ├── step01_prepare_pipeline_input.py
│       ├── step02a_llm1_disease_abbr.py
│       ├── step02b_update_disease_name.py
│       ├── step03a_llm2_validate_disease.py
│       ├── step04a_llm3_chemical_abbr.py
│       ├── step04b_update_chemical_name.py
│       ├── step05a_llm4_validate_chemical.py
│       ├── step06a_llm5_duplicate_disease.py
│       ├── step06b_remove_duplicate_disease.py
│       ├── step07a_llm8_combination_therapy.py
│       ├── step07b_apply_combination_therapy.py
│       ├── step11_llm6_novelty.py
│       └── step12_llm7_relation_types.py
├── run_pipeline.py               # Pipeline 统一入口
└── .env                          # API Key（不纳入版本控制）
```

---

## 快速开始

**1. 安装依赖**
```bash
pip install langchain-openai langchain-core python-dotenv
pip install -e path/to/myutils
# myutils 为作者私有工具库，如需运行请联系作者或参考 requirements.txt 替换为标准库实现
```

**2. 配置 API Key**

在 `biomedical_nlp/.env` 中添加：
```
DEEPSEEK_API_KEY=your_api_key_here
```

**3. 运行 pipeline**
```bash
python run_pipeline.py drug_disease
```

单步调试：
```bash
python biomedical_nlp/drug_disease/step02a_llm1_disease_abbr.py --dataset test --max_items 10
```

---

## 说明

本项目为基于前司生产环境 pipeline 的个人重构版本：
- 原系统依赖公司内部 LLM 调用框架及私有数据库，无法开源
- 本版本将 LLM 层替换为 LangChain + DeepSeek，数据层使用脱敏后的公开数据集结构
- 核心业务逻辑（实体验证、去重、关系分类等）与生产版本保持一致

*[English version →](README_EN.md)*
