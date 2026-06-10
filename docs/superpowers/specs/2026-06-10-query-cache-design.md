# Query Cache — 成长轨迹 & 教学班详情缓存

## 背景

成长轨迹（`build_student_growth_context`）和教学班增益汇总（`class_gain_summary`）每次请求执行 6-10 条 SQL + 批量循环计算。SQLite 单连接，多次进出同一页面重复执行相同查询，体感延迟明显。

## 目标

- 缓存两个重计算函数的返回值，TTL 60 秒
- 写操作（提交测评、新建/编辑班级、创建学生、重建数据库）即时清除对应缓存，保证数据一致
- 零外部依赖，不引入 Redis

## 方案：Flask-Caching SimpleCache

`Flask-Caching` 的 `SimpleCache` 后端使用内存 dict + TTL，成熟稳定，无额外进程。

### 依赖

```
Flask-Caching
```

### 架构

```
extensions.py          ← 初始化 Cache 实例
services/gain.py       ← @cache.memoize(60) 装饰 class_gain_summary
services/growth.py     ← @cache.memoize(60) 装饰 build_student_growth_context
views/admin.py         ← 写操作点调用 cache.delete_memoized(…)
views/student.py       ← 写操作点调用 cache.delete_memoized(…)
```

### 缓存键设计

`@cache.memoize` 自动以函数名 + 参数值计算缓存键：

- `class_gain_summary(tc, student_ids)` → 键包含 class_id + student_ids
- `build_student_growth_context(student_id, class_ids)` → 键包含 student_id + class_ids

### 缓存清除点

| 写操作 | 清除范围 |
|--------|----------|
| 提交测评 (`student.take_assessment`) | 该学生 + 所有班级的 growth 缓存 |
| 教师创建/编辑班级 | 该班级的 gain_summary 缓存 |
| 教师创建学生 | 该学生的 growth 缓存 |
| 教师发布/取消发布测评 | 相关班级的 gain_summary + 学生 growth |
| 重建数据库脚本 | 全部缓存（`cache.clear()`） |

### 简化清除策略

为避免逐键精准清除的复杂度，采用**影响面小、易于验证**的策略：

1. 写操作调用 `cache.delete_memoized(func)` 清除该函数所有缓存 —— 一次清除全部 key
2. TTL 60 秒兜底，即使漏清也能自动过期

实际触发：提交测评 → 清除 `build_student_growth_context` 全部缓存；管理侧写操作 → 清除 `class_gain_summary` 全部缓存。

### 文件改动清单

| 文件 | 改动 |
|------|------|
| `requirements.txt` | +1 行 `Flask-Caching` |
| `app/extensions.py` | 初始化 Cache |
| `app/app.py` | `cache.init_app(app)` |
| `app/services/gain.py` | `class_gain_summary` 加 `@cache.memoize(60)` |
| `app/services/growth.py` | `build_student_growth_context` 加 `@cache.memoize(60)` |
| `app/views/student.py` | `take_assessment` 提交后清除 growth 缓存 |
| `app/views/admin.py` | 班级/测评/学生写操作后清除对应缓存 |
| `run.sh` | 安装新依赖 |

### 边界条件

- `class_gain_summary` 参数含 `TeachingClass` ORM 对象，需要 `__hash__` 和 `__eq__`。SQLAlchemy model 天然支持（以 id 判等），Flask-Caching 能正确处理
- 仅缓存读取，不缓存写入
- 单用户场景缓存命中率最高；多用户场景 60 秒 TTL 内视图一致
