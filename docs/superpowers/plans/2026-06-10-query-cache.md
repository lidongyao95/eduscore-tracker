# Query Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对 `build_student_growth_context` 和 `class_gain_summary` 两个重计算函数加内存缓存，写操作时自动清除，重复访问同一页面 0 条 SQL。

**Architecture:** Flask-Caching SimpleCache（内存 dict + TTL），通过 `@cache.memoize(60)` 装饰两个服务函数，写操作点调用 `cache.delete_memoized(...)` 批量清除。不引入外部服务。

**Tech Stack:** Flask-Caching (SimpleCache backend)

---

### Task 1: 安装 Flask-Caching 依赖

**Files:**
- Modify: `requirements.txt:7`

- [ ] **Step 1: 添加依赖**

```
Flask-Caching
```

- [ ] **Step 2: 安装**

```bash
pip install Flask-Caching --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet
```

- [ ] **Step 3: 验证安装**

```bash
python3 -c "from flask_caching import Cache; print('OK')"
```

Expected: `OK`

---

### Task 2: 初始化 Cache 扩展

**Files:**
- Modify: `app/extensions.py:1-3`
- Modify: `app/app.py:3-26`

- [ ] **Step 1: 在 extensions.py 初始化 Cache**

`app/extensions.py` 当前内容：
```python
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()
```

改为：
```python
from flask_sqlalchemy import SQLAlchemy
from flask_caching import Cache


db = SQLAlchemy()
cache = Cache()
```

- [ ] **Step 2: 在 app.py 注册 cache**

`app/app.py` 的 `create_app()` 函数中，在 `db.init_app(app)` 之后添加 `cache.init_app(app)`：

在 `db.init_app(app)` 行后插入：
```python
    cache.init_app(app)
```

同时需要在文件顶部 import cache。当前 `app.py` 顶部：
```python
from flask import Flask, redirect, url_for
from pathlib import Path
from .config import Config
from .extensions import db
```

改为：
```python
from flask import Flask, redirect, url_for
from pathlib import Path
from .config import Config
from .extensions import db, cache
```

- [ ] **Step 3: 验证 Flask 启动无报错**

```bash
cd /sessions/6a28ba4c8e0916bd26d3579b/workspace && python3 -c "
from app.app import create_app
app = create_app()
print('App created OK')
"
```

Expected: `App created OK`

---

### Task 3: 缓存 build_student_growth_context

**Files:**
- Modify: `app/services/growth.py:1-6`

- [ ] **Step 1: 添加 import 和装饰器**

`app/services/growth.py` 顶部 import 区添加：
```python
from ..extensions import cache
```

`build_student_growth_context` 函数定义前加装饰器。当前第 118 行：
```python
def build_student_growth_context(student_id, class_ids=None):
```

改为：
```python
@cache.memoize(timeout=60)
def build_student_growth_context(student_id, class_ids=None):
```

注意：`class_ids` 默认值需要是可 hashable 的类型。当前代码传入的是 list。`cache.memoize` 会用 `repr()` 序列化参数，list 的 `repr()` 能正常区分不同值。但如果传入 `None` 或相同的 list，缓存键一致，行为正确。

- [ ] **Step 2: 确认 import 路径正确**

`app/services/growth.py` 当前已有的 import：
```python
import logging
from ..models import TeachingClass, TeachingUnit
from .gain import unit_gain_for_student_cached, score_rate, best_submission, _bulk_load_units_data
```

新增一行在 logging 之后：
```python
from ..extensions import cache
```

---

### Task 4: 缓存 class_gain_summary

**Files:**
- Modify: `app/services/gain.py:227`

- [ ] **Step 1: 添加 import 和装饰器**

`app/services/gain.py` 顶部无 import 区（纯模块级函数），在函数定义上方添加 import 和装饰器。当前第 227 行：
```python
def class_gain_summary(teaching_class, student_ids):
```

改为：
```python
from ..extensions import cache


@cache.memoize(timeout=60)
def class_gain_summary(teaching_class, student_ids):
```

- [ ] **Step 2: 验证 import 循环**

确认 `services/gain.py` → `extensions.py` 无循环依赖。`extensions.py` 只 import `flask_sqlalchemy` 和 `flask_caching`，不依赖任何项目模块。无循环依赖风险。

---

### Task 5: 学生提交测评后清除 growth 缓存

**Files:**
- Modify: `app/views/student.py:125-130`

- [ ] **Step 1: 添加 cache import**

`app/views/student.py` 顶部 import 区（第 1-10 行）添加：
```python
from ..extensions import cache
```

当前 import：
```python
import json
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from functools import wraps
from ..models import (
    db, Assessment, Submission,
    TeachingClass, ClassEnrollment,
)
from ..services.gain import unit_gain_for_student
from ..services.growth import build_student_growth_context
```

加入 `cache` 和 `class_gain_summary`：
```python
import json
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from functools import wraps
from ..models import (
    db, Assessment, Submission,
    TeachingClass, ClassEnrollment,
)
from ..services.gain import unit_gain_for_student, class_gain_summary
from ..services.growth import build_student_growth_context
from ..extensions import cache
```

- [ ] **Step 2: 在提交成功后清除缓存**

`take_assessment` 函数中，POST 提交成功后（当前第 125-130 行）：
```python
        db.session.add(submission)
        db.session.commit()
        submission.grade()
        db.session.commit()

        flash(f'第 {attempt_number} 次提交成功！', 'success')
        return redirect(url_for('student.submission_result', submission_id=submission.id))
```

改为在 `db.session.commit()` 之后、`flash` 之前添加缓存清除：
```python
        db.session.add(submission)
        db.session.commit()
        submission.grade()
        db.session.commit()

        # 清除成长轨迹缓存，让学生刷新后看到最新数据
        cache.delete_memoized(build_student_growth_context)
        cache.delete_memoized(class_gain_summary)

        flash(f'第 {attempt_number} 次提交成功！', 'success')
        return redirect(url_for('student.submission_result', submission_id=submission.id))
```

---

### Task 6: 教师管理操作后清除缓存

**Files:**
- Modify: `app/views/admin.py:1-11`

- [ ] **Step 1: 添加 cache import**

`app/views/admin.py` 顶部 import 区添加 `cache`：
```python
from ..extensions import cache
from ..services.gain import class_gain_summary
from ..services.growth import build_student_growth_context
```

当前第 9 行：
```python
from ..services.gain import class_gain_summary
from ..services.growth import build_student_growth_context
```

改为：
```python
from ..services.gain import class_gain_summary
from ..services.growth import build_student_growth_context
from ..extensions import cache
```

- [ ] **Step 2: 测评发布/取消后清除**

`toggle_publish` 函数（第 323-333 行），在 `db.session.commit()` 后加清除：
```python
    db.session.commit()
    cache.delete_memoized(class_gain_summary)
    cache.delete_memoized(build_student_growth_context)
    status = '已发布' if assessment.is_published else '已取消发布'
```

- [ ] **Step 3: 测评删除后清除**

`delete_assessment` 函数（第 336-347 行），在 `db.session.commit()` 后加清除：
```python
    db.session.commit()
    cache.delete_memoized(class_gain_summary)
    cache.delete_memoized(build_student_growth_context)
    flash('测评已删除', 'info')
```

- [ ] **Step 4: 测评创建后清除**

`create_assessment` 函数（第 262-291 行），在 `db.session.commit()` 后加清除：
```python
        db.session.commit()
        cache.delete_memoized(class_gain_summary)
        flash('测评创建成功', 'success')
```

- [ ] **Step 5: 测评编辑后清除**

`edit_assessment` 函数（第 294-321 行），在 `db.session.commit()` 后加清除：
```python
        db.session.commit()
        cache.delete_memoized(class_gain_summary)
        cache.delete_memoized(build_student_growth_context)
        flash('测评更新成功', 'success')
```

- [ ] **Step 6: 学生创建后清除（可选，仅清除 growth）**

`create_student` 函数（第 226-244 行），在 `db.session.commit()` 后：
```python
        db.session.commit()
        cache.delete_memoized(build_student_growth_context)
        flash('学生创建成功', 'success')
```

---

### Task 7: 最终验证

- [ ] **Step 1: 验证无 import 错误**

```bash
cd /sessions/6a28ba4c8e0916bd26d3579b/workspace && python3 -c "
from app.app import create_app
app = create_app()
print('App with cache OK')
"
```

Expected: `App with cache OK`

- [ ] **Step 2: 验证缓存生效**

```bash
cd /sessions/6a28ba4c8e0916bd26d3579b/workspace && python3 -c "
from app.app import create_app
from app.services.growth import build_student_growth_context
app = create_app()
with app.app_context():
    r1 = build_student_growth_context(1, [1])
    r2 = build_student_growth_context(1, [1])
    assert r1 is r2, 'Cache should return same object'
    print('Cache hit OK')
"
```

Expected: `Cache hit OK`

- [ ] **Step 3: 验证清除生效**

```bash
cd /sessions/6a28ba4c8e0916bd26d3579b/workspace && python3 -c "
from app.app import create_app
from app.services.growth import build_student_growth_context
from app.extensions import cache
app = create_app()
with app.app_context():
    r1 = build_student_growth_context(1, [1])
    cache.delete_memoized(build_student_growth_context)
    r2 = build_student_growth_context(1, [1])
    assert r1 is not r2, 'Cache should return new object after delete'
    print('Cache eviction OK')
"
```

Expected: `Cache eviction OK`
