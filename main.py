import os
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
# 引入内置的搜索工具，让 Agent 拥有联网能力
from crewai_tools import SerperDevTool 

# ==========================================
# 0. 环境与配置初始化
# ==========================================
# 配置 LLM
os.environ["OPENAI_API_KEY"] = "your-openai-api-key"
# 配置 Google Serper API (用于联网搜索，需在 serper.dev 注册获取)
os.environ["SERPER_API_KEY"] = "your-serper-api-key"

llm_fast = ChatOpenAI(model="gpt-4-turbo", temperature=0.2)
llm_reasoning = ChatOpenAI(model="gpt-4-turbo", temperature=0.5)

# 初始化工具
search_tool = SerperDevTool()

# ==========================================
# 1. 定义多 Agent (赋能工具与长链推理)
# ==========================================

# Agent 1: 拥有联网能力的数据挖掘专家
researcher = Agent(
    role='高级全网数据挖掘工程师',
    goal='使用搜索工具，精准挖掘关于指定主题的最前沿、最硬核的商业与技术数据。',
    backstory='你精通高级搜索指令和信息过滤，绝不提供模糊的信息。你会主动交叉验证信息源的可靠性。',
    verbose=True,
    allow_delegation=False,
    tools=[search_tool], # 赋予联网搜索能力
    llm=llm_fast
)

# Agent 2: 专精于长链推理的商业分析大脑
analyst = Agent(
    role='首席战略与商业分析师',
    goal='对原始数据进行深度长链推理（Chain of Thought），挖掘隐藏的商业模式和未来爆发点。',
    backstory='''你是一个坚持第一性原理的思考者。在分析时，你必须遵循以下推理链：
    1. 表象梳理：当前市场发生了什么？
    2. 深度归因：为什么会发生？背后的技术突破或政策驱动是什么？
    3. 玩家博弈：主要竞争对手在做什么？各自的护城河是什么？
    4. 终局推演：未来3-5年市场的最终格局是什么？''',
    verbose=True,
    allow_delegation=True, # 允许要求 researcher 重新搜索缺失的数据
    llm=llm_reasoning
)

# Agent 3: 研报撰写者
writer = Agent(
    role='麦肯锡级别研报主笔',
    goal='将复杂的分析推演过程，转化为金字塔原理结构的商业报告。',
    backstory='你擅长化繁为简，用极具说服力的语言、清晰的标题层级（Markdown）向高管汇报。',
    verbose=True,
    allow_delegation=False,
    llm=llm_fast
)

# Agent 4: 幻觉与逻辑审查官 (自纠错闭环)
reviewer = Agent(
    role='严苛的事实核查与逻辑审查官',
    goal='确保研报没有任何事实错误（幻觉）、逻辑断层或主观臆断。',
    backstory='你是最后的守门员。如果报告中存在没有数据支撑的结论，或者前后逻辑自相矛盾，你必须指出并让 Writer 甚至 Analyst 重新工作。',
    verbose=True,
    allow_delegation=True, # 核心：赋予打回重做的权力
    llm=llm_fast
)

# ==========================================
# 2. 定义任务工作流 (Task Workflow)
# ==========================================

topic = "2026年具身智能（Embodied AI）机器人领域的商业化落地进展与中美竞争格局"

task1_research = Task(
    description=f'使用搜索工具，查找【{topic}】相关的最新研报、新闻、顶级公司的财报或融资记录。务必提取具体的数字（如融资金额、量产时间表、参数规模）。',
    expected_output='包含丰富数据点和来源链接的原始信息汇总文档。',
    agent=researcher
)

task2_analysis = Task(
    description='严格按照你的系统设定的“四步推理链”（表象、归因、博弈、推演）对搜集到的数据进行深度剖析。找出中美两国在该领域的核心差异点。',
    expected_output='结构化的深度分析提纲，必须包含明确的逻辑推导过程，而不仅仅是事实的罗列。',
    agent=analyst
)

task3_writing = Task(
    description='基于分析提纲撰写 2500 字以上的万字长文级别的深度研报。要求使用 Markdown 格式，包含：1. 核心观点摘要 2. 行业宏观背景 3. 深度逻辑剖析 4. 中美竞争态势分析 5. 投资与战略建议。',
    expected_output='排版精美、逻辑严密的 Markdown 格式商业报告初稿。',
    agent=writer
)

task4_review = Task(
    description='对初稿进行逐段审查。1. 检查数据是否有出处；2. 检查推导结论是否合理。输出最终的修订版。如果有重大缺陷，记录错误原因并打回。',
    expected_output='经过事实核查后的最终完美定稿。',
    agent=reviewer
)

# ==========================================
# 3. 组装与执行 (Process Execution)
# ==========================================

# 采用层级化或顺序化流程
enterprise_crew = Crew(
    agents=[researcher, analyst, writer, reviewer],
    tasks=[task1_research, task2_analysis, task3_writing, task4_review],
    process=Process.sequential, 
    memory=True, # 开启记忆功能，让 Agent 之间的上下文传递更顺畅
    verbose=True 
)

if __name__ == "__main__":
    print(f"🚀 [Enterprise System] 开始执行高难度多 Agent 并发推理任务：{topic}")
    final_report = enterprise_crew.kickoff()
    
    print("\n\n" + "="*50)
    print("✅ [成功] 最终生成通过审核的商业深度报告：")
    print("="*50 + "\n")
    print(final_report)
