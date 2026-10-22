# 算法规格

## 1. 基础集合
大乐透完整组合 C=(F_C,B_C)：
- F_C: 前区5个号码，范围01..35
- B_C: 后区2个号码，范围01..12

历史第 t 期开奖 H_t=(F_t,B_t)。

## 2. 组合级历史碰撞（核心，不可省略）
对每组 C 与每期 H_t：
- a_t = |F_C ∩ F_t|，a∈{0..5}
- b_t = |B_C ∩ B_t|，b∈{0..2}
- k_t = a_t+b_t，k∈{0..7}

每组候选的二维碰撞分布：
N_{a,b}(C) = Σ_t I(a_t=a and b_t=b)

总位数分布：
N_k(C) = Σ_t I(k_t=k)

必须满足校验：
Σ_{a=0..5}Σ_{b=0..2} N_{a,b}(C) = 历史期数
Σ_{k=0..7} N_k(C) = 历史期数

## 3. 批量汇总
候选集合 Ω：
M_k = Σ_{C∈Ω} N_k(C)
U_k = Σ_{C∈Ω} I(N_k(C)>0)

二维同理：
M_{a,b}=Σ_C N_{a,b}(C)
U_{a,b}=Σ_C I(N_{a,b}(C)>0)

解释：
- M：组合-期次对的数量。
- U：至少发生过一次该等级碰撞的不同候选组合数。

## 4. 历史碰撞稀缺排序
默认使用“高位优先字典序”，避免隐含人工权重：
scarcity_key(C) = (N7,N6,N5,N4,N3,N2,N1)
升序排列。

即先最小化历史全中次数，再最小化6位、5位……1位次数。

可选 weighted 模式必须显式配置权重，且 UI 标明实验参数。

## 5. BitMask 实现
前区35位、后区12位都可放入64-bit整数：
front_hits = popcount(candidate_front_mask & draw_front_mask)
back_hits = popcount(candidate_back_mask & draw_back_mask)

禁止字符串逐号码循环作为大批量主路径。

## 6. 单号码统计（第二层，不得替代碰撞层）
### 频率
F_i(W)=count(i in last W draws)/W
支持 short/mid/long 窗口。

### 当前遗漏
O_i = 从 history_cutoff 向前连续未出现的期数。
标准化：G_i=(O_i-mean(O))/std(O)，std=0时置0。

### 趋势
Trend_i = α*z(F_short)+β*z(F_mid)+γ*z(F_long)+δ*z(Omission)
参数配置化。

## 7. 结构特征
前区：
- 奇偶比 odd:even
- 三区：01-12 / 13-24 / 25-35
- 和值 sum
- 跨度 max-min
- 连号对数量
- 同尾对数量（可选）
- 与上一期重号数（可选）

后区：
- 奇偶
- 大小/区段
- 和值/跨度（仅作描述与实验特征，不做硬性“必然”约束）

### 结构趋势分
对结构类别使用历史窗口频率并做 Laplace smoothing：
p(s)=(count(s)+λ)/(N+λ*K)
结构分可取 log(p(s)) 或 percentile。

默认用软评分，只有玩法合法性是硬过滤。用户显式设置的过滤器才做 hard filter。

## 8. 模型生成流程
1) 截取 <= history_cutoff 的历史。
2) 计算单号码统计。
3) 形成候选号码池（可由用户固定或按分数取Top N并做最小覆盖约束）。
4) 枚举/采样合法5+2组合。
5) 计算结构特征。
6) 计算每组完整历史碰撞 N_ab / N_k。
7) 默认按 scarcity_key 主排序。
8) 次排序使用 number_score + structure_score + diversity_score。
9) 选Top K，并用多注分散算法减少高度相似组合。
10) 保存完整 run 参数和历史截止期。

## 9. 多注分散度
Jaccard：J(A,B)=|A∩B|/|A∪B|（前后区可分别算再加权）。
选择第 n 注时，对与已选票的最大相似度施加惩罚。

## 10. 综合次评分（默认示例）
注意：碰撞稀缺默认作为主排序，不必塞进线性分数。
secondary_score =
  0.45*number_score +
  0.45*structure_score +
  0.10*diversity_score

权重必须在配置中，可版本化。

## 11. 随机生成
- production: `secrets.SystemRandom()`
- test/回放: 可注入 `random.Random(seed)`
- 每注内部无重复
- 默认拒绝同批完全重复票

## 12. 复式
若前区选 nf 个、后区 nb 个：
bets = C(nf,5)*C(nb,2)

## 13. 胆拖
Df=前区胆码数，Tf=前区拖码数；Db/Tb同理。
bets = C(Tf,5-Df)*C(Tb,2-Db)
约束：
- 0<=Df<=4，0<=Db<=1
- 胆/拖不重叠
- 对声明为胆拖的分区，胆码必须>0
- 对声明为胆拖的分区，总选择数必须超过基本选择数
- 组合必须能补足5前+2后

## 14. 金额
base_unit=2元
addon_unit=1元（追加开启时，对展开的每一基本注）
multiplier=1..99
cost=bets*(base_unit + (addon?addon_unit:0))*multiplier
另按游戏规则配置校验单张票金额上限。

## 15. 防数据泄漏
任何 generation/backtest 必须带：
- target_issue
- history_cutoff_issue
- history_window

数据库查询必须保证 draw.issue <= history_cutoff_issue。
测试必须构造 target 后一期开出“完美匹配”并证明不会影响 target 生成结果。
