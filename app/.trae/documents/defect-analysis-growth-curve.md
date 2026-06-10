# 项目缺陷分析：成长曲线及相关代码

> **目标：** 全面审查项目代码，识别缺陷和潜在风险，重点关注成长曲线（growth curve）相关逻辑。
> **项目概述：** 基于 Flask 的教学测评系统（EduScore），核心功能是让学生完成教学单元的前测/后测，通过对比前后测得分率计算学习增益（gain），并以成长曲线图表展示。

---

## 缺陷清单

### 缺陷 #1: `normalized_gain()` 天花板饱和返回 0.0 掩盖真实退步
**文件:** `services/gain.py:16-22` | **严重程度:** 中

```python
def normalized_gain(pre_rate, post_rate):
    if pre_rate is None or post_rate is None:
        return None
    if pre_rate >= 100:
        return 0.0  # <--- 问题
    return round((post_rate - pre_rate) / (100 - pre_rate), 3)
```

**问题:** 当前测得分率为 100（满分），且后测得分率低于 100（学生退步了）时，`normalized_gain` 返回 `0.0` 而非 `None` 或负值。这会向教师/学生传达"没有变化"的误导信号——实际上学生退步了，但数据被静默覆盖。

**根因:** Hake g-factor 公式 `(post - pre) / (100 - pre)` 在 `pre = 100` 时分母为 0 无定义。代码选择返回 `0.0` 作为兜底，但这在语义上不正确。

---

### 缺陷 #2: `Submission.grade()` 多选评分对 `correct_answer=None` 无防护 → 崩溃
**文件:** `models.py:218-222` | **严重程度:** 高

```python
elif q.type == 'multi_choice':
    correct_set = set(x.strip().upper() for x in q.correct_answer.split(','))
    #                                              ^^^^^^^^^^^^^^^
    #                   如果 q.correct_answer is None，这里会抛出 AttributeError
```

**问题:** 当题目的 `correct_answer` 字段为 `None`（如教师未设置、简答题迁移为多选）时，`.split(',')` 会在 `None` 上抛出 `AttributeError`，导致整个 `grade()` 调用崩溃。同样的问题也存在于 `views/student.py:156` 和 `services/gain.py:55` 的多选评分分支。

而单选题分支已做了防护：`(q.correct_answer or '').strip().upper()`。

**对比:** `services/gain.py:55` 中的 `objective_breakdown()` 使用了 `(q.correct_answer or '')` 做了防护，与 `grade()` 不一致，说明这是遗漏而非故意。

---

### 缺陷 #3: `objective_breakdown()` 多选空答案的边界行为不正确
**文件:** `services/gain.py:55-56` | **严重程度:** 低

```python
correct_set = set(x.strip().upper() for x in (q.correct_answer or '').split(','))
```

当 `correct_answer` 为 `''` 或 `None` 时，`''.split(',')` 产生 `['']`，则 `correct_set` = `{''}`。这意味着学生必须留空才算答对。这是一个隐晦的边界行为——题目没有设置正确答案时，不应要求任何"空匹配"。

---

### 缺陷 #4: `score_rate()` 使用 `not submission.total_score` 将"已评分但 0 分"误判为无效
**文件:** `services/gain.py:4-7` | **严重程度:** 低

```python
def score_rate(submission):
    if submission is None or not submission.total_score:
        return None
```

**问题:** `not submission.total_score` 在 `total_score == 0` 时也为 `True`。如果测评总分恰好为 0（所有题目分值均为 0 或没有题目），正确提交的 `score_rate` 也会返回 `None`——但实际上得分率应为 `None`（无法计算），尚可接受。真正的问题是：如果 `score == 0` 且 `total_score > 0`（学生确实交了白卷），则代码正确返回 `0.0`，这是对的。但条件表达式的语义不清晰，建议改为显式的 `submission.total_score == 0` 使意图明确。

---

### 缺陷 #5: `build_student_growth_context()` 跨教学班单元编号重置 → 图表标签重复冲突
**文件:** `services/growth.py:13-40` | **严重程度:** 中

```python
for tc in classes:
    units = tc.units.order_by(...).all()
    for idx, unit in enumerate(units, start=1):  # <--- 每个 class 都从 1 开始
        chapter_number = _chapter_number(unit, idx)
        report['chapter_label'] = f'第{chapter_number}章'
```

**问题:** 如果学生选修了两门课程，每门课都有第 1 章，则成长曲线图表中会出现两个 `"第1章"` 标签，学生无法区分它们属于哪门课。图表数据虽然包含 `class_name` 字段，但 `display_label` 没有附带课程信息。

**影响:** 前端图表渲染时，X 轴会显示两个相同的标签名称，造成混淆。

---

### 缺陷 #6: `_chapter_number()` 的 sort_order=0 与 enumerate 起始值 1 冲突
**文件:** `services/growth.py:9-10` | **严重程度:** 低

```python
def _chapter_number(unit, fallback_index):
    return unit.sort_order if unit.sort_order and unit.sort_order > 0 else fallback_index
```

**问题:** `sort_order` 默认为 0，`fallback_index` 从 `enumerate` 的 `start=1` 得到。教师可能有意将某个单元 `sort_order` 设为 0，但这与 "0 表示未设置" 无法区分。如果教师同时设置了 `sort_order=0` 和 `sort_order=1`，这两个单元都会显示为 `第1章`。

---

### 缺陷 #7: `class_gain_summary()` - 无前测的学生被静默排除
**文件:** `services/gain.py:117-151` | **严重程度:** 中

```python
for sid in student_ids:
    report = unit_gain_for_student(unit, sid)
    if report['absolute_gain'] is not None:   # <--- 没有前测 → gain 为 None → 被排除
        unit_abs.append(report['absolute_gain'])
        ...
avg_abs = round(sum(unit_abs) / len(unit_abs), 1) if unit_abs else None
```

**问题:** 如果一个教学单元只有后测没有前测，所有学生的 `absolute_gain` 都是 `None`，他们被全部排除在统计之外。函数返回 `avg_abs=None`，但上层调用者（`admin.py:67`）把 `summary` 传入模板可能期望看到完整的"无数据"提示，而非静默的空值。

**更严重的情况:** 如果部分学生有前测、部分没有，统计结果会偏向"有前测"的学生群体。均值计算基于 `unit_abs` 而非 `student_ids` 总人数，造成样本偏差。

---

### 缺陷 #8: `unit_gain_for_student()` 在无前测/无提交时目标增益数据不完整
**文件:** `services/gain.py:69-114` | **严重程度:** 低

```python
pre_best = best_submission(pre_subs)   # 可能为 None
post_best = best_submission(post_subs)
pre_rate = score_rate(pre_best)        # None
post_rate = score_rate(post_best)

# objective_gains 中 pre_item['rate'] 为 None 时
# absolute_gain(None, post_rate) → None，目标增益为空
```

**问题:** 返回的 `objective_gains` 列表中每个元素可能 `gain=None`，但前端代码可能期望一个数值。调用方 `build_student_growth_context` 将 `report` 的 `pre_rate`/`post_rate` 传入图表数据但没有目标级增益的展示。如果未来前端需要展示目标增益，这里的 None 值需要做处理。

---

### 缺陷 #9: N+1 查询 — 成长曲线构建触发大量级联 SQL
**文件:** `services/gain.py:117-151`, `services/growth.py:13-40` | **严重程度:** 中

```python
# class_gain_summary 对每个 unit × 每个 student 调用 unit_gain_for_student
for unit in units:
    for sid in student_ids:
        report = unit_gain_for_student(unit, sid)  # 每次调用触发:
        #   unit.get_pre_assessment()       → 1 query
        #   unit.get_post_assessment()      → 1 query
        #   Submission.query.filter_by(...)  → 1 query per assessment
        #   unit.objectives.order_by(...)    → 1 query
        #   objective.questions访问          → lazy loading → N queries
```

**问题:** 一个有 5 个单元、30 个学生的班级，`class_gain_summary` 可能产生 300+ 次数据库查询。虽然对于小型 SQLite 项目这不是致命问题，但随着数据增长会显著拖慢页面加载。

同样，`build_student_growth_context` 中按教学班逐个单元调用 `unit_gain_for_student` 也有 N+1 问题。

---

### 缺陷 #10: `build_student_submission_growth_context()` 使用 `submitted_at.desc()` 但 `best_score_submission` 按得分率而非时间选择
**文件:** `services/growth.py:91-135` | **严重程度:** 低

```python
submissions = (
    Submission.query.filter_by(student_id=student_id)
    .order_by(Submission.submitted_at.desc(), Submission.id.desc())
    .all()
)
# ...
best = _best_score_submission(item['submissions'])
```

**问题:** 先按提交时间降序获取所有提交，然后 `_best_score_submission` 挑选得分率最高的那次提交。这本身逻辑正确——取最优成绩。但排序的 `desc` 顺序对结果无影响（因为 `_best_score_submission` 会遍历全部），只是浪费了对齐读者预期。代码意图不清晰：读者可能误以为排序是为了取最新提交。

---

### 缺陷 #11: `Assessment.is_open()` 使用 `datetime.utcnow()` 而非 timezone-aware datetime
**文件:** `models.py:150-159` | **严重程度:** 低

```python
def is_open(self):
    from datetime import datetime
    now = datetime.utcnow()  # 返回 naive datetime
```

**问题:** Flask-SQLAlchemy 和现代 Python 推荐使用 timezone-aware datetime。`utcnow()` 返回的是不含时区信息的 naive datetime，如果系统时间处理有误或数据库中有带时区的 datetime，可能导致比较行为异常。虽然对于这项目目前影响不大，但这是不推荐的实践。

---

### 缺陷 #12: `app.py` 中 DATABASE_URI 被重复设置
**文件:** `app.py:25、51` | **严重程度:** 低

```python
# 第 25 行
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{INSTANCE_DIR / 'eduscore.db'}"
# ...
# 第 51 行（重复）
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{BASE_DIR / 'instance' / 'eduscore.db'}"
```

**问题:** `INSTANCE_DIR` 已经等于 `BASE_DIR / 'instance'`，两行设置的是完全相同的路径。第 51 行是冗余代码。虽然功能上无害，但表明代码可能经过多次修改而遗留了旧代码。

---

### 缺陷 #13: `build_student_growth_context()` 对未入学学生返回空数据而非错误
**文件:** `services/growth.py:18-23` | **严重程度:** 低

```python
if not class_ids:
    return {
        'unit_reports': [],
        'chart_items': [],
        'chart_payload': [],
        'chart_mode': 'unit',
    }
```

**问题:** 当 `class_ids` 为空列表时，函数返回空数据结构。调用方 `views/student.py:184` 直接把这些空数据传给模板渲染，学生看到的是一张空图表。更好的做法是在视图层判断并显示一条"您尚未加入任何课程"的友好提示。

---

### 缺陷 #14: 成长曲线缺少按课程过滤 / 缺少跨课程聚合视图
**文件:** `services/growth.py:13-47`, `views/student.py:180-185` | **严重程度:** 功能缺失

**问题:** `build_student_growth_context` 将所有课程的单元合并为一维列表，但：
- 没有提供按课程过滤的参数
- 图表标签中的 `class_name` 未体现在 `group_label`/`display_label` 中

当学生选修多门课程时，成长图表缺乏课程维度的区分能力。

---

### 缺陷 #15: 教师端缺少"班级内所有学生成长概览"视图
**文件:** `views/admin.py`, `services/gain.py` | **严重程度:** 功能缺失

**问题:** `class_gain_summary` 按单元聚合了平均增益，但教师无法直接查看：
- 班级内每个学生的个体成长曲线
- 学生之间的成长对比
- 哪些学生增益为负（退步）

当前 `admin/class_detail.html` 只渲染 `summary`，无法下钻到学生级别。

---

### 缺陷 #16: `build_student_submission_growth_context()` 在提交记录为空时返回无意义的图表数据
**文件:** `services/growth.py:91-135` | **严重程度:** 低

如果学生没有任何提交记录，`assessment_payload` 是空列表，但返回值中的 `submissions` 也是空列表，前端渲染时可能遇到空图表的奇怪状态，缺少提示信息。

---

## 缺陷汇总

| # | 文件 | 严重程度 | 类别 |
|---|------|---------|------|
| 1 | `services/gain.py` | 中 | 逻辑：天花板返回 0.0 掩盖退步 |
| 2 | `models.py` | **高** | **崩溃：`correct_answer=None` 时 `.split()` 抛出异常** |
| 3 | `services/gain.py` | 低 | 边界：空答案匹配行为 |
| 4 | `services/gain.py` | 低 | 逻辑：条件表达式语义不清 |
| 5 | `services/growth.py` | 中 | 数据：跨课程单元标签重复 |
| 6 | `services/growth.py` | 低 | 逻辑：sort_order=0 与 idx=1 冲突 |
| 7 | `services/gain.py` | 中 | 统计：无前测学生被静默排除 |
| 8 | `services/gain.py` | 低 | 数据：目标增益 None 值传播 |
| 9 | `services/growth.py`, `services/gain.py` | 中 | 性能：N+1 查询 |
| 10 | `services/growth.py` | 低 | 代码清晰度：排序无实际用途 |
| 11 | `models.py` | 低 | 实践：naive datetime |
| 12 | `app.py` | 低 | 冗余：重复 URI 设置 |
| 13 | `services/growth.py` | 低 | 用户体验：空数据无提示 |
| 14 | `services/growth.py` | 功能缺失 | 缺少课程过滤 |
| 15 | `views/admin.py` | 功能缺失 | 缺少学生级成长概览 |
| 16 | `services/growth.py` | 低 | 用户体验：无提交时空图表 |
