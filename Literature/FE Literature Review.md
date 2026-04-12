1. Cao, Yang, Miao Liu, Jiaping Qiu, and Ran Zhao. 2024\. “Information in Disclosing Emerging Technologies: Evidence from AI Disclosure.” SSRN. [https://doi.org/10.2139/ssrn.4987085](https://doi.org/10.2139/ssrn.4987085)  
   1. NLP 词汇  
      1. 早期（2010-2013）主要是 "business intelligence", "data mining"  
      2. 后期（2018+）变成 "artificial intelligence", "machine learning"  
      3. 2023年出现 "large language model"

   2. How to use NLP  
      1. 对每个关键词，提取前后各400词（共800词的窗口），喂给 **ChatGPT-4o**让它做两件事：  
         1. 判断是否真的在讲AI  
         2. 分类AI用途  
            1. AI revenue  
               1. Product Development  
               2. Pricing Optimization  
               3. AI Product Provider  
            2. AI cost  
               1. AI Product Provider  
               2. Operational Efficiency

   3. **Question and corresponding regression**  
      1. **Question 1: 什么因素会决定公司下一年是否披露AI**  
         （因为员工是t时刻雇佣的，但是10-K在t+1 publish）  
         1. Model: Logit (dependent variable: 0/1)  
      2. AI Disclosurei, t+1​=βAI Employee Sharei, t+λControls+Dj​+Dt​+ϵ  
         1. AI Disclosurei, t+1​  
            dummy variable, 公司在10-K里有没有披露AI相关内容  
            2. AI Employee Sharei, t  
               公司里有AI相关技能的员工占总员工的比例  
               (从简历中提取，Babina et al. 2024的数据)  
            3. Controls  
               公司层面的特征  
               log(Assets)  
               ROA  
               Cash  
               Leverage  
               Net PPE  
               MtB （市值账面比--成长性）  
               Log (Firm Age)  
            4. Dj​：行业固定效应  
            5. Dt​：年份固定效应  
      3. AI披露能预测未来业绩吗  
         Model:   
         ![][image1]  
         Key: 控制了AI Employee Share，看披露是否有增量信息  
      4. AI风险披露能预测股票风险吗  
         ![][image2]

   4. 主要发现  
      披露AI的公司，**次年**销售增长+16%、员工增长+14%、研发支出+15%；披露AI风险的公司股票尾部风险更高，监管、竞争、伦理风险影响最大。

2. Basnet, Anup, Maxim Elias, Galla Salganik-Shoshan, Thomas Walker, and Yunfei Zhao. 2025\. “Analyzing the Market’s Reaction to AI Narratives in Corporate Filings.” *International Review of Financial Analysis* 105 (September): 104378\. [https://doi.org/10.1016/j.irfa.2025.104378](https://doi.org/10.1016/j.irfa.2025.104378).   
   1. NLP（其实是没有用NLP）  
      这篇分析市场能不能分辨"真正的AI战略"和"蹭热点的AI buzzword"时使用了人工手动分类：两个研究者独立标注，有分歧找第三人裁定  
      1. 手动把Ai披露分成三类  
         1. Actionable  
            有具体实施计划："我们用ML优化供应链，已部署在X系统"  
         2. Speculative  
            模糊，没有具体计划："我们正在探索AI的可能性"  
         3. Irrelevant  
            和公司核心业务无关：只是顺带提了一下AI  
   2. Model  
      1. Panel Fixed Effects  
         ![][image3]  
         在排除了公司本身特征、宏观环境、和其他财务指标之后，第一次披露AI关键词，有没有让公司市值相对提高？  
         这篇用的是变化量作为dependent variable  
         1. Tobin's Q= 市值 / 账面价值，衡量投资者对公司的估值  
         2. Keyward：dummy variable  
            	今年第一次在10-K里提到AI关键词 → \=1  
            	去年就提过了，或者今年也没提 → \=0  
         3. γfirm：fixed effect for firm  
         4. γyear：fixed effect for year

         结论：Actionable的披露让Tobin's Q提升约5%，Speculative和Irrelevant没有效果。

         

      2. Local Projections DiD（LP-DiD）  
         和普通DID的差异：普通DiD只看一个时间点，LP-DiD把效果在多个时间点上分别估计  
         1. 以每个公司第一次披露AI为事件  
         2. 对比披露公司 vs 同期没有披露的公司的Tobin's Q轨迹  
         3. Model:   
            ![][image4]  
            With h=1, 2, 3  
            看效果是立刻出现还是慢慢累积

3. Wang, Tawei, and Ju-Chun Yen. 2023\. “Does AI Bring Value to Firms? Value Relevance of AI Disclosures.” *Die Unternehmung: Swiss Journal of Business Research and Practice* 77 (2): 134–161. [https://doi.org/10.5771/0042-059X-2023-2-134](https://doi.org/10.5771/0042-059X-2023-2-134)  
   1. NLP  
      1. 第一层：关键词匹配  
         **目的**：判断一篇10-K文件是否包含AI相关内容  
         **方法**：在SeekEdgar数据库中检索包含"artificial intelligen\*"（\* 表示通配符，涵盖intelligence、intelligent等变体）的文件  
         **产生的变量**：  
         1. `AI_it`：二元变量，有AI关键词=1，否则=0  
         2. `AIFreq_it`：AI关键词出现次数的自然对数，衡量披露程度深浅

         **局限性**：这种方法非常粗糙，只能判断"有没有"，无法理解"说了什么"，因此需要第二层分析

      2. 第二层：LDA主题模型  
         1. 任务1：对AI风险因素（Item 1A）做主题分析  
            **目的**：分析企业在**风险因素章节**中披露的AI相关风险属于哪类主题  
            （投资者不怕公司承认有风险，怕的是公司**不知道**自己有风险。风险因素披露本质上是管理层能力和诚信度的信号，所以披露AI风险反而能提升公司价值。）  
            步骤一：文本提取  
            步骤二：文本预处理  
            步骤三：确定主题数量  
            步骤四：运行LDA模型  
            步骤五：主题标注  
            步骤六：生成哑变量  
         2. 任务2：对全文AI披露上下文做主题分析（补充测试）  
            **目的**：分析**10-K全文**中AI关键词出现时的语境主题  
      3. 其他possible NLP  
         1. 词典法（Dictionary Approach）  
         2. 词嵌入（Word2Vec, GloVe）  
         3. 预训练语言模型（BERT, GPT等）  
         4. 情感分析  
         5. 命名实体识别（NER）

   2. Hypothesis and results  
      1. Hypothesis 1: 有AI披露的公司股价与无AI披露的公司不同  
         AI披露与股价显著正相关（系数15.239，p\<0.01），说明投资者**正面评价**企业的AI实施。

      2. Hypothesis 2: 有AI风险因素披露的公司市值不同  
         结果同样显著为正（系数13.846，p\<0.05）。进一步用LDA主题分析将AI风险因素分为三类：  
         1. 新技术市场竞争（Topic1）：不显著  
         2. 业务运营（Topic2）：弱显著（p\<0.10）  
         3. 监管与安全（Topic3）：强显著（系数35.338，p\<0.01）

         说明投资者最看重企业对数据隐私和合规风险的意识。

      3. AI风险因素披露的价值相关性受IT治理水平调节  
         当企业拥有更好的董事会/高管层IT治理时，业务运营类AI风险披露的价值相关性显著提升（交互项系数37.192，p\<0.01）。这意味着IT治理能力是投资者评估AI风险管理能力的重要信号。

4. Lauren Cohen (Patent)  
   1. 专利流氓（Patent Trolls）  
      Patent Trolls: Evidence from Targeted Firms  
      1. **研究问题：**非实施主体（Non-Practicing Entities，NPEs）即"专利流氓"究竟是在保护创新，还是在寄生式勒索？  
      2. **理论模型**：  
         1. 理论模型：NPE诉讼在理想状态下可以减少侵权、支持小发明人；  
         2. 实践检验：当NPE擅长提起**无实质根据的诉讼**时，企业被迫支付高额辩护成本，从而挤出本可创造社会价值的创新。  
      3. **结论**：被NPE起诉的企业，事后R\&D支出显著下降，说明专利流氓确实在压制创新活动。  
   2. 专利猎人（Patent Hunters）  
      Patent Hunters  
      1. **研究问题：**分析1976至2020年间USPTO授予的数百万件专利，研究发现部分专利只有在很长时间之后才变得突出（即"晚期绽放专利"）。在这些晚期绽放的有影响力专利中，存在一群关键玩家——"专利猎人"——他们能持续识别并开发这些专利。  
      2. **研究发现：**专利猎人对这些被忽视专利的采用，与销售增长提升6.4%（t=3.02）、Tobin’s Q提升2.2%（t=3.91）以及新产品供应增加2.2%（t=2.97）显著相关。  
   3. ESG与绿色专利  
      The ESG-Innovation Disconnect: Evidence from Green Patenting  
      1. **研究发现（反直觉）**：石油、天然气和能源生产企业——即ESG评分较低、且经常被ESG基金明确排除在外的企业——实际上是美国绿色专利格局中的关键创新者。这些能源生产商产出了更多且质量显著更高的绿色创新。在许多绿色技术领域，他们是难以替代的先行者，并持续产出其他替代能源企业赖以构建的基础性创新和商业化成果。  
      2. **政策含义**：ESG排除策略可能产生适得其反的效果——将资本从真正在做绿色创新的能源企业中抽走，反而可能减缓绿色技术进步。这一结论对ESG投资理论构成严重挑战。

关于patent的文章使用NLP较少。  
![][image5]

# 总体概念划分总结

# Cao, Yang, Miao Liu, Jiaping Qiu, and Ran Zhao. 2024\. “Information in Disclosing Emerging Technologies: Evidence from AI Disclosure.” SSRN. [https://doi.org/10.2139/ssrn.4987085](https://doi.org/10.2139/ssrn.4987085)

## **一、文章里隐含的 substantive disclosure**

更接近 **substantive disclosure** 的，是那些满足以下特征的 AI 披露：

· **不只是出现 AI 关键词**，而是经上下文审核后，被 GPT 确认为 **“Related to AI”**。

· **明确说明 AI 用在什么地方**，并能归入具体应用类别。文章把应用披露分成五类：

1\. Product Development 

2\. Pricing Optimization 

3\. AI Product Provider 

4\. Inventory Management 

5\. Operational Efficiency。 

· **风险披露也要具体**。在 Item 1A 中，只有能明确落入下列风险类型的，才算有实质内容：regulatory, operational, competitive, cybersecurity, ethical, third-party risks。 

· **必须是文本中“明确写出来”的内容**，而不是模型推断。在 prompt 中明确要求 GPT：**不要推断，只报告explicitly mentioned 的类别。** 

文章里的 substantive disclosure 可以理解为：

**经过 GPT 语义确认，且能明确映射到具体 AI 应用场景或具体 AI 风险场景的披露。**

## **二、文章里隐含的 generic disclosure**

更接近 **generic disclosure** 的，是那些：

· **虽然命中了 AI 关键词**，但上下文不足以支持“真实 AI 使用”判断的文本；这类会被 GPT 判成 **“Not Related to AI”**，因此不会进入最终 AI disclosure 样本。 

· **即使提到 AI，也没有明确说明用途、功能、产品、流程或风险渠道**，因此难以被归入五类应用或六类风险中的任一类。这个判断是根据文章分类逻辑作出的归纳。

· 更像是**泛泛提及 AI 概念、趋势或战略方向**，而不是具体业务披露。文章没有单独给这类文本命名为 generic disclosure，但它们实际上被排除在“有效 AI 披露”之外。 

文章里的 generic disclosure 可以理解为：

**只是在表面上提到 AI，但没有足够具体的信息让 GPT确认其为明确的 AI 应用或风险披露。**

## **三、文章具体是怎么划分的**

### **1\. 先用关键词找“候选 AI 文本”**

作者先在 10-K 中用 AI 关键词表做检索，定位可能和 AI 有关的段落。

### **2\. 再截取上下文，而不是只看关键词**

每发现一个关键词，就提取其前后约 **800 词窗口**，作为 GPT 的输入文本。

### **3\. GPT 先判断是不是“真的在讲 AI”**

**· （如果要用到GPT，需要的prompt都可以在这篇文章的附录里找到）**

GPT 的第一步任务是判断该段文本是：

· Related to AI 

· Not Related to AI  
并给出概率分数。

### **4\. 若 Related to AI，再做“具体场景分类”**

· 在 Item 1 / Item 7 中，分到五类具体应用。 

· 在 Item 1A 中，分到六类具体风险。 

### **5\. 分类只依据“明确表述”**

作者要求 GPT 不能脑补或推断，只能按文本中明确出现的内容分类。

***Yao, Kai and Xiao, Yu and Huang, Rong and Zhao, Jingyi, AI Disclosure & the Cost of Debt (March 08, 2026). Available at SSRN: [https://ssrn.com/abstract=6373498](https://ssrn.com/abstract=6373498) or [http://dx.doi.org/10.2139/ssrn.6373498](https://dx.doi.org/10.2139/ssrn.6373498)***  
 

**这篇论文并没有直接使用“substantive AI disclosure” 和 “generic AI disclosure”。**  
作者真正使用的概念是：

· **capability-backed AI disclosure**：有可观测 AI 能力支撑的 AI 披露 

· **residual AI salience**：无法被企业真实 AI 能力解释的剩余 AI 强调 

作者认为，并不是所有 AI 披露都同样有信息含量；有些披露背后有真实 AI 投入与能力支撑，有些则可能只是企业在战略性地强调 AI，但并没有相应的底层能力。

# **一、两种概念分别是怎么定义的**

## **1\. capability-backed AI disclosure 是什么**

作者用 **observable inputs, most notably AI-skilled human capital, to reflect underlying AI capacity**，也就是用企业**可观测的 AI 技能型人力资本**来代理企业真实的 AI 能力。

因此，所谓 **capability-backed AI disclosure**，本质上就是：

企业在 conference call 里谈到的 AI 内容中，那部分能够被其可观测 AI 能力解释的部分。

也就是说，这不是“企业说了多少 AI”，而是“企业所说的 AI，有多少和它真实的 AI 能力相匹配”。

这部分在概念上非常接近**substantive AI disclosure**，因为它不只是 talk，而是有能力基础支撑的 disclosure。

## **2\. residual AI salience 是什么**

作者把剩余那一部分定义为 **AI salience**。  
他们说，这部分是 **the component of AI disclosure that cannot be explained by the firm’s observable AI capability**，即企业 AI 披露中**不能被真实 AI 能力解释的部分**。

作者进一步把它解释为 **abnormal emphasis**，也就是“异常强调”“额外强调”，并明确说这可以理解成 **over- or under-claiming**。

· 如果一家企业谈了很多 AI，但它实际可观察到的 AI 人才、AI岗位、AI能力并不强，那么这些“多出来的 AI 话语”就会落入 **residual AI salience** 

· 这部分在概念上就很接近 **generic AI disclosure**、AI hype、AI slogan-like talk 

但是严谨来说，作者没有直接说 residual AI salience \= generic AI disclosure。  
作者真正说的是：这部分是**不能被能力支撑、因而较难验证的 AI 强调**。

# **二、他们如何从数据上量化地区分这两类**

这是最核心的部分。作者的做法可以拆成三步。

## **第一步：先构造总体的 AI disclosure**

在前面的主分析里，作者先构造一个总的 **AI\_DISCLOSURE** 指标。  
这个指标来自 earnings conference calls 的文本分析，具体是基于 **word2vec** 训练出的 AI 相关词典，再去衡量 presentation section 中 AI 相关词语的占比。变量定义表中明确写道：

**AI\_DISCLOSURE \= The proportion of AI words in the trained dictionary in the presentation session**。

也就是说，总体 AI disclosure 先被定义为一个**文本强度指标**：  
企业在电话会里，AI-related words 占比有多高。

这一层还没有区分“实质”还是“空泛”，它只是先找出企业“谈 AI 的强度”。

## **第二步：用外部数据构造 AI capability**

然后作者需要一个独立于文本的话语之外的“真实 AI 能力”度量。

他们使用的是 **Babina et al. (2024)** 的公开数据来衡量 **AI-skilled human capital**，并把它作为企业 AI capability 的代理变量。具体地，他们定义：

**AI\_CAPABILITY \= log(1 \+ the number of AI-related jobs held by the firm as of the end of the forecast quarter)**。

也就是说，作者不是靠文本再定义一个“能力感”，而是引入了一个**外部、可验证的、真实投入导向的数据源**：

· 企业有多少 AI-related jobs 

· 企业有多少 AI-skilled human capital 

这个设计非常关键，因为它把“真实 AI 能力”从“企业自己怎么说”中剥离出来了。

## **第三步：用回归把 AI disclosure 分解成两部分**

这是整套方法最关键的一步。

作者设定了下面这个回归：

其中：

· 左边是企业在电话会上**说了多少 AI** 

· 右边是企业**真实拥有多少 AI 能力** 

· 剩下的误差项 ε，就是 **AI\_SALIENCE** 

这一步的经济含义可以这样理解：

### **1）回归中被 AI\_CAPABILITY 解释掉的那部分**

### **企业之所以谈这么多 AI，是因为它确实有更多 AI 岗位、AI人才、AI能力。**

### **所以这部分是“有能力支撑的 AI 披露”。**

### **2）回归后剩下的残差部分**

### **在控制了真实 AI 能力之后，这家企业依然“额外地”在谈 AI。**

### **这部分就是作者所谓的 residual AI salience，也就是无法被真实能力解释的 AI 强调。**

# **三、这个区分的本质是什么**

这套做法的本质不是做一个文本分类器去判断句子“像不像口号”，而是做一个**经济意义上的分解**：

 

所以，作者区分两类概念的标准不是：

· 有没有提 use case 

· 有没有提部门

· 有没有提 outcome 

而是：

· 这部分 AI talk 能不能被企业真实 AI 能力解释？ 

能解释的，更接近“实质性、可信的 AI disclosure”；  
不能解释的，更接近“泛化式、额外渲染式的 AI talk”。

这是一个非常漂亮的识别思路，因为它避免了单纯靠主观阅读文本来判断“是不是 substantive”。

# **四、作者如何验证这个区分是有意义的**

作者做完这个分解后，把主回归中的 AI\_DISCLOSURE 替换成两部分：

· AI\_CAPABILITY 

· AI\_SALIENCE 

结果发现：

· **AI\_CAPABILITY 的系数显著为正** 

· **AI\_SALIENCE 的系数不显著** 

作者据此得出结论：  
债券投资者主要定价的是 **the component of AI disclosure that is backed by observable AI capability**，而不是那些**not supported by measurable AI capabilities** 的 AI-related talk。

这其实就是在用市场结果反过来验证他们的概念划分：

· 真正有能力支撑的 AI disclosure，会被债券市场当回事 

· 单纯的 AI salience、AI emphasis、AI rhetoric，不会被同样认真地定价 

所以，这种区分不是停留在概念层面，而是经过了实证结果的支持。

哈哈这篇其实和概念区分关系不大

# Rech, Frederik and Meng, Fanchen and Musa, Hussam and Tuo, Siele Jean, AI Disclosure Density and Financial Distress Prediction: Evidence from Chinese Listed Manufacturers. Available at SSRN: [https://ssrn.com/abstract=5967426](https://ssrn.com/abstract=5967426) or [http://dx.doi.org/10.2139/ssrn.5967426](https://dx.doi.org/10.2139/ssrn.5967426)哈哈这篇其实和概念区分关系不大

 

# **一、作者如何理解 AI wash**

作者没有把 AI wash 做成一个单独变量，但在理论部分讲得很明确：

**AI-related disclosures 既可能代表企业真实的能力建设，也可能只是企业在财务压力下进行 impression management。** 作者原文直接说，AI-related disclosures may indicate **genuine capability building** or **impression management under financial pressure (i.e., “AI washing”)**。

所以，在这篇文章里，**AI wash 的含义**大致是：

· 企业在披露中大量强调 AI 

· 但这种强调未必对应真实 AI adoption 或真实 AI capability 

· 尤其当企业面临财务压力时，AI 叙事可能被当作一种“讲故事”或“包装未来”的方式 

这也是作者为什么没有提出一个方向明确的因果假说。因为 AI disclosure 既可能是好信号，也可能是坏信号：  
如果它代表真实数字化升级，那可能降低困境风险；  
如果它更像 AI washing，那反而可能与更高风险相联系。

# **二、作者如何处理 AI wash**

## **1）先承认它存在，但不直接做文本分类**

第一步，不是去手工标注哪些句子是 wash，哪些是 substantive。  
他们**没有直接构造一个 “AI wash dummy”**，也没有做 substantive/generic 的文本分类。相反，他们采取的是一种更保守的做法：

先把 AI disclosure 量化成连续的 **AI level / AI density** 指标，再看这些指标在预测财务困境时呈现出什么样的非线性和异质性模式。

对 AI wash 的处理方式不是“先定义、再分类”，而是：

· 在概念上承认 AI wash 的可能性 

· 在实证上观察“高密度 AI 披露”是否有时反而和更高风险联系在一起 

## **2）通过“density”而不是原始词频，降低虚假热词堆砌的干扰**

作者不用单纯的 AI term counts，而是大量使用 **AI density**。  
他们明确说，之所以要把 AI mentions 除以报告字数，是为了：

· 让不同篇幅的报告可以比较

· 避免 AI 指标只是被 overall verbosity 机械驱动 

· 减少“写得很长、重复很多次 AI 词”的表面效应 

这个设计其实对 AI wash 很关键。如果一家公司只是反复堆砌 AI 热词，原始词频可能会虚高；而用 density 至少能部分控制这种“靠写得长、提得多”制造出来的表面热度。

## **3）进一步聚焦 narrative text，减少格式性和表格性噪音**

作者还专门区分了：

· **AI density full** 

· **AI density ChEn** 

· **AI density full (MD\&A)** 

· **AI density ChEn (MD\&A)** 

其中 **AI density ChEn** 和 **AI density ChEn (MD\&A)** 去掉了表格和财务报表材料，只保留中英文 narrative text。作者明确说，这种做法可以：

· 更好捕捉 **managerial emphasis** 

· 减少 non-narrative repetition 的噪音 

这一步和 AI wash 也直接相关。因为如果企业只是通过模板化、表格化、重复标签式方式把 AI 词嵌进去，narrative-only density 会比 full-text density 更不容易被这种机械性的堆词污染。

所以，作者虽然没有直接识别 AI wash，但他们在变量构造上其实做了两层“降噪”：

· 用 density 控制篇幅和冗长度 

· 用 narrative-only text 控制表格和格式化重复 

## **4）通过 SHAP 结果事后识别 AI wash 的可能模式**

作者对 AI wash 最直接的实证处理，来自 SHAP 分析的解释。

他们发现：

· **very low AI disclosure density** 往往对应更高的 predicted distress 

· **moderate AI density** 往往对应更低的 distress risk 

· 但在 **2022 和 2023 年**，**very high AI density ChEn (MD\&A)** 反而更常出现在提高 distress risk 的一侧 

原因：这可能是因为 **financially pressured firms emphasize AI more**。

在作者看来，**过高、过密、尤其集中在 MD\&A narrative 中的 AI 强调**，在某些年份里可能不是“企业真的更强”，而是“企业更想讲 AI 故事”，这正是 AI wash 的典型表现。

因此，这篇文章对 AI wash 的识别逻辑不是前置分类，而是后置解释：

· 如果 AI density 适中，可能更接近真实 adoption signal 

· 如果 AI density 尤其是 MD\&A narrative density 高得异常，反而可能反映 AI washing motive 

# Blades, Richard and Bilinski, Pawel and Kraft, Arthur, Analysts' Response to 'AI Washing' in Earnings Conference Calls (February 26, 2026). Available at SSRN: [https://ssrn.com/abstract=6359598](https://ssrn.com/abstract=6359598) or [http://dx.doi.org/10.2139/ssrn.6359598](https://dx.doi.org/10.2139/ssrn.6359598)

 

## **1\. 两种Disclosure的定义**

这篇论文虽然不用 **substantive AI disclosure / generic AI disclosure** 这两个术语，但实际上区分的是：

### **（1）实质性 AI 披露**

对应作者的 **Existing firms**。  
这类披露具有以下特征：

· 提供 **具体的 AI 产品或服务** 

· 提供 **可衡量的 AI use cases** 

· 提到 **已建立的 AI 项目/公司的并购** 

· 展示 **清晰的运营层面 AI track record** 

也就是说，这类披露不是单纯“谈 AI”，而是有**具体内容、具体应用、具体证据**。

### **（2）投机性 / AI washing 披露**

对应作者的 **Speculative firms**。  
这类披露具有以下特征：

· 缺乏 **significant commitment** 

· 缺乏 **meaningful track record** 

· 主要是 **模糊的未来计划** 

· 只是提到 **AI 人才或经验**，但没有具体实施方案

· 充满 **aspirational statements without evidence** 

**说了很多 AI，但没有实质证据支持。** 

## **2\. 两种披露如何区分**

作者的核心思路是看企业的 **AI talk** 和 **AI walk** 是否一致。

· **AI talk**：企业在 conference call 里怎么谈 AI，内容是否 speculative 

· **AI walk**：企业是否真的有可观察的 AI 投资与活动 

如果企业：

· 披露内容本身很 speculative

· 实际上没有 observable AI investment 

那么作者就认为这属于 **AI washing**。

## **3\. 实际中的量化区分方法**

作者分两步量化：

### **第一步：量化“talk”**

作者把 management 的 AI disclosure 提取出来，交给 **ChatGPT** 按定义进行分类。提示词中明确要求区分：

· **Speculative (1)**：模糊未来计划、缺乏 track record、没有具体证据 

· **Existing (0)**：有具体 AI 产品、服务、use case 或 operational track record 

为了减少随机性，作者让 ChatGPT **独立判断 5 次**。  
如果 5 次中至少 **4 次判为 speculative**，则记为：

· **Speculative Disclosure Indicator (SDI) \= 1** 

否则：

· **SDI \= 0** 

### **第二步：量化“walk”**

作者用 **Babina et al. (2024)** 的 firm-level AI investment measure，具体是：

· 企业 **AI-related employees** 的数量

并按 AI investment 水平把企业分成三组（terciles）。  
最低一组代表 **AI investment 很弱**。

### **最终分类**

作者将企业定义为 **Speculative firm** 的条件是：

· **SDI \= 1** 

· 且企业处于 **最低 AI investment tercile** 

用公式表达就是：

 

否则归为 **Existing firm**。

# Moon, Katie and Suh, Paula and Zhou, Guanqun, Described Patents and Knowledge Diffusion between Firms (November 24, 2025). Available at SSRN: [https://ssrn.com/abstract=5807362](https://ssrn.com/abstract=5807362) or [http://dx.doi.org/10.2139/ssrn.5807362](https://dx.doi.org/10.2139/ssrn.5807362)

(是老师推荐的其中一个作者，主要是方法可以借鉴我觉得）  
 

# **一、研究问题**

这篇论文的研究问题是：

**专利研究中广泛使用的 front-page patent citations，是否真正反映了企业之间的知识流动？如果不够准确，能否用专利正文中“被明确描述的专利”（described patents / in-text citations）来更好地衡量知识扩散与知识获取意图？** 

l 传统 front-page citations 可能受到专利律师、审查员、法律责任和专利诉讼策略的影响，因此会混入很多“策略性引用”噪音，未必能准确表示技术知识真正是如何从一个企业流向另一个企业的。相比之下，专利正文中的 in-text citations 更可能是发明人在叙述技术演化和依赖关系时主动写出来的，因此更接近真实知识流。

l 更进一步，作者想证明：如果 in-text citations 真的是更好的知识流指标，那么它们应该更能预测**引用企业后来去雇佣被引专利的发明人**。因为如果一家企业真的依赖另一家企业的关键知识，它就更可能进一步通过招聘发明人来获取这类知识。

# **二、研究方法**

## **1）核心识别框架**

作者把专利引用分成两类：

· **front-page citations**：出现在专利首页参考文献中的专利引用

· **in-text citations / described patents**：出现在专利正文描述部分、并被明确提及和讨论的专利引用

然后比较这两类引用：

· 哪一种更少受法律策略影响

· 哪一种更能体现真正的技术相关性

· 哪一种更能预测 inventor hiring，从而更好反映知识流动 

## **2）如何识别 in-text citations**

作者用 PatentsView 的专利长文本数据，针对 1976–2021 年的 USPTO utility patents，解析约 **799 万份专利文本**。他们先通过 “No.” / “Nos.” 等专利引用前缀过滤段落，再总结出 **42 种常见正则表达式模式**，去识别正文中提到的patent number、application number 或 publication number，并用 crosswalk 把它们统一映射到最终 patent number。最终构造出 citing patent – cited patent 的 in-text citation 数据集。

## **3）如何理解“被描述”的原因**

这是这篇文章最有方法论价值的部分。作者并不满足于只抓到“正文提到了哪个专利”，而是进一步分析**为什么提到它**。

他们先让 GPT-4 总结 patent writer 在正文中提及其他专利的可能原因，然后归纳为三类：

· **Novelty and Advancement Over Existing Technologies**  
强调新发明相对于已有技术的独特性和进步

· **Building Upon and Evolving Existing Technology**  
说明新发明如何建立在已有技术基础之上，体现技术演进

· **Legal and Procedural Context**  
与法律合规、程序性引用、避免侵权相关

接着，作者让 GPT-4 对约 **5 万条** in-text citation 上下文进行分类，并把结果作为训练样本，使用 **Bayes Classifier** 去分类剩余约 **900 万条** textual mentions。结果显示，平均概率高达 **0.93** 的 in-text citations 属于第二类，即 **Building Upon and Evolving Existing Technology**，说明绝大多数正文提及专利都是为了说明当前发明如何建立在既有技术上。图 2 也直观显示第二类占压倒性多数。 

## **4）回归与验证**

作者之后做了几类回归验证：

· 检验诉讼经历是否影响企业未来做更多 front-page citations 或 in-text citations 

· 检验 in-text citations 是否更集中在地理更近、技术更近、时间更近的专利对之间 

· 检验 in-text citations 是否比 front-page citations 更能预测 inventor hiring 

· 检验 trade secret protection（IDD）是否只会削弱 in-text citation 预测到的 inventor mobility，而不会削弱 front-page citation 的预测能力 

# **三、数据来源**

这篇论文的数据来源主要有四类：

## **1）USPTO / PatentsView 专利文本数据：包括 published patent applications（2001 起）和 granted patents（1976 起）的长文本，作者最终聚焦 1976–2021 年的 utility patents。**

## **2）Compustat 公司数据：用于 firm-level financial characteristics。**

## **3）Audit Analytics 诉讼数据：用于 patent litigation 分析。**

## **4）其他匹配与补充数据**

包括：

· inventor mobility / hiring 数据 

· Sanati (2025) 的 IDD 数据 

· Kogan et al. (2017) patent value 

· Hoberg and Phillips (2014) product market fluidity 

· Doc2Vec / CPC class 构造的技术相似度等 

最终 firm-to-firm citation pair 样本有约 **5380 万对**；其中 14% 是 in-text citations，46% 的 in-text citations 同时也出现在 front-page。

# **四、研究结论**

## **1）in-text citations 比 front-page citations 更少受法律策略干扰**

l 图一：front-page citations 的平均数量在样本期内指数式上升，尤其 2000 年代中后期后加速；而 in-text citations 只是轻微上升。同时，front-page cited 与 citing patents 的技术接近度持续下降，而 in-text citation 的技术接近度一直更高且更稳定。 

l 表二：企业过去作为被告经历 patent litigation 后，下一年会显著增加 front-page citations，但不会显著增加 in-text citations。说明 front-page citations 更受法律防御策略影响，而 in-text citations 相对“干净”。 

## **2）in-text citations 更能反映真正的技术相关性**

l 表三：被 in-text cited 的专利通常与 citing patent：

· 地理距离更近

· 技术相似度更高

· 年代更接近

· patent value 更高 

· tech classes 更多 

这些特征都符合“真实知识扩散”的直觉。

## **3）in-text citations 更能预测 inventor hiring**

l 表四显示，过去三年中被某 firm 更多 in-text cited 的 inventor，明显更可能被该 firm 雇佣。这个效应的经济量级大约是 front-page citation 的 **7 倍**。

## **4）带正向语气的 in-text described patents 更可能对应后续招聘**

l 表七显示，如果 citing patent 在描述 cited patent 时使用更正面的语气，那么对应 inventor 将来被 citing firm 雇佣的概率更高。 

l 这说明不仅“有没有被描述”有信息，**怎么被描述**也有信息。

# **五、它如何划分 “substantive” 和 “generic”——最重要的说明**

## **这篇论文不是 AI disclosure 论文，但是它的思路和我们的问题高度相关，因为它实际上做了一种内容层面的“实质 vs 非实质”区分，只不过对象不是 AI disclosure，而是专利引用。**

### **它区分的不是两种 AI disclosure，而是两种“被提及”的知识关系：**

#### **（1）更“实质”的 textual mention**

l 对应文中的 **Building Upon and Evolving Existing Technology**。  
这类文本提及表示 citing patent 真正建立在 cited patent 的技术基础上，体现真实知识流动。图二显示，这类原因的平均概率约为 **0.93**，远高于另外两类。

#### **（2）更“非实质”或“程序性”的 mention**

· **Legal and Procedural Context** 

· 部分 **Novelty and Advancement** 类型提及

尤其前者，本质上更像程序性、法律性引用，而不是真正的知识吸收或技术依赖。

# **六、它实际中的量化方法**

这篇文章提供了一套很强的方法模板：

## **1）先用文本识别 mention**

l 先抓出所有 in-text citations（就是先识别所有 AI-related sentences / paragraphs）

## **2）再用 LLM 归纳“提及的功能类型”**

l 作者先用 GPT-4 总结 possible reasons，再对 5 万条样本人工/LLM 标注，最后训练 **Bayes Classifier** 去扩展到大样本。

对应到我们这里可以改成：

· use case / deployment / investment / outcome 

· legal/compliance / buzzword / generic vision / aspirational talk 

## **3）再验证哪一类更有经济含义**

l 作者不是停在文本分类，而是拿 inventor hiring、IDD、proximity 等外部结果来验证哪类 mention 真正对应知识流。

l 对应到AI这里，就可以验证：

· 哪类 AI disclosure 更对应 AI hiring / AI patents / AI capex / firm outcomes 

· 哪类只是 generic AI talk / AI washing 

 

# ***How to Disclose? Strategic AI Disclosure in Crowdfunding*** 本文把 AI disclosure 拆成两层：

· **substantive signals**：披露中关于 AI 实际参与程度的事实性信息 

· **rhetorical signals**：披露语言的表达方式，包括 explicitness、authenticity、emotional tone 

这篇文章是在研究：

l **同样是 AI disclosure，什么样的“实质内容”与“表达方式”会让投资者反应更差或更好。** 

# **一、研究问题**

这篇论文的核心问题有两个：

### **1）AI disclosure 本身会不会影响众筹表现？**

作者利用 Kickstarter 在 2023 年 8 月推出的**强制 AI disclosure 政策**，研究当项目必须公开说明是否以及如何使用AI 时，众筹结果会发生什么变化。

### **2）不同的 AI disclosure 策略会不会带来不同后果？**

作者特别关注两类披露策略：

· **substantive signals**：AI 实际参与程度有多高 

· **rhetorical signals**：披露时的语言方式如何

并进一步问：

· **这些不同的信号，会不会通过改变 backers 对 creator competence 和 AI washing concerns 的判断，进而影响 pledge decisions。** 

# **二、研究方法**

## **1）总体实证设计：政策冲击 \+ DID**

作者使用 Kickstarter 的 AI disclosure policy 作为外生冲击。这个政策要求 creators 在项目提交时说明：

· 是否使用 AI 

· AI 如何参与项目开发、设计或宣传 

这些 disclosure 会被公开展示在项目页面的 “Use of AI” 区域。

作者把：

· **AI-related projects** 作为 treatment group 

· **non-AI projects** 作为 control group 

然后用 **difference-in-differences (DID)** 来估计政策实施后 AI disclosure 对众筹表现的影响。 

## **2）AI-related campaign 的识别**

作者先用一个三部分的关键词词典识别哪些项目属于 AI-related：

· 一部分来自既有文献中的 canonical AI terms 

· 一部分来自实际 campaign descriptions 中 creators 对 AI 的表达 

· 一部分来自生成式 AI 工具和模型名称，例如 ChatGPT、Claude、Gemini、LLaMA、Mistral 

只要 title 或 description 中出现至少一个词典关键词，就把项目归为 AI-related。这个识别与 creators 自报的 AI adoption 高度一致，覆盖了大约 97% 明确披露 AI 使用的项目。

## **3）机制识别：在线实验**

除了平台数据的 DID，作者还做了 **四个 Prolific 在线实验**，分别操纵四个 disclosure 维度：

· AI involvement 

· explicitness 

· authenticity 

· emotional tone 

实验通过编辑真实 Kickstarter 的 AI disclosures 来构造 high / low 条件，再观察参与者的：

· pledge intention 

· perceived AI washing 

· perceived creator competence 

# **三、数据来源**

这篇论文的数据主要有两部分。

## **1）Kickstarter 平台数据**

作者收集了 Kickstarter 项目数据，观察窗口覆盖政策实施前后各一年，即 **2022 年 8 月到 2024 年 8 月结束的项目**。主样本一共有 **35,832 个项目**。

主要结果变量包括：

· **LogTotalPledge**：总筹资额

· **LogTotalBackers**：总支持者人数

## **2）Prolific 在线实验数据**

四个实验总共得到 **318 个完整回应**，剔除 manipulation check 失败者后，主实验分析基于 **266 名参与者**。

 

# **四、研究结论**

## **1）强制 AI disclosure 整体上降低众筹表现**

主结果显示，强制 AI disclosure 政策实施后，AI-related projects 的：

· 筹资额平均下降约 **39.8%** 

· backer 数量下降约 **23.9%** 

这说明在众筹场景里，AI disclosure 平均而言不是利好信号，而更可能引发担忧。

## **2）“实质信号”会放大负面效应**

作者发现，**更高的 AI involvement** 会让 AI disclosure 的负面效应更强。也就是说，当 backers 感觉 AI 不是辅助工具，而是项目产出的核心来源时，他们反而更不愿意支持。 

## **3）“表达方式”会显著改变市场反应**

三个 rhetorical signals 的结果是：

· **high explicitness**：减弱负面效应

· **high authenticity**：减弱负面效应

· **high positive emotional tone**：加剧负面效应

也就是说，清楚、具体、真诚的 AI disclosure 会让 backers 没那么抗拒；但如果过度热情、过度宣传，反而更像在“吹 AI”。

## **4）机制上主要通过 competence 与 AI washing concerns 发挥作用**

实验结果表明：

· **高 AI involvement** 主要通过降低 perceived creator competence 来降低 pledge intention 

· **高 explicitness** 通过提升 competence、并部分减少 AI washing concerns 来提高 pledge intention 

· **高 authenticity** 主要通过先降低 AI washing concerns，再提升 competence 来提高 pledge intention 

· **过高 positive emotion** 则通过提高 AI washing concerns、再压低 competence 来降低 pledge intention 

# **五、对AI disclosure对分类**

## **它明确提出了“substantive”与“rhetorical”两层区分，两类互补信号：**

### **（1）Substantive signals**

指事实性、能力性、过程性的内容，反映项目中 **AI 实际参与的程度和方式**。  
在这篇论文里，substantive signal 的核心操作化变量就是 **AI involvement**。作者把它定义为：

l AI 在项目产出中是处于核心位置，还是只是边缘支持角色。 

这其实很接近 **substantive AI disclosure**，因为它关心的是：

· AI 是不是被真正用于生产核心输出 

· AI 参与程度高不高 

· 它是辅助还是替代了人类创造劳动

### **（2）Rhetorical signals**

指不是“AI 做了什么”，而是“你怎么说 AI 做了什么”。作者基于 Aristotle 的 rhetorical triangle，将其拆成三维：

· **Explicitness (logos)**：披露是否清楚、具体、技术性强

· **Authenticity (ethos)**：披露是否真实、可信、个人化

· **Emotional tone (pathos)**：披露是否带有过度积极、煽动性的情绪色彩

#  

# **六、它实际中如何量化地区分这些概念**

## **1）AI involvement：量化 substantive signal**

作者用 **GPT-4o-mini** 对 AI disclosures 做分类，构造 **HighAIInvolvement**：

· 如果 disclosure 表明 AI 是项目主要输出形成的核心部分，而不是边缘支持工具，则记为 1 

· 否则为 0 

这相当于把“AI 实际参与程度”量化成 substantive dimension。

## **2）Explicitness：量化 logos**

作者仍用 GPT-4o-mini 给 disclosure 打标签。如果 disclosure 对 AI 用法解释得：

· 清楚

· 逻辑性强

· 有技术细节

· 不模糊

则记为 **HighExplicitness \= 1**。

## **3）Authenticity：量化 ethos**

如果 disclosure 呈现出：

· 个人化

· 真诚

· 可信

· 不是模板化、空泛语言

则记为 **HighAuthenticity \= 1**。

## **4）Positive emotion：量化 pathos**

作者用 **VADER sentiment analysis** 构造 **HighPosEmotion**，把正向情绪高于样本中位数的 disclosure 标成 1。

Yang Cao（关键词法+LLM）

**关键词列表法：**

数据来源 2010-2023 10-k，随机选取50家公司

1- 筛选出所有提及AI的10-k，每个年份随机选择25个10-k，一共350个

2- 建立 keyword list（包含术语的频数），为了保证强相关性，控制在25个keywords

3- improve the accuracy of using AI keyword list in classification (列表识别与人工识别的一致性达到98%）

4- 解读每个阶段被提及次数最多的关键词，与AI发展趋势对应

**使用ChatGPT-4o解决局限性：**

（上下文缺失、词义存在歧义、无法区分用途 \<收入增长、成本下降、披露风险\>）

1- 围绕每个关键词提取前后各400个词，ChatGPT审查，把真正有关AI的内容提取出来

2- 按用途分类：

（1）收入：Product Development, Pricing Optimization, AI Product Provider

（2）成本：Inventory Management, Operational Efficiency

3- 提供 probability score

4- 识别风险披露：

（1）监管风险（2）操作风险（3）竞争风险

（4）网络安全风险（5）伦理风险（6）第三方风险

5- 衡量AI信息披露强度：计算与AI相关内容占全文的比例，构造AI intensity指标  
6- prompt的设计：  
（1）Zero-shot prompting：用于判断文本是否属于 AI 披露，以及属于哪一类应用场景  
（2）Few-shot prompting：用于从文本中剔除与 AI 无关的部分，保留真正 AI 披露内容

Anup Basnet（NLP）

数据来源：2005-2018年 Russell 3000公司 10-k年报中的item 1（business description）

**关键词识别+人工语境分类**

1- actionable

2- speculative

3- irrelevant

 Tawei Wang

数据来源：SEC 10-K

**1- 关键词识别：**

搜索 10-K 里是否出现 “artificial intelligence” 及其变是否出现：AI=1 AI=0

AI披露强度：AIFreq（用次数代替）

AI风险披露：AIRisk=1

AI风险披露强度：AIRiskFreq

**2- 风险主题模型LDA：**

Topic 1: new technology market competition

Topic 2: business operations

Topic 3: regulation and security

构造三个 topic dummy，将每段风险文本分配给概率最高的主题

**3- 价值相关性回归**

Price \= β0 \+ β1 AI \+ β2 AIRisk \+ controls \+ FE \+ ε

 

\#\#\# 第一步：获取企业的“言辞” (The "Talk" \- 文本数据爬取)

要分析企业有没有吹牛，首先要拿到他们公开说的话。主要来源是 \*\*10-K 年报\*\* 和 \*\*财报电话会议 (Earnings Calls)\*\*。

\#\#\#\# 1\. 爬取 10-K 年报文本 (SEC EDGAR)  
\*   \*\*目标\*\*：获取美国上市公司的 10-K 文件，并精准提取出 Item 1 (业务)、Item 1A (风险因素) 和 Item 7 (管理层讨论与分析 MD\&A)。  
\*   \*\*获取方式\*\*：  
    \*   \*\*官方/开源工具\*\*：强烈建议不要从零写爬虫，直接使用 Python 库 \`sec-edgar-downloader\`。它可以批量下载指定 Ticker 和年份的 10-K 文件。  
    \*   \*\*数据清洗难点\*\*：SEC 的文件包含大量 HTML 标签和不可见字符。使用 Python 的 \`BeautifulSoup\` 配合正则表达式（Regex）来清洗文本。  
    \*   \*\*精准截取段落\*\*：利用正则表达式定位目录锚点（例如匹配 \`(?i)item\\s+1a\\.\\s+risk\\s+factors\` 到下一个 Item），只抽取所需章节，大幅减少后续 LLM 的 token 消耗。

\#\#\#\# 2\. 爬取财报电话会议记录 (Earnings Conference Calls)  
\*   \*\*目标\*\*：获取管理层演讲 (Presentation) 和问答环节 (Q\&A) 的文字记录。  
\*   \*\*获取方式\*\*：  
    \*   \*\*学术数据库 (首选)\*\*：如果你们学校购买了 \*\*WRDS (Wharton Research Data Services)\*\* 数据库，直接去提取 Thomson Reuters StreetEvents 数据集，这里面有结构化非常好的电话会议 transcript。  
    \*   \*\*爬虫 (备选)\*\*：如果没有数据库权限，可以爬取金融网站（如 Seeking Alpha、Motley Fool）。  
        \*   \*\*工具\*\*：这网站反爬很严，普通的 \`requests\` 行不通，需要使用自动化测试工具 \`Playwright\` 或 \`Selenium\`，配合动态代理池 (Proxy Pool) 来模拟真实用户浏览并抓取文本。

\---

\#\#\# 第二步：获取企业的“行动” (The "Walk" \- 实质性 AI 能力数据)

为了识别 "AI Washing"（蹭热点），你们必须找到独立于文本之外的\*\*客观数据\*\*来证明企业真的在搞 AI。

\#\#\#\# 1\. AI 人才储备数据 (Human Capital)  
文献中反复提到 \*Babina et al. 2024\* 的数据（AI Employee Share），这是目前学术界衡量真实 AI 投入的黄金标准。  
\*   \*\*获取方式\*\*：  
    \*   \*\*开源数据集\*\*：很多顶级期刊的作者会把最终的 Firm-level 汇总数据公开在 GitHub 或个人主页。你们可以去搜寻 \*Babina\* 论文的 Data Availability 声明。  
    \*   \*\*商业数据库替代\*\*：利用你们学校的资源，查找是否订阅了 \*\*Lightcast (原 Burning Glass)\*\* 或 \*\*Revelio Labs\*\*。这些数据库汇集了全网的招聘启事和员工简历，可以直接筛选“包含 AI 技能”的岗位比例。  
    \*   \*\*不要自己爬\*\*：极度不建议自己去爬 LinkedIn 或 Indeed，防爬机制极高且有法律风险。寻找学术共享数据是正道。

\#\#\#\# 2\. 专利与知识产权数据 (AI Patents)  
\*   \*\*目标\*\*：获取企业申请的 AI 相关专利，以及正文中引用了哪些 AI 技术（参考 Moon et al. 的 In-text citation 方法）。  
\*   \*\*获取方式\*\*：  
    \*   \*\*API 直接拉取\*\*：使用 \*\*USPTO PatentsView API\*\*，它提供结构化的 JSON 数据。  
    \*   \*\*Google BigQuery\*\*：Google 托管了公开的专利数据集 (Google Patents Public Datasets)。你可以直接用 SQL 语句在网页端提取包含特定 AI 关键词的专利正文，效率比爬虫高一万倍。

\---

\#\#\# 第三步：NLP 处理与大模型分析流水线 (The Pipeline)

拿到海量文本后，如何像文献中那样“提取前后400词”并“喂给 ChatGPT”？

\#\#\#\# 1\. 关键词命中与上下文截取 (Python 脚本)  
\*   \*\*方法\*\*：使用 Python 的 \`nltk\` 或 \`spacy\` 库进行分词。  
\*   \*\*逻辑\*\*：写一个脚本，扫描文本，一旦命中 "artificial intelligence", "machine learning", "LLM" 等关键词，自动截取该词前后各 400 个 tokens 的窗口，保存成一个 Excel/CSV 的新列，命名为 \`AI\_Context\`。

\#\#\#\# 2\. 批量调用 ChatGPT (OpenAI API)  
\*   \*\*降本增效核心技巧\*\*：千万不要用普通的循环一个一个发请求去调 API，既容易触发 Rate Limit，又极其昂贵。  
\*   \*\*解决方案\*\*：使用 \*\*OpenAI Batch API\*\*。  
    \*   将你们所有的 \`AI\_Context\` 打包成一个 \`.jsonl\` 文件。  
    \*   在 System Prompt 中严格定义输出格式（要求 JSON 格式输出，比如 \`{"is\_real\_ai": 1, "category": "Product Development"}\`）。  
    \*   上传给 Batch API，通常 24 小时内跑完，\*\*成本直接打 5 折\*\*。

\---

\#\#\# 第四步：财务与控制变量数据获取 (Controls & Outcomes)

也就是回归方程里的 $Controls$，比如公司规模、资产回报率、市账比等。  
\*   \*\*获取方式\*\*：  
    \*   这个最简单，直接使用 Python 的 \`wrds\` 库连接学校的数据库。  
    \*   编写 SQL 脚本，从 \*\*Compustat\*\* (北美公司财务数据) 和 \*\*CRSP\*\* (股票收益率数据) 中按公司标识符 (CIK 或 TICKER) 联合提取。

\---

\#\#\# 💡 给你们小组的行动建议 (Action Plan)

1\.  \*\*明确目标\*\*：跟组员确认你们究竟打算分析哪种文件？（10-K 还是 Conference Calls？两者爬取难度不同）。  
2\.  \*\*摸底学校资源\*\*：立刻去学校图书馆主页，确认是否有 \*\*WRDS (CRSP, Compustat, Thomson Reuters)\*\* 的访问权限，这能给你们省下 80% 的爬虫工作。  
3\.  \*\*跑通小样本\*\*：随便选 5 家公司（比如微软、英伟达，加几家传统行业的公司），用 \`sec-edgar-downloader\` 下载它们 2023 年的 10-K，写几行 Python 代码测试一下“关键词前后 400 词截取”以及“调用 ChatGPT API 分析”的流程。

一、 如何获取和清洗 10-K 年报文本？（EDGAR 爬取标准）  
Cohen, L., Malloy, C., & Nguyen, T. (2020). "Lazy Prices." The Journal of Finance, 75(3), 1371-1415.  
(注：这是金融文本分析领域的顶会神作，几乎所有处理 10-K 的论文都会借鉴它的清洗流程)

数据获取 (Scraping)：  
作者通过自动化脚本连接到 SEC EDGAR 数据库 的 FTP 服务器，批量下载了 1995-2014 年间的 10-K 和 10-Q 文件。  
文本清洗技术 (Text Parsing)：  
剔除 HTML/XBRL：作者使用 Perl/Python 的正则表达式（Regex）去除了所有的 HTML 标签、表格（Tables）、图像和非文本格式。这证明了\*\*“去除格式噪音，只保留叙述性文本（Narrative text）”\*\*是学术界的标准操作。  
精准截取章节：论文详细披露了他们如何使用正则表达式匹配 Item 1 (Business)、Item 1A (Risk Factors) 和 Item 7 (MD\&A)。例如，通过匹配加粗的 "Item 1A" 直到出现 "Item 1B" 来截取特定段落。  
对你们的借鉴：这篇文献强力支持了我们使用 Python 脚本（配合正则表达式）去清洗 SEC 文件，而不是通读全文。你们在论文中可以直接引用它来证明你们“只提取特定 Item 进行 NLP 处理”的合理性。  
二、 如何获取财报电话会议 (Earnings Calls) 数据？  
Hassan, T. A., Hollander, S., Van Lent, L., & Tahoun, A. (2019). "Firm-level Political Risk: Measurement and Effects." The Quarterly Journal of Economics, 134(4), 2135-2202.  
(注：这篇是构造“特定主题文本指标”的模板，其抓取和计算逻辑被后续无数 AI 披露论文模仿)

数据获取：  
作者没有自己去爬网站，而是直接使用了 Refinitiv (Thomson Reuters) StreetEvents 数据库。该数据库包含了经过严格结构化的电话会议 Transcript，并明确区分了高管陈述部分 (Presentation) 和问答部分 (Q\&A)。  
NLP 与技术处理：  
近邻算法 (Proximity Search)：为了判断企业是否真的在谈论某个主题，作者编写了算法，计算“主题关键词”与“近义词库”在文本中同时出现的频率（通常限制在相距不到 10 个单词内）。  
对你们的借鉴：这篇顶刊告诉我们，能用现成数据库（如 WRDS 里的 StreetEvents）就绝不要自己写爬虫，数据质量天差地别。同时，它证明了“提取关键词前后窗口（如你们设定的 400 词）”来锁定语境的方法，在顶刊中是完全被认可的有效计量手段。  
三、 如何获取企业真实的“行动”数据？（The "Walk" \- 人才数据）  
Babina, T., Fedyk, A., He, A. X., & Hodson, J. (2024). "Artificial Intelligence, Firm Growth, and Product Innovation." Journal of Financial Economics.  
(注：这就是你们同学笔记里反复提到的那篇神作，定义了如何用招聘数据衡量真实 AI 投入)

数据获取：  
作者使用了一家名为 Burning Glass Technologies (现改名为 Lightcast) 的商业数据库。该数据库通过网络爬虫（Web Scraping）抓取了全球超过 4 万个招聘网站的超 2 亿份招聘启事（Job Postings）。  
NLP 与技术处理：  
他们没有单纯搜 "AI" 这个词，而是构建了一个严谨的 AI 技能词典（例如包含了 "Machine Learning", "Natural Language Processing", "TensorFlow", "Computer Vision" 等底层技能词汇）。  
他们计算了每家公司每年发布的职位中，要求具备这些 AI 技能的职位比例，以此作为企业“真实 AI 投资”的代理变量。  
对你们的借鉴：这篇文章完美佐证了\*\*“不能只看财报，必须引入第三方招聘/人力数据来验证 AI Washing”\*\*的思路。如果你们学校没有 Lightcast 的权限，你们可以在论文中明确引用这篇文章的附录词典，去 LinkedIn 等平台进行小样本的抽样验证，或者寻找开源的人力资本数据集。  
四、 为什么要用 LLM (如 ChatGPT) 替代传统词典法？  
Huang, A. H., Wang, H., & Yang, Y. (2023). "FinBERT: A Large Language Model for Extracting Information from Financial Text." Contemporary Accounting Research, 40(2), 806-841.

研究对比：  
作者专门对比了传统的词典法（Dictionary Approach，比如数 "AI" 这个词出现了几次）与大语言模型（LLM/BERT）在处理金融文本时的效果。  
结论与技术发现：  
传统的词典法无法理解上下文（Context）和否定语态（Negation）。例如，公司说 "We have not yet adopted machine learning in our core products" 会被传统算法误判为 AI 披露。  
大语言模型能够准确捕捉文本的情感倾向、具体应用场景（Use cases）以及战略意图。  
对你们的借鉴：这篇文献直接为你们\*\*“使用 ChatGPT-4o 来判断是否真的在讲 AI 并分类 AI 用途”\*\*提供了学术背书。在答辩或写论文时，引用这篇文章可以有效反驳“为什么不用简单的词频统计”的质疑。  
💡 你们小组的下一步行动建议（附带引用支持）：  
如果你们要在论文或汇报中介绍你们的Data Pipeline（数据获取管道），可以这样写来彰显学术严谨性：

文本来源：基于 Hassan et al. (2019) 的建议，我们通过 WRDS 数据库获取结构化的财报电话会议纪要；基于 Cohen et al. (2020) 的方法，通过自动化脚本拉取 EDGAR 10-K，并用 Regex 剥离 HTML，精准提取 Item 1, 1A, 7。  
真伪验证：参考 Babina et al. (2024) 的前沿做法，我们将尝试获取企业的 AI 相关招聘数据（AI Human Capital），将其作为“实体 AI 能力 (The Walk)”的代理变量，以此剥离出无法被解释的“蹭热点 (AI Washing)”水分。  
NLP 模型：摒弃传统的粗糙词频统计，我们在截取关键词上下文后，应用类似 Huang et al. (2023) 所验证的大语言模型优势，利用批量 API (Batch API) 调用 LLM 对文本进行“深层语境分类”。

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,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>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAgEAAAAwCAYAAACIX6lAAAAQXUlEQVR4Xu2d55sUxRaH/WPuNSuKGEAEAxhQFBOiawADqIiKqICKeAEFVBBBMSEqJlDBrIABAxgwYHjEACoggiImzPdLX97innlqTnVP98z07M5unw/vs1Onqruru6urfnXqdO9222//r8gwDMMwjOKxnTYYhmEYhlEMTAQYhmEYRkExEWAYhmEYBcVEgGEYhmEUFBMBhmEYhlFQTAQYhmEYRkExEWAYhmEYBcVEgGEYhmEUFBMBhmEYhlFQTAQYhmEYRkExEWAYhmEYBcVEgGEYhmEUFBMBhmEYhlFQTAQYhmEYRkExEWAYhmEYBcVEgGEYhmEUlIaLgEEDTw9sRjz77LNX1LXrPoG9PdLSMiDab7+9A7th1MKOO24fnXZaS7TrrjsHeYZh1E5DRcALi5+P/vvPn4Hd56qrRrkyWdDbJlHNNg8/fH80evTlgT2NAw7Y3+1/w7frgrxqmf/YPLevOXPuicaNG+t+r1v7VbTDDv8OyjY7kyZOiFav+jTq3/+E6O6774xGjrw0KJMVff/h+skTS/mzZ99VljfxugnBPtozcl4Txv8nyGsWEHpbtvzk6omI1fn1cuqpp5Suw1NPLogWL9rWp+yyy07RwuefCco3M3IeY8ZcEeQZRlvRMBFw5JFHRCs/+dA1+q+/WhXkC48veDSwsc2M6TeV2Z579umgXCVuvGGy24+2ayjzz99/BPYsPPnE/K3n+FFgz8rw4Re641922Yggb889O6Veu2bj119/DGxZ7kEa0nlqO7ND7oG2dyRefGFhq4iAnXfeMerUabfAnpWke1QPlZ7N664dn/vxfDZ9/21gy4O8RcDQoecFto5MPW202enX7+jA1ho0TAT8/dfvrpOWzmGnnXYIysCHH7wX2Cg/7aYby2xJ2ycxedJ1De0khKROKgtpHecrr7xUMb/ZuPjiYYEtj/rHXSfag7Z1RBYveq5VREDfvn2iYcOGBvas3H77rbneD7wK7K+S+z/P42kate+8RcDmzd8Fto5MPW202Wkrz1ZDRMAhhxwUffH5Svd7wfxHXMP/dOXHQTn4/bdfAhvlb5p6Q2CvhkkTr23Yg+yzetVngS0r1G/6zVMDu8DsjDJHHdUnyGs2unfvFtgOPLBH9Mi8hwN7tWgRUBQBAIsWPtsqIqBfv751d7B53pM/fv81dX/PP1eddzAr/fsfn3rsWslbBPz88w+BrSNTbxttZljq0rbWoCEi4M8/tpTN3KUTj1vj3nffLoEtiwjo3LmT8yJQ9vPPPgn2zdq0PMgIEn7Pm/tQWZk33ng92rhhXakcnov33lse/fjj9842YED/6N1333az/alTrg/qoN3fRxxxaPTblp9d+VdffbliRyIxBSeddGKQ50OZtmoc1SAqFg/OY4/OjYYMOafi+VeDtB9+MzPMsl8E1AcrtrUPEaTAEswDD9zn4i/mzn3AtSPsTzw+P5o370G3vLD77rtGDz54X3TvvXe7mBHaKGUl3aVL5+jSSy9x+8F23nlDSvuv1C7ffnuZczOT16NHd/eccJ38ehPnQLsiJuTsswa1mgg47rh+dXeweP9mzpwR2GshS7unztr2+ILH3LbMkJmMiP3llxZFX67+3OXxnHOdERpfffmFu99STjwawLUHyVu27FUXAzR1ymQH58uyY5bjC+T5IoB7zH7oM77buD52UlQJ3QdlgUnFxg3fuGMiePw86q/LNxO1tNEhg8921/2hh+aU2fv0OSzq2bNHUL6teOnFhYEtK336HO6WzGvxJuQuArrv3zVau2Z1mQ3Fzk14f+sAq8vHQdm4QVdoaTnZlZH1ITpp0vt3269UhiAxbL/8srlkoxFgI6iINBeOjhiblDnmmKNKncApp5zkbByH9LhxV5fVw49+32uvPcr2QyfvpzWzZt3h8tOWOaQu2l4vdKBZybIORx15oP768zfXkT37zFO51VuugdwHiFt6EGgHlJFBgsFd6rLHHrtHJ554nEvTOcggTVwG9aZTxHb44Yf+/56PdYNGr16HuPRZZw50aQb7b9Z9XaoX+0hrl7179yrVn05Yfku9b7vtlmjJy4tLaZmRXjthXHCOeXP88fWLgJEjR5SdT63Is1SNoBDvEPdUbDzbt9xys/vNPSCwkDJig++/W19W525d990qBGY6G79B8vBsMbgTp0PgK+1Ftk07vkAZXwToQV+n0yAoU9sqcc89s0rtTre/3XbbxT23eptmoto2yqTOP9cV779TysujreYJQlXb0qCv4jyITaON8+zoMmnkLgKSLqzcBDpKnaehXJII6NZ1Wwc/ZPBZZXaixv1jiwjQ2+uGj7rX5XQZsfmCQnPuuYNdGd+DQUehywnj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>

[image4]: <data:image/png;base64,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>

[image5]: <data:image/png;base64,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>