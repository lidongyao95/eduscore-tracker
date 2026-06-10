# 统一学生侧与教师侧成长曲线渲染

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 学生侧和教师侧的成长曲线使用完全相同的数据结构和渲染逻辑，消除模板差异导致的"教师侧正常、学生侧无数据"问题。

**Architecture:** 创建独立的 JSON API 端点 `/api/growth/<student_id>`，返回统一格式的 `chart_payload`。学生侧和教师侧模板通过 AJAX 调用同一个 API 获取数据、用同一段 JS 渲染图表。模板文件不在工作区中，后端变更为可控范围。同时保留模板变量的注入作为 fallback，确保不破坏现有模板。

**Tech Stack:** Flask (JSON endpoint), 现有模板保持不变（仅调整 JS 引用）

---

## 现状分析

### 教师端（正常）
- 路由：`admin/student_detail/<id>` → `admin/student_detail.html`
- 传参：`chart_payload`, `has_data`, `unit_reports`, `chart_items`, `student`, `submissions`
- `chart_payload` 包含 unit + assessment 两种 `group_type` 的数据点（13 个字段），模板 JS 过滤 `group_type`

### 学生端（无数据）
- 路由：`student/growth` → `student/growth.html`
- 传参：`**context` 解包 → `chart_payload`, `has_data`, `unit_reports`, `chart_items`, `submissions`, `chart_mode`
- `chart_payload` 被裁剪为只含 unit 点、6 个字段
- 日志确认数据正确：9 个 unit 点，pct 值正常 → **问题在模板文件本身的 JS 渲染逻辑或变量引用方式**

### 根因推断
模板文件不在工作区中无法直接读取，但从日志确认后端数据完全正确。问题只能是模板侧的 JS 图表初始化方式与教师侧不同，或模板期望的变量名/数据结构与传入的不一致。

### 统一方案评估

| 方案 | 优点 | 缺点 |
|------|------|------|
| A. 修改学生模板 | 改动最小 | 模板不在工作区，无法修改 |
| B. 创建 JSON API + 统一 JS | 完全可控，两个页面共享同一渲染逻辑 | 需要后端新增路由 |
| C. 让学生路由直接复用教师模板变量名 | 极简 | 无法控制模板内部逻辑 |

**选择方案 B**：JSON API 是我们可以完全控制的后端代码，且天然消除模板差异——两个页面用同样的 Ajax 调用同样的端点。

---

## 改动清单

### 改动 1：新增 `/api/growth/<student_id>` JSON 端点
- 文件：`views/student.py`（或新建 `views/api.py`）
- 调用 `build_student_growth_context`，返回完整 JSON

### 改动 2：精简 `student/growth` 路由
- 文件：`views/student.py:180-208`
- 去掉裁剪 `chart_payload` 的逻辑，改为直接传入完整数据，新增 `chart_json_endpoint` URL 供模板 JS 使用

### 改动 3：新增 `views/api.py` 蓝图
- 文件：`views/api.py`（新建）
- 注册到 `app.py`

---

## 实现步骤

### Task 1: 创建 API 蓝图文件

**Files:**
- Create: `views/api.py`
- Modify: `views/__init__.py`

- [ ] **Step 1: 创建 `views/api.py`**

```python
"""JSON API endpoints for growth chart data."""
from flask import Blueprint, jsonify, current_app
from flask_login import login_required, current_user

from ..models import ClassEnrollment
from ..services.growth import build_student_growth_context

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/growth/<int:student_id>')
@login_required
def growth_data(student_id):
    """Return unified chart_payload JSON for a student.

    Access control: the requesting user must be either the student themselves
    or a teacher.
    """
    if current_user.role == 'student' and current_user.id != student_id:
        return jsonify({'error': 'forbidden'}), 403

    enrolled_rows = ClassEnrollment.query.filter_by(student_id=student_id).all()
    class_ids = [r.class_id for r in enrolled_rows]

    growth = build_student_growth_context(student_id, class_ids)

    # Count by group_type for diagnostics
    unit_count = sum(1 for p in growth['chart_payload'] if p['group_type'] == 'unit')
    assessment_count = sum(1 for p in growth['chart_payload'] if p['group_type'] == 'assessment')

    current_app.logger.info(
        '[api/growth] student_id=%s unit_points=%s assessment_points=%s',
        student_id, unit_count, assessment_count,
    )

    return jsonify({
        'chart_payload': growth['chart_payload'],
        'has_data': growth['has_data'],
        'unit_reports': growth['unit_reports'],
        'chart_items': growth['chart_items'],
        'chart_mode': growth['chart_mode'],
    })
```

- [ ] **Step 2: 注册蓝图到 `app.py`**

修改 `app.py` 第 40-42 行附近：

```python
    # Register API blueprint
    from .views.api import api_bp
    app.register_blueprint(api_bp)
```

### Task 2: 精简学生端路由

**Files:**
- Modify: `views/student.py:180-208`

- [ ] **Step 1: 重写学生端 growth 路由，去掉裁剪逻辑，传入 API URL**

```python
@student_bp.route('/growth')
@student_required
def growth():
    class_ids = _enrolled_class_ids(current_user.id)
    context = build_student_growth_context(current_user.id, class_ids)

    import flask
    flask.current_app.logger.info(
        '[student/growth] student_id=%s class_ids=%s '
        'chart_payload_total=%s unit_points=%s assessment_points=%s',
        current_user.id, class_ids,
        len(context['chart_payload']),
        sum(1 for p in context['chart_payload'] if p['group_type'] == 'unit'),
        sum(1 for p in context['chart_payload'] if p['group_type'] == 'assessment'),
    )

    # Pass the API URL so the template's JS can fetch data via AJAX
    context['chart_api_url'] = url_for('api.growth_data', student_id=current_user.id)

    return render_template('student/growth.html', **context)
```

关键变化：
- 去掉 `chart_payload` 裁剪和字段过滤（那些逻辑现在移到 API 端点或由模板前端处理）
- 新增 `chart_api_url` 变量传入模板，模板 JS 改用 `fetch(chart_api_url)` 获取数据

### Task 3: 统一数据结构规范

**Files:**
- Modify: `services/growth.py`（添加文档注释，不改逻辑）

- [ ] **Step 1: 在文件顶部添加数据结构规范文档**

```python
"""
Growth trajectory data builders.

Unified chart_payload schema (every item has all 13 fields):
┌──────────────────┬─────────────────────────────────────┐
│ Field            │ Description                         │
├──────────────────┼─────────────────────────────────────┤
│ group_type       │ 'unit' | 'assessment'               │
│ group_id         │ unit.id or assessment.id            │
│ group_label      │ display label for chart axis        │
│ type             │ 'pre_test' | 'post_test'            │
│ type_order       │ 0=pre_test, 1=post_test             │
│ total            │ always 100 (percentage scale)       │
│ pct              │ score rate (0-100) or None          │
│ assessment_id    │ None for unit points                │
│ assessment_title │ None for unit points                │
│ unit_title       │ None for unit points                │
│ attempt          │ None for unit points                │
│ score            │ None for unit points                │
│ submitted_at     │ None for unit points                │
└──────────────────┴─────────────────────────────────────┘

Front-end chart rendering pseudocode:
  const payload = await fetch(chart_api_url).then(r => r.json()).chart_payload;
  // Filter by view mode:
  const points = payload.filter(p => p.group_type === currentView);
  // Group by group_label for paired bar chart:
  const groups = [...new Set(points.map(p => p.group_label))];
  // Render each group_label with pre_test bar + post_test bar.
"""
```

（添加到 `services/growth.py` 文件顶部 module docstring）

---

## 验证步骤

1. 启动应用，教师端访问 `GET /admin/students/<id>` — 图表正常（不变）
2. 学生端访问 `GET /student/growth` — 日志输出完整数据统计
3. 浏览器打开开发者工具，学生端页面加载后应看到 Ajax 请求 `GET /api/growth/<student_id>` 返回 JSON
4. JSON 响应中 `chart_payload` 包含 unit 和 assessment 数据点
5. 如果模板已更新使用 Ajax，图表正常渲染；如果模板未更新，浏览器 console 不会有 JS 错误（数据仍通过模板变量 `chart_payload` 完整传入作为 fallback）
