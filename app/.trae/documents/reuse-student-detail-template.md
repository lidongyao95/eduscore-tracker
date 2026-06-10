# 学生侧和教师侧完全复用同一模板（仅返回按钮不同）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 学生侧和教师侧共用一个模板 `admin/student_detail.html`，通过一个 `back_url` 变量区分返回按钮目标，零重复代码。

**Architecture:** 两个路由构造完全相同的数据、渲染同一个模板，唯一差异是传入的 `back_url` 变量。模板中的返回按钮从硬编码 `url_for('admin.students')` 改为 `{{ back_url }}`。

**Tech Stack:** Flask

---

## 改动

### 改动 1：管理员路由新增 `back_url`
**文件:** `views/admin.py` 第 218-231 行附近
```python
        back_url=url_for('admin.students'),
```
加到 `render_template()` 参数中。

### 改动 2：学生侧路由改写
**文件:** `views/student.py` 第 180-196 行
- 删除旧的 `student/growth.html` 引用和裁剪逻辑
- 改为与教师端完全相同的 `render_template('admin/student_detail.html', ...)`
- 唯一差异：`back_url=url_for('student.dashboard')`

### 改动 3：（模板侧，需手动改一行）
`admin/student_detail.html` 中返回按钮从硬编码改为 `{{ back_url }}`

---

## 实现步骤

### Task 1: 管理员路由加 `back_url`

**Files:**
- Modify: `views/admin.py:221-231`

- [ ] **Step 1: 在 `render_template` 调用中加一行**

```python
    return render_template(
        'admin/student_detail.html',
        student=student,
        submissions=growth['submissions'],
        chart_payload=growth['chart_payload'],
        has_data=growth['has_data'],
        unit_reports=growth['unit_reports'],
        chart_items=growth['chart_items'],
        back_url=url_for('admin.students'),
    )
```

### Task 2: 学生侧路由改写，完全复用

**Files:**
- Modify: `views/student.py:180-196`

- [ ] **Step 1: 替换整个 growth 路由**

```python
@student_bp.route('/growth')
@student_required
def growth():
    class_ids = _enrolled_class_ids(current_user.id)
    growth_data = build_student_growth_context(current_user.id, class_ids)

    return render_template(
        'admin/student_detail.html',
        student=current_user,
        submissions=growth_data['submissions'],
        chart_payload=growth_data['chart_payload'],
        has_data=growth_data['has_data'],
        unit_reports=growth_data['unit_reports'],
        chart_items=growth_data['chart_items'],
        back_url=url_for('student.dashboard'),
    )
```

### Task 3: 模板手动改动（一行）

**Files:**
- Modify: `templates/admin/student_detail.html`

- [ ] **Step 1: 将返回按钮的 href 从硬编码改为变量**

（这一行在模板中，需要用户手动操作）

```html
<!-- 改前 -->
<a href="{{ url_for('admin.students') }}">返回学生列表</a>

<!-- 改后 -->
<a href="{{ back_url }}">返回</a>
```

`back_url` 在教师端渲染为 `/admin/students`，学生端渲染为 `/student/dashboard`。

---

## 验证

1. 教师端 `/admin/students/<id>` → 返回按钮跳转到 `/admin/students`
2. 学生端 `/student/growth` → 返回按钮跳转到 `/student/dashboard`
3. 图表数据完全一致
4. `student/growth.html` 不再被引用，可删除
