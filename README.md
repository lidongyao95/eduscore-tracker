# EduScore Tracker — 高校教学前测后测测评平台

一个轻量级的高校教学测评系统。教师发布前测/后测评测任务，学生多次提交作答，系统自动判分并追踪成长轨迹。

## 特性

- **前测后测** — 学期初摸底 + 学期末评测，对比学生学习效果
- **多次提交** — 同一测评允许多次作答，记录每次分数，追踪进步
- **成长轨迹** — ECharts 可视化图表展示学习曲线，支持按单元/测评双模式切换
- **学情分析** — 自动计算得分率、增益、风险等级与薄弱单元，输出个性化教学建议
- **自动判分** — 单选题/多选题自动判分，简答题支持教师人工批改
- **班级增益汇总** — 班级视角的绝对增益与 Hake g 对比表
- **数据导出** — 一键导出学生成绩 CSV
- **零配置部署** — SQLite 数据库，一行命令启动，无需安装 MySQL/PostgreSQL
- **AI 可复刻** — 内置 ARCHITECTURE.md 技术文档，可喂给任何 AI 助手独立重建系统
- **架构可视化** — 根目录 `architecture-diagram.html` 可直接在浏览器打开查看系统架构图

## 技术栈

| 组件 | 技术 | 备注 |
|------|------|------|
| 后端 | Python 3 + Flask | |
| 数据库 | SQLite | 零配置，部署即用 |
| 前端 | Bootstrap 5 | BootCDN 国内镜像，无需翻墙 |
| 图表 | ECharts 5 | 中文文档完善，BootCDN 直连 |
| 认证 | Flask-Login | |
| 表单 | Flask-WTF | 内建 CSRF 保护 |

## 快速开始

```bash
# 克隆项目
git clone <your-repo-url>
cd eduscore-tracker

# 正式模式启动
# 仅启动应用，不主动重建数据库，也不写入演示数据
bash run.sh

# 演示模式启动
# 会重建数据库并写入更丰富的演示数据
bash run.sh demo
```

启动后访问 http://localhost:5001

### 启动模式说明

| 模式 | 行为 | 适用场景 |
|------|------|----------|
| 正式模式 | 保留现有数据库，执行安全初始化，确保表结构和默认教师账号存在 | 日常开发、联调、正式部署 |
| 演示模式 | 重建数据库并写入完整演示数据 | 演示、截图、验收、功能浏览 |

### 演示账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 教师 | teacher | teacher123 |
| 学生 | student1 | student123 |

## 项目结构

```
eduscore-tracker/
├── app/
│   ├── __init__.py
│   ├── app.py                 # Flask 入口
│   ├── config.py              # 配置
│   ├── models.py              # 数据库模型
│   ├── forms.py               # WTForms 表单
│   ├── auth.py                # 认证模块
│   ├── extensions.py          # 扩展初始化
│   ├── services/
│   │   ├── gain.py            # 增益计算
│   │   └── growth.py          # 成长曲线
│   └── views/
│       ├── student.py         # 学生端路由
│       └── admin.py           # 教师后台路由
├── templates/                 # Jinja2 模板
├── static/                    # CSS/JS
├── docs/
│   └── ARCHITECTURE.md        # AI 可复刻技术文档
├── run.sh                     # 一键启动脚本
├── requirements.txt           # 依赖列表
└── scripts/                   # 辅助脚本
    ├── init_db.py             # 正式模式初始化
    ├── seed_data.py           # 最小种子数据
    ├── demo_data.py           # 演示数据
    └── rebuild_db.py          # 重建数据库
```

## AI 复刻

如果你想用 AI 编码助手（Trae、Cursor、Copilot 等）独立重建此系统，将 `docs/ARCHITECTURE.md` 作为 prompt 喂给 AI 即可。文档包含完整的数据库设计、API 路由表、业务逻辑伪代码和分阶段实施指令。

## 扩展方向

- PostgreSQL 替代 SQLite（高并发场景）
- 批量导入学生（CSV/Excel）
- 题库分类标签系统
- 接入 Superset 深度分析看板

## License

MIT
