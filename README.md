# 🏢 Enterprise Multi-Agent Research System

基于 `CrewAI` 和大模型构建的企业级自动化商业调研与报告生成系统。

## ✨ 核心特性
* **多智能体协作**：Researcher (检索), Analyst (推理), Writer (撰写), Reviewer (审核) 闭环协作。
* **长链推理 (CoT)**：内置分析师 Agent 采用四步推理模型，深度归因商业逻辑。
* **反幻觉机制**：引入 Reviewer Agent 进行红蓝对抗，实现事实核查与自主纠错打回。
* **外部工具集成**：支持 `SerperDevTool` 实时全网信息抓取。

## 🚀 快速启动
```bash
# 克隆项目
git clone [https://github.com/您的用户名/Enterprise-Agent-Research-System.git](https://github.com/您的用户名/Enterprise-Agent-Research-System.git)
cd Enterprise-Agent-Research-System

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
export OPENAI_API_KEY="your-api-key"

# 启动引擎
python main.py
