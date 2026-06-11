# eduscore-tracker 架构文档 — AI 复刻指南

> 本文档可独立喂给任何 AI 编码助手（Trae、Cursor、Copilot、Claude Code）用于从零重建此系统。

---

## 1. 项目概述

**EduScore Tracker** 是一个高校教学前测后测评测平台。教师发布测评任务（前测/后测），学生多次提交作答，系统自动判分并可视化追踪成长轨迹。

**核心价值：** 通过前测（学期初摸底）和后测（学期末评估）的分数对比，量化教学效果；允许多次提交，记录每次进步曲线。

**部署目标：** 高校教师通过 `bash run.sh` 一行命令启动，零配置，无需 MySQL/PostgreSQL/Nginx。

---

## 2. 技术栈选型

| 组件 | 技术 | 选型理由 |
|------|------|----------|
| 后端框架 | Python 3.10+ / Flask 3.0 | 轻量、学习曲线低，适合非技术用户部署 |
| 数据库 | SQLite | 零配置，单文件 `instance/eduscore.db` |
| ORM | Flask-SQLAlchemy 3.1 | 模型定义清晰，支持 JSON 列类型，`lazy='select'` 惰性加载 |
| 认证 | Flask-Login 0.6 | 会话管理简单，与 SQLAlchemy 无缝集成 |
| 表单 | Flask-WTF 1.2 + WTForms 3.1 | 内建 CSRF 保护，无需额外配置 |
| 缓存 | Flask-Caching (SimpleCache) | 内存 dict 缓存成长轨迹与班级增益，TTL 60s，写操作即时清除 |
| 前端 CSS | Bootstrap 5.3（本地 static） | 本地 static 文件加载，无外部网络依赖 |
| 前端图表 | ECharts 5（本地 static） | 中文文档完善、柱状图/折线图/分组切换原生支持、配置式 API 适合 Jinja2 模板 |
| UI 图标 | Bootstrap Icons 1.11（本地 static）| 免费、无需注册，字体文件本地化 |
| 密码哈希 | werkzeug.security | Flask 内置依赖，默认 scrypt 算法 |

**国内部署友好：** 所有前端资源（CSS/JS/图标/字体）已本地化到 `static/` 目录，Python 包从清华镜像安装，全程无需翻墙。

---

## 3. 项目结构

```
eduscore-tracker/
├── app/                       # Python 包（Flask 社区惯用包名）
│   ├── __init__.py
│   ├── app.py                 # Flask 工厂函数 (create_app)
│   ├── config.py              # 配置 (SECRET_KEY, DATABASE_URL, CACHE_TYPE)
│   ├── models.py              # 8 张表：User, TeachingClass, ClassEnrollment, TeachingUnit, LearningObjective, Question, Assessment, Submission
│   ├── forms.py               # WTForms 表单：LoginForm, RegisterForm, TeachingClassForm, TeachingUnitForm, LearningObjectiveForm, QuestionForm, AssessmentForm, StudentCreateForm, GradingForm
│   ├── auth.py                # 认证蓝图 (login/login_required/register)
│   ├── extensions.py          # db = SQLAlchemy(); cache = Cache()
│   ├── services/              # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── gain.py            # 学习增益计算 (得分率/Hake g/班级汇总) + 缓存缓存
│   │   └── growth.py          # 成长轨迹数据构建 (统一 chart_payload)
│   └── views/                 # 路由蓝图
│       ├── __init__.py
│       ├── student.py         # 学生端路由 (dashboard/growth/take/result)
│       └── admin/             # 教师后台路由（按功能域拆分）
│           ├── __init__.py    # 公共路由 + teacher_required 装饰器
│           ├── classes.py     # 教学班 & 教学单元 CRUD + 排序
│           ├── questions.py   # 题库管理
│           ├── students.py    # 学生管理
│           ├── assessments.py # 测评管理
│           └── exports.py     # 数据导出
├── templates/
│   ├── base.html              # Bootstrap 5 母版 + 导航栏
│   ├── login.html             # 居中登录卡片
│   ├── register.html          # 注册页
│   ├── admin/                 # 11 个教师专属模板
│   │   ├── dashboard.html / classes.html / class_detail.html
│   │   ├── students.html / student_form.html
│   │   ├── questions.html / question_form.html
│   │   ├── assessments.html / assessment_form.html / assessment_submissions.html
│   │   └── grade.html
│   ├── student/               # 4 个学生专属模板
│   │   ├── dashboard.html / assessment_detail.html
│   │   ├── test.html / result.html
│   └── shared/                # 2 个跨角色共享模板
│       ├── _growth_chart.html    # ECharts 图表 JS（include 引入）
│       └── student_detail.html   # 学生详情 + 成长轨迹（教师 & 学生共用）
├── static/
│   ├── style.css              # 自定义样式
│   ├── bootstrap.min.css      # Bootstrap 5.3 CSS（本地化）
│   ├── bootstrap.bundle.min.js # Bootstrap 5.3 JS Bundle（本地化）
│   ├── bootstrap-icons.css    # Bootstrap Icons 1.11 CSS（本地化）
│   ├── echarts.min.js         # ECharts 5（本地化）
│   └── fonts/                 # Bootstrap Icons 字体文件
├── scripts/
│   ├── init_db.py             # 正式模式初始化
│   ├── seed_data.py           # 最小种子数据
│   ├── demo_data.py           # 演示数据
│   └── rebuild_db.py          # 重建数据库
├── docs/
│   ├── ARCHITECTURE.md
│   └── superpowers/
│       ├── specs/             # 设计文档
│       └── plans/             # 实现计划
├── tests/                     # pytest 测试套件
├── instance/
│   └── eduscore.db            # SQLite 数据库文件（.gitignore 忽略）
├── .gitignore                 # venv/ *.db __pycache__/ *.pyc .env
├── requirements.txt
├── run.sh                     # 一键启动脚本
└── README.md
```

---

## 4. 数据库设计

### 4.1 ER 关系图

```
┌──────────────┐       ┌──────────────────┐
│  users       │       │ teaching_classes │
├──────────────┤       ├──────────────────┤
│ id (PK)      │◄──────│ teacher_id (FK)  │
│ username     │       │ id (PK)          │
│ password_hash│       │ name             │
│ role         │       │ semester         │
│ display_name │       │ description      │
│ created_at   │       │ created_at       │
└──────────────┘       └────────┬─────────┘
       ▲                        │
       │              ┌─────────▼────────────┐
       │              │ class_enrollments    │
       │              ├──────────────────────┤
       │              │ id (PK)              │
       │              │ class_id (FK)        │
       └──────────────│ student_id (FK)      │
        student_id    │ enrolled_at          │
                      └──────────────────────┘
       ┌──────────────┐
       │ teaching_units│────────────────────┐
       ├──────────────┤                    │
       │ id (PK)      │                    │
       │ class_id (FK)│                    │
       │ title        │                    │
       │ sort_order   │                    │
       │ description  │                    │
       │ created_at   │                    │
       └──────┬───────┘                    │
              │                            │
    ┌─────────▼────────────┐    ┌──────────▼─────────┐
    │ learning_objectives  │    │ assessments         │
    ├──────────────────────┤    ├────────────────────┤
    │ id (PK)              │    │ id (PK)            │
    │ unit_id (FK)         │    │ unit_id (FK)       │
    │ title                │    │ title              │
    │ sort_order           │    │ description        │
    │ description          │    │ type               │  pre_test | post_test
    └──────────┬───────────┘    │ teacher_id (FK)    │
               │                │ is_published       │
               │                │ counts_toward_grade│
               │                │ start_time/end_time│
               │                │ questions (JSON)   │
               │                │ max_attempts       │
               │                │ created_at         │
               │                └──────────┬─────────┘
     ┌─────────▼─────────┐                │
     │ questions         │                │
     ├───────────────────┤                │
     │ id (PK)           │                │
     │ title             │                │
     │ content           │                │
     │ type              │  single/multi/short_answer
     │ options (JSON)    │                │
     │ correct_answer    │                │
     │ score             │                │
     │ teacher_id (FK)   │                │
     │ objective_id (FK) │                │
     │ created_at        │                │
     │ updated_at        │                │
     └───────────────────┘                │
                                          │
     ┌────────────────────────────────────┘
     │ submissions
     ├───────────────────
     │ id (PK)
     │ student_id (FK)
     │ assessment_id (FK)
     │ attempt_number
     │ answers (JSON)
     │ score
     │ total_score
     │ submitted_at
     └───────────────────
```

### 4.2 完整 SQL DDL

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'student',
    display_name VARCHAR(100) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE teaching_classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    semester VARCHAR(50) NOT NULL,
    description TEXT,
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE class_enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL REFERENCES teaching_classes(id),
    student_id INTEGER NOT NULL REFERENCES users(id),
    enrolled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(class_id, student_id)
);

CREATE TABLE teaching_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL REFERENCES teaching_classes(id),
    title VARCHAR(200) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE learning_objectives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL REFERENCES teaching_units(id),
    title VARCHAR(200) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    description TEXT
);

CREATE TABLE questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    type VARCHAR(30) NOT NULL,
    options JSON,
    correct_answer VARCHAR(500),
    score INTEGER NOT NULL DEFAULT 2,
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    objective_id INTEGER REFERENCES learning_objectives(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL REFERENCES teaching_units(id),
    title VARCHAR(200) NOT NULL,
    description TEXT,
    type VARCHAR(20) NOT NULL,
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    is_published BOOLEAN DEFAULT 0,
    counts_toward_grade BOOLEAN DEFAULT 0,
    start_time DATETIME,
    end_time DATETIME,
    questions JSON,
    max_attempts INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(unit_id, type)
);

CREATE TABLE submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES users(id),
    assessment_id INTEGER NOT NULL REFERENCES assessments(id),
    attempt_number INTEGER NOT NULL DEFAULT 1,
    answers JSON,
    score INTEGER DEFAULT 0,
    total_score INTEGER DEFAULT 0,
    submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, assessment_id, attempt_number)
);
```

### 4.3 字段说明

| 表 | 字段 | 类型 | 说明 |
|----|------|------|------|
| users | role | VARCHAR(20) | `student` 或 `teacher` |
| teaching_classes | semester | VARCHAR(50) | 学期标识，如 `2024-秋季` |
| teaching_units | sort_order | INTEGER | 排序序号（章节号） |
| learning_objectives | sort_order | INTEGER | 目标排序序号 |
| questions | type | VARCHAR(30) | `single_choice`、`multi_choice`、`short_answer` |
| questions | options | JSON | `["A. 选项一", "B. 选项二", ...]` |
| questions | correct_answer | VARCHAR(500) | 单选: `"A"`；多选: `"A,C"`；简答: 参考答案文本 |
| assessments | type | VARCHAR(20) | `pre_test` 或 `post_test`（每单元最多各一个） |
| assessments | questions | JSON | `[1, 3, 5, 7]` — 题目ID数组，保证顺序 |
| assessments | max_attempts | INTEGER | `0` = 无限次数 |
| assessments | counts_toward_grade | BOOLEAN | 后测通常计入成绩，前测不计 |
| submissions | answers | JSON | `{"1": "A", "3": "B", "5": "学生答案文本"}` |
| submissions | attempt_number | INTEGER | 从 1 开始递增 |

---

## 5. 路由 API 表

| 方法 | 路径 | 认证 | 角色 | 功能描述 | 模板 |
|------|------|------|------|----------|------|
| GET,POST | `/login` | 否 | 任意 | 用户登录 | `login.html` |
| GET,POST | `/register` | 否 | 任意 | 用户注册 | `register.html` |
| GET | `/logout` | 是 | 任意 | 用户登出 | 重定向 |
| GET | `/student/dashboard` | 是 | student | 学习中心 | `student/dashboard.html` |
| GET | `/student/assessment/<id>` | 是 | student | 测评详情 | `student/assessment_detail.html` |
| GET,POST | `/student/assessment/<id>/take` | 是 | student | 答题 + 提交后清除缓存 | `student/test.html` |
| GET | `/student/submission/<id>` | 是 | student | 单次结果 | `student/result.html` |
| GET | `/student/growth` | 是 | student | 成长轨迹（复用 shared/student_detail） | `shared/student_detail.html` |
| GET | `/admin/dashboard` | 是 | teacher | 后台首页 | `admin/dashboard.html` |
| GET | `/admin/classes` | 是 | teacher | 教学班列表 | `admin/classes.html` |
| GET | `/admin/classes/<id>` | 是 | teacher | 班级详情 + 增益汇总 | `admin/class_detail.html` |
| POST | `/admin/classes/<id>/units/new` | 是 | teacher | 新增教学单元 | 重定向 |
| POST | `/admin/units/<id>/edit` | 是 | teacher | 编辑教学单元 | 重定向 |
| POST | `/admin/units/<id>/delete` | 是 | teacher | 删除教学单元 | 重定向 |
| POST | `/admin/units/<id>/move-up` | 是 | teacher | 单元上移（AJAX） | JSON |
| POST | `/admin/units/<id>/move-down` | 是 | teacher | 单元下移（AJAX） | JSON |
| GET | `/admin/questions` | 是 | teacher | 题库列表 | `admin/questions.html` |
| GET,POST | `/admin/questions/new` | 是 | teacher | 创建题目 | `admin/question_form.html` |
| GET,POST | `/admin/questions/<id>/edit` | 是 | teacher | 编辑题目 | `admin/question_form.html` |
| POST | `/admin/questions/<id>/delete` | 是 | teacher | 删除题目 | 重定向 |
| GET | `/admin/students` | 是 | teacher | 学生列表 | `admin/students.html` |
| GET,POST | `/admin/students/new` | 是 | teacher | 添加学生 | `admin/student_form.html` |
| GET | `/admin/students/<id>` | 是 | teacher | 学生详情（shared 模板） | `shared/student_detail.html` |
| GET | `/admin/assessments` | 是 | teacher | 测评列表 | `admin/assessments.html` |
| GET,POST | `/admin/assessments/new` | 是 | teacher | 创建测评 | `admin/assessment_form.html` |
| GET,POST | `/admin/assessments/<id>/edit` | 是 | teacher | 编辑测评 | `admin/assessment_form.html` |
| POST | `/admin/assessments/<id>/publish` | 是 | teacher | 发布/取消发布 + 清除缓存 | 重定向 |
| POST | `/admin/assessments/<id>/delete` | 是 | teacher | 删除测评 + 清除缓存 | 重定向 |
| GET | `/admin/assessments/<id>/submissions` | 是 | teacher | 测评提交列表 | `admin/assessment_submissions.html` |
| GET,POST | `/admin/grade/<submission_id>` | 是 | teacher | 简答题批改 | `admin/grade.html` |
| GET | `/admin/export/assessment/<id>` | 是 | teacher | 导出测评成绩 | CSV 下载 |
| GET | `/admin/export/student/<id>` | 是 | teacher | 导出学生轨迹 | CSV 下载 |

---

## 6. 关键业务逻辑

### 6.1 自动判分算法

```
function auto_grade(submission):
    for question in assessment.get_questions():
        student_answer = submission.answers.get(str(question.id), '')
        
        if question.type == "single_choice":
            if student_answer.strip().upper() == question.correct_answer.strip().upper():
                score += question.score
                
        elif question.type == "multi_choice":
            correct_set = set(question.correct_answer.split(",")) - {''}
            student_set = set(student_answer.split(",")) if student_answer else set()
            if correct_set and correct_set == student_set:
                score += question.score
                
        elif question.type == "short_answer":
            score += 0    # 标记为待人工批改
    
    total = sum(q.score for q in assessment.get_questions())
    return score, total
```

### 6.2 测评有效期检查

```
function is_open(assessment):
    if not assessment.is_published:
        return False
    now = datetime.now(timezone.utc)
    if assessment.start_time and now < ensure_aware(assessment.start_time):
        return False
    if assessment.end_time and now > ensure_aware(assessment.end_time):
        return False
    return True
```

### 6.3 多次提交管理

```
function create_submission(student, assessment, answers):
    existing_count = count_submissions(student, assessment)
    
    if assessment.max_attempts > 0 and existing_count >= assessment.max_attempts:
        flash("已达到最大提交次数")
        redirect to dashboard
    
    submission = Submission(
        student_id = student.id,
        assessment_id = assessment.id,
        attempt_number = existing_count + 1,
        answers = answers
    )
    db.session.add(submission); db.session.commit()
    submission.grade(); db.session.commit()
    
    // 清除成长轨迹缓存，确保学生刷新后看到最新数据
    cache.delete_memoized(build_student_growth_context)
    cache.delete_memoized(class_gain_summary)
    
    redirect to submission_result
```

### 6.4 学习增益计算 (services/gain.py)

```
score_rate(submission)           → score / total_score × 100（None 安全）
absolute_gain(pre_rate, post_rate) → post_rate - pre_rate
normalized_gain(pre_rate, post_rate) → (post - pre) / (100 - pre)  // Hake g-factor

best_submission(submissions)     → 得分率最高的提交
objective_breakdown(submission, objectives) → 每个学习目标的得分率详情

_bulk_load_units_data(units, student_ids)  → 一次查询预载 assessments / objectives / questions / submissions
unit_gain_for_student_cached(unit, student_id, preloaded) → 单学生单单元增益（使用预载数据）

class_gain_summary(teaching_class, student_ids) → 班级增益汇总
    @cache.memoize(timeout=60)    ← 60 秒缓存
    遍历每单元每学生，聚合 avg_absolute_gain / avg_normalized_gain
```

### 6.5 成长轨迹数据构建 (services/growth.py)

```
build_student_growth_context(student_id, class_ids)
    @cache.memoize(timeout=60)    ← 60 秒缓存

    返回统一 schema：
    {
        unit_reports:   [{unit, pre_rate, post_rate, absolute_gain, normalized_gain,
                          class_name, chapter_number, chapter_label, unit_title, ...}],
        chart_items:    [{group_type, group_id, pre_rate, post_rate, display_label, ...}],
        chart_payload:  [{group_type, group_id, type, pct, ...}, ...],  // 统一格式，前端 filter
        submissions:    [Submission, ...],   // joinedload(Submission.assessment) 预载
        has_data:       bool,
        // 学情分析字段（2026-06 新增）
        avg_assessment_rate: float | None,   // 所有测评平均得分率
        avg_pre_rate:        float | None,   // 前测平均得分率
        avg_post_rate:       float | None,   // 后测平均得分率
        avg_gain:            float | None,   // 单元平均绝对增益
        risk_level:          str,            // 风险等级：预警/预警（有进步）/待提升/待提升（有进步）/进步显著/正常
        recommendations:     [str],          // 个性化教学建议列表
        weak_units:          [dict],         // 薄弱单元（post_rate < 60，最多5个，按得分率升序）
        trend_series:        [float],        // 所有测评得分率序列
    }

weak_units 每个元素包含：unit, class_name, chapter_number, chapter_label, unit_title, pre_rate, post_rate
risk_level 判定逻辑：后测绝对值优先（<60 预警，<75 待提升），同时考虑增益（≥10 标注"有进步"）
recommendations 生成规则：有薄弱单元时建议优先复习；后测≥前测且≥60 时鼓励保持节奏

chart_payload 中每条记录有 group_type 字段：
  - 'unit': 按教学单元分组（前测/后测百分比）
  - 'assessment': 按测评分组（单个测评的结果）

前端 _growth_chart.html 根据 group_type 过滤渲染，支持下拉框切换分组方式。
```

### 6.6 查询缓存策略

| 缓存位置 | 装饰器 | TTL | 清除时机 |
|----------|--------|-----|----------|
| `build_student_growth_context` | `@cache.memoize(60)` | 60s | 学生提交测评、教师发布/删除/编辑测评、教师创建学生 |
| `class_gain_summary` | `@cache.memoize(60)` | 60s | 学生提交测评、教师创建/编辑/发布/删除测评 |

清除方式：`cache.delete_memoized(func)` 清除该函数全部缓存项，下一请求重新计算。

---

## 7. ORM Relationship 配置

所有关系使用 `lazy='select'`（返回 list，模板可直接 `|length`），排序由 `order_by` 参数控制：

| 模型 | relationship | 配置 |
|------|-------------|------|
| TeachingClass | `.units` | `lazy='select', order_by='TeachingUnit.sort_order'` |
| TeachingClass | `.enrollments` | 默认 backref |
| TeachingUnit | `.objectives` | `lazy='select', order_by='LearningObjective.sort_order'` |
| TeachingUnit | `.assessments` | `lazy='select'` |
| LearningObjective | `.questions` | `lazy='select'` |
| Submission | `.assessment` | 查询时 `joinedload(Submission.assessment)` |

---

## 8. 模板继承树

```
base.html (Bootstrap 5 + ECharts 本地 static, 导航栏, flash消息)
├── login.html
├── register.html
├── student/
│   ├── dashboard.html              — 教学班卡片 + 单元测评状态
│   ├── assessment_detail.html      — 测评信息 + 历史提交表格
│   ├── test.html                   — 答题表单（单选/多选/简答）
│   └── result.html                 — 得分摘要 + 逐题反馈
├── shared/
│   ├── _growth_chart.html          — ECharts 图表 JS（include 引入）
│   └── student_detail.html         — 学生详情 + 学情标签 + 得分率卡片 + 教学建议 + 薄弱单元 + 成长轨迹图表 + 提交记录（教师 & 学生共用）
└── admin/
    ├── dashboard.html               — 统计卡片 + 教学班概览 + 测评分布饼图 + 快捷导航
    ├── classes.html                 — 教学班卡片网格
    ├── class_detail.html            — 班级详情 + 增益汇总表
    ├── questions.html               — 题库表格 + 分页
    ├── question_form.html           — 题目创建/编辑表单
    ├── students.html                — 学生表格
    ├── student_form.html            — 添加学生表单
    ├── assessments.html             — 测评卡片网格
    ├── assessment_form.html         — 测评创建/编辑 + 题目选择器
    ├── assessment_submissions.html  — 提交列表表格
    └── grade.html                   — 简答题批改表单
```

---

## 9. 安全设计

| 安全机制 | 实现方式 |
|----------|----------|
| 密码存储 | `werkzeug.security.generate_password_hash()` — 默认 scrypt 算法 |
| 密码验证 | `werkzeug.security.check_password_hash()` — 常数时间比较 |
| 会话管理 | `flask_login.LoginManager` — 服务端 session cookie |
| CSRF 保护 | `flask_wtf.FlaskForm` — 自动在每个表单注入 CSRF token |
| SQL 注入 | SQLAlchemy ORM — 参数化查询 |
| 角色权限 | `student_required` 装饰器检查 `role == 'student'`；`teacher_required` 检查 `role == 'teacher'`；非匹配角色返回 403 |
| 数据隔离 | 学生只能查看自己的提交和已选课程；教师只能管理自己的教学班、题目和测评 |

---

## 10. 部署指南

### 一键启动

```bash
git clone <repo-url>
cd eduscore-tracker
bash run.sh          # 正式模式（保留现有数据库）
# 或
bash run.sh demo     # 演示模式（重建数据库 + 演示数据）
```

启动后访问 `http://localhost:5001`

### 启动模式

| 模式 | 行为 | 适用场景 |
|------|------|----------|
| 正式模式 | 保留现有数据库，安全初始化 | 日常开发、联调、正式部署 |
| 演示模式 | 重建数据库并写入完整演示数据 | 演示、截图、验收 |

### 演示账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 教师 | teacher | teacher123 |
| 学生 | student1 | student123 |

### 前端静态资源（本地化，无外部依赖）

| 资源 | 本地路径 |
|------|----------|
| Bootstrap CSS | `static/bootstrap.min.css` |
| Bootstrap JS | `static/bootstrap.bundle.min.js` |
| Bootstrap Icons | `static/bootstrap-icons.css` + `static/fonts/` |
| ECharts | `static/echarts.min.js` |

### Python 包镜像

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 11. AI 复刻指令

将本节直接作为 prompt 喂给 AI 编码助手，按阶段执行：

### 阶段一：项目骨架
1. 创建项目目录结构（`app/`, `templates/`, `static/`, `scripts/`, `docs/`, `tests/`, `instance/`）
2. 创建 `.gitignore`（`venv/`, `*.db`, `__pycache__/`, `*.pyc`, `.env`）
3. 创建 `requirements.txt`（Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF, WTForms, Flask-Caching, email-validator）
4. 创建 `app/config.py`（SECRET_KEY, SQLite URI → `instance/eduscore.db`, CACHE_TYPE=SimpleCache）
5. 创建 `app/extensions.py`（`db = SQLAlchemy()`, `cache = Cache()`）
6. 创建 `app/models.py`（8 张表完整定义 + relationships）
7. 创建 `app/app.py`（Flask 工厂函数，注册蓝图，`db.init_app(app)`, `cache.init_app(app)`, `db.create_all()`）

### 阶段二：认证系统
8. 创建 `app/forms.py`（LoginForm, RegisterForm, TeachingClassForm, TeachingUnitForm, LearningObjectiveForm, QuestionForm, AssessmentForm, StudentCreateForm, GradingForm）
9. 创建 `app/auth.py`（LoginManager, user_loader, login/logout/register 路由）
10. 创建 `templates/base.html`（Bootstrap 5 母版 + 本地 static 引用 + 导航栏 + flash 消息）
11. 创建 `templates/login.html`（居中登录卡片）
12. 创建 `templates/register.html`（注册表单）

### 阶段三：学生端
13. 创建 `app/services/gain.py`（score_rate, absolute_gain, normalized_gain, best_submission, _bulk_load_units_data, unit_gain_for_student, class_gain_summary → @cache.memoize(60)）
14. 创建 `app/services/growth.py`（build_student_growth_context → @cache.memoize(60)，统一 chart_payload 含 unit/assessment 两种 group_type）
15. 创建 `app/views/student.py`（Blueprint, student_required 装饰器, 7 个路由：dashboard, assessment_detail, take_assessment, submission_result, growth）
16. 创建 `templates/student/dashboard.html`
17. 创建 `templates/student/assessment_detail.html` + `test.html` + `result.html`

### 阶段四：教师后台
18. 创建 `app/views/admin/` 子包（`__init__.py` 定义 Blueprint + teacher_required 装饰器，按功能域拆分 classes.py / questions.py / students.py / assessments.py / exports.py，各文件包含对应路由 + 缓存清除调用）
19. 创建 `templates/admin/dashboard.html`
20. 创建 `templates/admin/classes.html` + `class_detail.html`（教学班管理）
21. 创建 `templates/admin/questions.html` + `question_form.html`（题库 CRUD）
22. 创建 `templates/admin/students.html` + `student_form.html`（学生管理）
23. 创建 `templates/admin/assessments.html` + `assessment_form.html` + `assessment_submissions.html`（测评管理）
24. 创建 `templates/admin/grade.html`（简答题批改）

### 阶段五：共享与数据
25. 创建 `templates/shared/_growth_chart.html`（ECharts JS，buildAssessmentGroups/buildUnitGroups 双模式，支持分组下拉框切换）
26. 创建 `templates/shared/student_detail.html`（学生详情 + 成长轨迹 + 提交记录，通过 back_url + current_user.role 区分教师/学生视图）
27. 创建 `scripts/init_db.py` + `seed_data.py` + `demo_data.py` + `rebuild_db.py`
28. 创建 `run.sh`（一键启动，支持 formal/demo 模式）
29. 创建 `static/` 目录，下载 Bootstrap 5.3 CSS/JS、Bootstrap Icons CSS + 字体文件、ECharts 5 到本地；创建 `static/style.css`（自定义样式）

### 阶段六：测试
30. 创建 `tests/conftest.py`（fixtures: app, client, db, teacher_id, student_id, teaching_class_id, unit_id, objective_id, question_id, assessment_id）
31. 创建 `tests/test_models.py`（User 密码哈希, Submission 自动判分, 唯一约束）
32. 创建 `tests/test_auth.py`（登录成功/失败、登出、403 保护）
33. 创建 `tests/test_student.py`（dashboard 访问、答题流程、多次提交限制）
34. 创建 `tests/test_admin.py`（教师 CRUD 操作：创建班级/题目/测评/学生、批改、导出 CSV）
