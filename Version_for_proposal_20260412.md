[text](https://docs.google.com/document/d/1DpajxFHXzFpijxxkR3qxp9qAiaMfxhWC8sIBPrHJmKU/edit?usp=sharing)


snapshot at 16:19 20260412
Version for proposal
This project studies whether AI-related corporate disclosure is a form of economically meaningful soft information, and whether a transparent NLP-based framework can distinguish substantive AI disclosure from generic AI talk.
The central idea is that not all AI-related disclosure is equally informative. Some disclosures reflect genuine technological implementation, operational change, and firm transformation, while others may primarily represent broad rhetoric, symbolic positioning, or market hype.
More specifically, the project asks three questions:
RQ1. Can a transparent NLP-based framework identify AI-related disclosure in firms’ 10-K filings and distinguish substantive AI disclosure from generic AI statements?
RQ2. Is substantive AI disclosure more closely associated with firm characteristics consistent with technological transformation and operational implementation than generic AI talk?
看document_ai_intensity和company盈利能力的关系：
只要2025年的ai_intensity即可，我们需要2024-2025年的stock price growth
Ai_intensity作为continuous variable
substantive/generic作为dummy variable
→ 看如果两个公司一个是substantive，一个是generic，有相同的ai intensity，那么substantive的growth会比generic的growth高多少
Control variable?
RQ3. After controlling for conventional financial variables, does substantive AI disclosure provide incremental explanatory power for firm value and future fundamentals, and does this informational relevance become stronger in the post-ChatGPT / post-GenAI-boom period?
The original sample contains 50 company-year MD&A documents from 7 firms over 2018–2025. We first apply an AI keyword filter and retain only those MD&A documents with at least one AI-related keyword hit for further classification. As a result, the final classification dataset contains 13 company-year observations. Importantly, the 37 excluded observations are not labeled as non-AI-related disclosures; rather, they are excluded because they do not match the current AI keyword list.
At the document level, we construct a binary variable, SubstantiveDisclosure, equal to 1 if the MD&A is classified as substantive and 0 if classified as generic. We also use document_ai_intensity as a continuous measure of AI disclosure intensity.
In addition, we construct six dummy variables for substantive disclosure subcategories: product development, AI product/provider, pricing optimization, inventory management, operational efficiency, and AI risk disclosure. For documents with AI risk disclosure, we further classify risk-related content into six finer categories: regulatory risk, operational risk, competitive risk, cybersecurity risk, ethical risk, and third-party risk.
？:
ai_keyword_hit
substantive_disclosure
ai_disclosure_intensity
subcat_product_development
subcat_ai_product_provider
subcat_pricing_optimization
subcat_inventory_management
subcat_operational_efficiency
subcat_ai_risk_disclosure
risk_regulatory
risk_operational
risk_competitive
risk_cybersecurity
risk_ethical
risk_third_party

log⁡(Assets)：公司规模
ROA：盈利能力
Leverage：杠杆
SalesGrowth：成长性
R&D/Assets：研发强度
Capex/Assets：资本开支强度
Intangibles/Assets：无形资产强度
Industry FE
Year FE
Tobin’s Q


A组：Data Cleaning
不负责判断 generic/substantive，把原始 10-K 变成干净、可分析的 MD&A 句子级数据。
抽取 MD&A
从 10-K 里准确截取 Item 7（MD&A）
结束边界设在 Item 7A 或 Item 8
去掉目录里伪出现的标题，避免前后 section 混进去
清洗文本
去 HTML/XBRL tags
去页眉页脚、table 残片、导航字符串、乱码
统一小写、空格和换行
保留否定词、情态词、数字，不要过度清洗
句子切分
把 MD&A 切成 sentence-level
注意 10-K 长句、分号、broken lines，不能简单按句号切
去重和质量控制
去 exact duplicates
去 near duplicates
删除标题句、残句、太短句
可选：初筛 AI candidate
用 seed dictionary 标记包含 AI 相关词的句子，供 B组进一步分类
目标是高召回，不要求高精度
A组最终交付一个 sentence-level MD&A master file，至少包含：
cik / gvkey / ticker / company / filing_date / fiscal_year
sentence_id / sentence_order
sentence_raw / sentence_clean
mdna_total_word_count / mdna_total_sentence_count
ai_candidate_flag / ai_keyword_matched_terms
is_exact_duplicate / is_near_duplicate / keep_sentence_flag

在完成 MD&A 提取后，对原始文本进行清洗与标准化。清洗过程主要包括：
删除 HTML / XBRL tags
删除页眉页脚、表格残片、导航字符串
删除编码噪音与无意义特殊符号
统一多余空格、换行与格式断裂
剔除不构成完整句子的交叉引用碎片
在文本标准化过程中，采用 lowercase conversion 和 whitespace standardization，但不进行过度清洗。特别是：
保留否定词与情态词（如 may, could, expect, plan）
保留数字与百分比信息
不删除所有 stop words
不进行激进 stemming
这样做的原因是，后续 generic 与 substantive 的区分依赖于句子语义、实施状态、管理层语气与 firm-specific linkage，而不仅仅是关键词出现频率。
句子切分
在清洗后的 MD&A 文本基础上，将文本切分为 sentence-level observations。句子是本项目的主要分析单位，原因在于：
同一段落中往往同时包含 broad strategic language 和 concrete operational detail
若以段落为单位，generic 与 substantive 信息容易混合，造成分类噪音
句子级分析更适合后续精细分类与聚合
句子切分需要适应 10-K 的文本特征，包括长句、分号、括号、项目符号残留与 broken lines 等。不能简单按句号分割，而应结合规则化 tokenizer 与人工检查逻辑。
去重与质量控制
为了避免 boilerplate language 或格式重复导致披露强度被高估，在 sentence-level 数据构建阶段应加入以下质量控制：
去除 exact duplicate sentences
去除 near-duplicate sentences
删除标题句、残句和过短句
删除不构成完整语义单位的 observation
Data Cleaning 阶段输出
Data Cleaning 组的最终输出应为一个 sentence-level MD&A master file，其中每一行对应一个 firm-year MD&A 中的一句话，包含以下核心字段：
firm-year identifiers
cik
gvkey
ticker
company_name
filing_date
fiscal_year
accession_number
MD&A metadata
section_name
mdna_total_word_count
mdna_total_sentence_count
mdna_total_char_count
sentence-level fields
sentence_id
sentence_order
sentence_raw
sentence_clean
sentence_word_count
quality flags
is_exact_duplicate
is_near_duplicate
keep_sentence_flag
AI candidate support
ai_candidate_flag
ai_keyword_matched_terms




B组：NLP
在 A组给的 sentence-level 数据上做AI disclosure 分类，然后聚合成回归可用变量。
分成 4 类：
0 = not_meaningful_ai_mention
1 = generic_ai_disclosure
2 = substantive_ai_implementation
3 = substantive_ai_risk_governance
not meaningful AI mention
只是提到 AI 词
标题、法规名、broad list、顺带提 AI
没有真正披露内容
generic
提到 AI，但只是战略方向、趋势、机会、探索
没有具体 use case、deployment、业务对象、风险机制
substantive implementation
公司自己把 AI 用到产品、服务、流程、内部运营
有 deploy / integrate / launch / automate / build 之类动作
有 firm-specific use case
substantive risk/governance
公司自己实际使用 AI 后，披露 model review / testing / validation / governance
或具体 AI 风险机制，比如 AI-enabled cyber risk、model failure 等

不要把 final_disclosure_type 当主变量
文档里可能既有 generic 又有 substantive
后面做回归要用 continuous measures，不要只靠一个 final label
加上 not_meaningful_ai_mention
现在很多 broad mention 被算进了 disclosure，会把 measure 搞脏
把 substantive 拆成 implementation 和 risk/governance
两类经济含义不一样，后面回归也可以分别看
监管提到具体功能 ≠ substantive
比如提 underwriting / claims / marketing，如果只是说 regulator 关注这些领域，不算公司自己的 substantive AI use
做 sentence 去重
现在 sample 里有重复/近重复 summary，会虚高 hit counts

先用 seed lexicon 筛 AI candidate sentences
写 annotation codebook
人工标 300–500 句做 calibration
扩大到 1000–2000 句做训练集
先做 rule-based baseline
再做 supervised classifier
TF-IDF + logistic / SVM
SBERT / FinBERT 之类 contextual model
最后聚合成 firm-year regression-ready 数据 

3.1 基本思想
本项目的核心不是识别“公司是否提到 AI”，而是判断公司在 MD&A 中的 AI 披露是：
仅仅使用了 broad, symbolic, or rhetorical AI language
还是披露了 firm-specific、economically meaningful 的 AI implementation 或 risk/governance 信息
因此，文本分类不能停留在关键词计数，而应在句子层面区分不同类型的 AI 语言。
3.2 AI candidate sentence extraction
首先，利用透明、可扩展的 AI seed lexicon 对 MD&A 句子进行初筛，提取所有可能与 AI 相关的 candidate sentences。AI seed lexicon 可包括：
artificial intelligence
AI
machine learning
generative AI
large language model
neural network
predictive analytics
intelligent automation
chatbot
computer vision
该步骤的目标是 high recall，即尽可能保留潜在 AI 相关句子，以便后续分类阶段进行更精细的判断。
3.3 分类体系
在 AI candidate sentences 中，建议采用如下四分类体系：
0. not meaningful AI mention
句子包含 AI 术语，但不构成经济上有意义的 AI disclosure。常见情形包括：
broad risk list 中顺带提到 AI
纯标题或交叉引用
仅提法规名称或技术概念而无公司层面内容
1. generic AI disclosure
句子提到 AI，但仅停留在：
broad technological trend
strategic priority
future opportunity
general exploration
high-level vision
其特点是：
没有具体业务 use case
没有实施动作
没有 firm-specific operational linkage
没有 AI-specific mechanism
2. substantive AI implementation
句子描述公司自身 AI 在产品、服务、运营流程或内部管理中的具体应用。常见特征包括：
deploy / implement / integrate / launch / build / embed
customer service, fraud detection, underwriting, recommendation, automation 等具体业务对象
AI-related product or platform
AI investment, R&D, internal tool deployment
3. substantive AI risk/governance
句子描述公司自身 AI 使用所带来的具体风险机制、控制流程或治理安排。常见特征包括：
model review, testing, validation
AI governance framework
AI-specific compliance or oversight
AI-enabled operational risk
AI-related cybersecurity mechanism
3.4 试样基础上的修改建议
基于目前已有试样，NLP 组应重点做以下调整：
第一，不再将 final_disclosure_type 作为主要文档级变量
当前试样中的 final_disclosure_type 过于粗糙。一个 MD&A 中往往既可能包含 generic disclosure，也可能包含 substantive implementation 或 risk/governance disclosure。将整个文档压缩成一个单一标签，会造成严重信息损失。因此，final_disclosure_type 最多可作为辅助描述，不应作为主要回归解释变量。
第二，新增 not_meaningful_ai_mention
目前试样中有不少 observation 只是 broad mention 或法规标题式 AI 引用，但仍被计入 AI-related hits。这会污染 AI disclosure 的分母，降低变量的经济含义。因此，需要把“碰到 AI 词但无实质披露”的句子单独剥离。
第三，将 substantive disclosure 拆分为 implementation 与 risk/governance
当前试样中的 substantive hits 混合了产品与流程应用，以及 model risk / governance / cyber risk 等不同类型内容。二者的经济含义和回归解释显著不同，因此需要拆分。
第四，避免将“行业/监管层面关于 AI 的讨论”误判为 firm-specific substantive disclosure
例如，若句子仅说明监管机构关注 AI 在 underwriting, marketing, claims 等场景中的使用，而未披露公司自身的 AI 应用或治理机制，则不应仅凭出现具体业务词而归类为 substantive。
第五，对近重复 observation 做去重
当前试样中出现多个措辞相似但本质重复的 summary，说明原始句子或摘要层面存在重复计数风险。这会导致 substantive hit counts 被高估，因此在聚合前必须基于原始 sentence-level 数据完成去重。
identifiers
cik
gvkey
ticker
company_name
filing_date
fiscal_year
MD&A size controls
mdna_total_word_count
mdna_total_sentence_count
mdna_total_char_count
AI disclosure counts
n_ai_candidate_sentences
n_not_meaningful_ai_mentions
n_generic_ai_sentences
n_substantive_ai_implementation_sentences
n_substantive_ai_risk_governance_sentences
n_substantive_ai_total_sentences
Intensity variables
ai_candidate_intensity
generic_ai_intensity
substantive_ai_implementation_intensity
substantive_ai_risk_governance_intensity
substantive_ai_total_intensity
Share variables
generic_ai_share
substantive_ai_share
substantive_impl_share
substantive_risk_share
Net measures
net_substantive_minus_generic
impl_minus_generic
risk_minus_generic
Dummies
any_generic_ai_dummy
any_substantive_ai_dummy
any_substantive_ai_implementation_dummy
any_substantive_ai_risk_governance_dummy
QC variables
n_dropped_duplicate_sentences
avg_classification_confidence


gvkey
cik
tic
conm
datadate
fyear
sic
naics
ff12_ind
ff48_ind

at
sale
ni
dlc
dltt
xrd
capx
intan
gdwl
che
ppent
ceq
prcc_f
csho
oancf
xsga
oibdp

mve
log_assets
roa
roa_oibdp
leverage
sales_growth
rd_assets
capex_assets
intangibles_assets
cash_assets
ppe_assets
goodwill_assets
ocf_assets
asset_turnover
profit_margin
tobins_q
mtb

filing_date
mdna_text_length
mdna_sentence_count
ai_sentence_count
ai_paragraph_count
ai_dummy
ai_intensity
ai_wordshare
generic_ai_dummy
substantive_ai_dummy
generic_ai_count
substantive_ai_count
generic_ai_share
substantive_ai_share
ai_usecase_dummy
ai_function_dummy
ai_product_dummy
ai_process_dummy
ai_investment_dummy
ai_risk_dummy
ai_efficiency_dummy
ai_innovation_dummy
ai_customer_dummy
ai_internal_ops_dummy

post_chatgpt
transition_2022



变量名
定义
公式 / 构造方式
数据来源
备注
gvkey
Compustat 公司唯一代码
原始字段
Compustat
主键之一
cik
SEC 公司代码
原始字段
SEC / Compustat
用来连 10-K
tic
股票代码
原始字段
Compustat
检查用
conm
公司名称
原始字段
Compustat
检查用
datadate
财务报表日期
原始字段
Compustat
年度 ending date
fyear
财年
原始字段
Compustat
回归主时间维度
sic
SIC 行业代码
原始字段
Compustat
可做 industry FE
naics
NAICS 行业代码
原始字段
Compustat
可替代 SIC
ff12_ind
Fama-French 12 行业分类
由 SIC 映射
自建
推荐保留
ff48_ind
Fama-French 48 行业分类
由 SIC 映射
自建
更细行业 FE


变量名
定义
公式 / 构造方式
数据来源
备注
at
总资产
原始字段
Compustat
size 基础变量
act
流动资产
原始字段
Compustat
liquidity 类变量可用
lct
流动负债
原始字段
Compustat
同上
lt
总负债
原始字段
Compustat
可替代 debt measures
che
现金及短期投资
原始字段
Compustat
cash holding
ppent
固定资产净额
原始字段
Compustat
tangible intensity
intan
无形资产
原始字段
Compustat
intangible intensity










ceq
普通股权益
原始字段
Compustat
book equity
seq
股东权益
原始字段
Compustat
可备用
dlc
短期债务
原始字段
Compustat
leverage
dltt
长期债务
原始字段
Compustat
leverage
sale
销售收入
原始字段
Compustat
growth 和 turnover
revt
总收入
原始字段
Compustat
有时与 sale 不同










xsga
SG&A 费用
原始字段
Compustat
管理/销售费用强度
xrd
研发费用
原始字段
Compustat
很关键




























































xint
利息支出
原始字段
Compustat
财务压力可用
capx
资本开支
原始字段
Compustat
你们很可能会用






























prcc_f
财年末股价
原始字段
Compustat / CRSP
market value
csho
流通股数
原始字段
Compustat / CRSP
market value


变量名
定义
公式 / 构造方式
数据来源
备注
log_assets
公司规模
log(at)
自建
你现在一定会用
roa
盈利能力
ni / at
自建
baseline 推荐
roa_oibdp
经营口径盈利能力
oibdp / at
自建
robustness 候选
leverage
杠杆
(dlc + dltt) / at
自建
推荐优先
sales_growth
销售增长率
(sale_t - sale_t-1) / sale_t-1
自建
需要 lag
log_sales_growth
对数销售增长
log(sale_t) - log(sale_t-1)
自建
robustness 可用
rd_assets
研发强度
xrd / at
自建
很重要
capex_assets
资本开支强度
capx / at
自建
很重要
intangibles_assets
无形资产强度
intan / at
自建
刚问到的
cash_assets
现金持有强度
che / at
自建
建议保留
ppe_assets
固定资产强度
ppent / at
自建
可反映传统资产结构










sga_assets
SG&A 强度
xsga / at
自建
管理/营销强度










profit_margin
利润率
ni / sale
自建
建议保留
asset_turnover
资产周转率
sale / at
自建
运营效率候选
current_ratio
流动比率
act / lct
自建
稳健性控制项
book_leverage_alt
备选杠杆
lt / at
自建
robustness
loss_dummy
是否亏损
1(ni < 0)
自建
很有用
rd_missing_dummy
R&D 是否缺失
1(xrd missing)
自建
建议一定加




变量名
定义
公式 / 构造方式
数据来源
备注
mve
股权市值
prcc_f * csho
自建
Tobin's Q 必备
tobins_q
Tobin's Q 近似值
(mve + at - ceq) / at
自建
baseline DV 候选
mtb
市净率
mve / ceq
自建
robustness 常用
ln_mve
市值对数
log(mve)
自建
备选 market outcome
future_roa_1
下一年 ROA
lead(roa,1)
自建
future performance
future_roa_2
下两年 ROA
lead(roa,2)
自建
persistence
future_sales_growth_1
下一年销售增长
lead(sales_growth,1)
自建
可选
future_ocf_assets_1
下一年经营现金流强度
lead(ocf_assets,1)
自建
可选


变量名
定义
公式 / 构造方式
数据来源
备注
filing_date
10-K 提交日期
原始字段
SEC EDGAR
用于对齐年份
filing_year
提交年份
从 filing_date 提取
自建
核对用
mdna_word_count
MD&A 总词数
分词后计数
10-K 文本
必留
mdna_sentence_count
MD&A 总句数
句子切分后计数
10-K 文本
必留
ai_sentence_count
AI 相关句数
AI 句子数
NLP 输出
必留
ai_paragraph_count
AI 相关段落数
AI 段落数
NLP 输出
建议保留
ai_dummy
是否提到 AI
1(ai_sentence_count>0)
NLP 输出
最基础
ai_intensity
AI 披露强度
ai_sentence_count / mdna_sentence_count
自建
推荐主指标之一
ai_wordshare
AI 词汇占比
AI词数 / MD&A总词数
自建
可作 robustness
generic_ai_dummy
是否有 generic AI 披露
规则/模型输出
NLP 输出
核心
substantive_ai_dummy
是否有 substantive AI 披露
规则/模型输出
NLP 输出
核心
generic_ai_count
generic AI 句数
汇总句子级分类
NLP 输出
核心
substantive_ai_count
substantive AI 句数
汇总句子级分类
NLP 输出
核心
generic_ai_share
generic AI 占比
generic_ai_count / mdna_sentence_count
自建
推荐
substantive_ai_share
substantive AI 占比
substantive_ai_count / mdna_sentence_count
自建
推荐
substantive_cond_share
实质性 AI 占 AI 披露比重
substantive_ai_count / (generic_ai_count + substantive_ai_count)
自建
很值得加
ai_usecase_dummy
是否提具体 use case
人工规则/模型输出
NLP 输出
机制分析
ai_function_dummy
是否提具体 business function
同上
NLP 输出
机制分析
ai_product_dummy
是否提 AI 产品/服务
同上
NLP 输出
机制分析
ai_process_dummy
是否提 AI 流程改造
同上
NLP 输出
机制分析
ai_investment_dummy
是否提 AI 投资/部署
同上
NLP 输出
机制分析
ai_risk_dummy
是否提 AI 风险/治理
同上
NLP 输出
机制分析
ai_efficiency_dummy
是否提降本增效
同上
NLP 输出
机制分析
ai_innovation_dummy
是否提创新/新业务
同上
NLP 输出
机制分析
ai_customer_dummy
是否提客户侧应用
同上
NLP 输出
机制分析
ai_internal_ops_dummy
是否提内部运营应用
同上
NLP 输出
机制分析
ai_specificity_score
AI 披露具体性得分
规则/模型打分
NLP 输出
可连续化
ai_actionability_score
可执行性得分
规则/模型打分
NLP 输出
可连续化
ai_context_score
语境丰富度得分
规则/模型打分
NLP 输出
可连续化
manual_check_flag
是否经过人工核验
0/1
自建
建议保留
manual_label_conflict
机器与人工是否冲突
0/1
自建
质量控制


变量名
定义
公式 / 构造方式
数据来源
备注
industry_fe
行业固定效应标记
由 SIC/FF12/FF48 生成
自建
回归时用
year_fe
年固定效应标记
由 fyear 生成
自建
回归时用
firm_fe
公司固定效应标记
由 gvkey 生成
自建
回归时用
post_chatgpt
后 ChatGPT 时期虚拟变量
1(fyear >= 2023)
自建
核心
transition_2022
2022 过渡年
1(fyear == 2022)
自建
可删或单独控制
sample_main
主样本标记
比如 2018–2021 与 2023–2025
自建
很有用
sp500_dummy
是否在目标样本中
0/1
自建
如果你们只做某样本
industry_target_dummy
是否属于目标行业
0/1
自建
如果你们按行业选样本


















Regression:

GenericAIIntensity：公司有没有在“讲 AI”
SubstantiveAIIntensity：公司有没有在“实质性讲 AI”
SubstantiveAIShare：在已经讲 AI 的公司里，实质内容占比多高
NetSubstantiveMinusGeneric：净信息含量更偏 substantive 还是 generic

Model Group A – RQ2
Valuation relevance
（1）Valuationit​=α+β1​AIIntensityit​+γ′Xit​+μi​+λt​+εit​
ValuationitValuation_{it}
Stock price
Tobin’s Q
Market-to-book（Robutness)
AIIntensityit​：AI-related meaningful disclosure intensity
Xit​：control variable
μi​：firm fixed effects & Industry FE
λt：year fixed effects

（2）Valuationit​=α+β1​GenericAIIntensityit​+β2​SubstantiveAIIntensityit​+γ′Xit​+μi​+λt​+εit​
Hypothesis H0:
β1>0, β2>0
β2-β1>0
Market value  substantive AI disclosure，Not generic AI talk
（3）Valuationit​=α+β1​SubstantiveAIShareit​+γ′Xit​+μi​+λt​+εit​
（4）Valuationit​=α+β1​NetSubstantiveMinusGenericit​+γ′Xit​+μi​+λt​+εit​ ——Robutsness
Control Variables: 
firm size（log assets / log market cap）
profitability（ROA / operating margin）
leverage
R&D intensity
capital expenditure intensity
sales growth
intangible intensity
year FE
industry FE 

Model Group B – RQ3
Post-ChatGPT heterogeneity
（1）Valuationit=α+β1GenericAIIntensityit+β2SubstantiveAIIntensityit+β3(GenericAIIntensityit×Postt)+β4(SubstantiveAIIntensityit×Postt)+γ′Xit+μi+λt+εit
Postt=1: post-ChatGPT / post-GenAI boom period，if fiscal year≥2023
在 GenAI 爆发后，市场对 generic 与 substantive AI disclosure 的定价权重是否发生了变化？
H0:
β4>0
β4-β3>0​ (restriction test
substantive AI disclosure in post period has better valuation relevance
generic AI talk 不一定同步增强，甚至可能被市场视为 hype

（2）Valuationit​=α+β1​SubstantiveAIShareit​+β2​(SubstantiveAIShareit​×Postt​)+γ′Xit​+μi​+λt​+εit​
Model Group C – RQ3
Future outcomes / informativeness
（1）FutureSalesGrowthi,t+1​=α+β1​GenericAIIntensityit​+β2​SubstantiveAIIntensityit​+γ′Xit​+μi​+λt​+εi,t+1​
（2）FutureROAi,t+1=α+β1GenericAIIntensityit+β2SubstantiveAIIntensityit+γ′Xit+μi+λt+εi,t+1

Model D(extension) (1)Returni,t+1​=α+β1​GenericAIIntensityit​+β2​SubstantiveAIIntensityit​+γ′Xit​+λt​+εi,t+1​
如果 generic 更强对应短期正收益，可能更像 hype
如果 substantive 更稳定，可能更像信息


(2)Returni,t+h​=α+β1​GenericAIIntensityit​+β2​SubstantiveAIIntensityit​+γ′Xit​+λt​+εi,t+h​h=1,2,…,12
generic AI talk 会不会先被市场追捧，后面反转？
substantive AI disclosure 是否更持久、更少 reversal？






















