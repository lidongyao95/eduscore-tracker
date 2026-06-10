"""
Demo data for eduscore-tracker (new schema).

1 teaching class, 5 units, 15 students.
Units 1-4: paired pre/post (parallel forms per learning objective).
Unit 5: post-test only (no pre-test).
"""

import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from app.models import (
    User, TeachingClass, ClassEnrollment, TeachingUnit,
    LearningObjective, Question, Assessment, Submission,
)

random.seed(42)

STUDENTS = [
    ('student1', '李小明'), ('student2', '王芳'), ('student3', '张伟'),
    ('student4', '刘洋'), ('student5', '陈静'), ('student6', '杨磊'),
    ('student7', '赵敏'), ('student8', '黄丽'), ('student9', '周强'),
    ('student10', '吴雪'), ('student11', '孙浩'), ('student12', '马超'),
    ('student13', '林婷'), ('student14', '郑凯'), ('student15', '何琳'),
]

CLASS_CONFIG = {
    'name': '2024秋 Python程序设计',
    'semester': '2024-秋季',
    'description': '面向大一新生的 Python 编程基础课程，采用教学单元前测后测跟踪学习增益。',
}

# Parallel pre/post questions per objective (different items, same learning goal)
UNITS_CONFIG = [
    {
        'title': '第1章 变量与数据类型',
        'sort_order': 1,
        'has_pre': True,
        'objectives': [
            {
                'title': '理解变量声明与赋值',
                'pre': [
                    ('变量本质', 'Python 中 x = 10 执行了什么？', 'A',
                     ['A. 创建名称并绑定对象', 'B. 声明固定类型变量', 'C. 分配内存地址', 'D. 编译为常量']),
                    ('命名规则', '以下哪个是合法变量名？', 'B',
                     ['A. 2name', 'B. student_name', 'C. class', 'D. my-var']),
                ],
                'post': [
                    ('赋值机制', '执行 a = b = [] 后，a.append(1) 会影响 b 吗？', 'A',
                     ['A. 会，同一对象', 'B. 不会，各自独立', 'C. 仅当 a is b', 'D. 抛出异常']),
                    ('标识符规则', '以下哪个变量名不合法？', 'C',
                     ['A. _count', 'B. name2', 'C. for', 'D. PI']),
                ],
            },
            {
                'title': '掌握基本数据类型',
                'pre': [
                    ('类型识别', 'type(3.14) 的结果是？', 'B',
                     ['A. int', 'B. float', 'C. str', 'D. number']),
                    ('类型转换', 'int("42") 的结果是？', 'A',
                     ['A. 42', 'B. "42"', 'C. 4.2', 'D. 报错']),
                ],
                'post': [
                    ('布尔运算', 'bool("") 的值是？', 'B',
                     ['A. True', 'B. False', 'C. None', 'D. 0']),
                    ('字符串特性', '"hello"[1:3] 的结果是？', 'C',
                     ['A. he', 'B. el', 'C. el', 'D. llo']),
                ],
            },
            {
                'title': '运用 input/output 交互',
                'pre': [
                    ('print函数', 'print("A", "B", sep="-") 输出？', 'B',
                     ['A. A B', 'B. A-B', 'C. AB', 'D. A\\nB']),
                    ('input返回', 'input() 函数的返回值类型是？', 'C',
                     ['A. int', 'B. float', 'C. str', 'D. 任意类型']),
                ],
                'post': [
                    ('格式化输出', 'f"{3:.1f}" 的结果是？', 'A',
                     ['A. 3.0', 'B. 3.1', 'C. 3', 'D. .1']),
                    ('类型转换输入', 'int(input()) 适用于？', 'B',
                     ['A. 任意输入', 'B. 数字字符串', 'C. 浮点字符串', 'D. 布尔值']),
                ],
            },
        ],
    },
    {
        'title': '第2章 条件与循环',
        'sort_order': 2,
        'has_pre': True,
        'objectives': [
            {
                'title': '编写条件分支语句',
                'pre': [
                    ('if基础', 'if x > 0: 中 x=0 时？', 'B',
                     ['A. 执行if体', 'B. 跳过if体', 'C. 报错', 'D. 返回None']),
                    ('elif逻辑', 'if/elif/else 中多个条件为真？', 'A',
                     ['A. 只执行第一个', 'B. 全部执行', 'C. 执行最后一个', 'D. 随机执行']),
                ],
                'post': [
                    ('嵌套条件', 'and 的优先级高于 or？', 'A',
                     ['A. 是', 'B. 否', 'C. 相同', 'D. 取决于版本']),
                    ('三元表达式', 'x if x>0 else 0 等价于？', 'C',
                     ['A. if-else块', 'B. switch', 'C. 简化的if-else', 'D. 循环']),
                ],
            },
            {
                'title': '使用 for 循环遍历',
                'pre': [
                    ('range用法', 'range(3) 生成？', 'B',
                     ['A. 1,2,3', 'B. 0,1,2', 'C. 0,1,2,3', 'D. 3,2,1']),
                    ('遍历列表', 'for x in [1,2]: 循环几次？', 'B',
                     ['A. 1', 'B. 2', 'C. 3', 'D. 0']),
                ],
                'post': [
                    ('enumerate', 'enumerate(["a","b"]) 第0项是？', 'A',
                     ['A. (0,"a")', 'B. ("a",0)', 'C. 0', 'D. "a"']),
                    ('嵌套循环', '二重循环各3次共执行？', 'C',
                     ['A. 3', 'B. 6', 'C. 9', 'D. 12']),
                ],
            },
            {
                'title': '使用 while 循环与 break/continue',
                'pre': [
                    ('while条件', 'while False: 循环体执行？', 'B',
                     ['A. 1次', 'B. 0次', 'C. 无限', 'D. 报错']),
                    ('break作用', 'break 的作用是？', 'A',
                     ['A. 退出循环', 'B. 跳过本次', 'C. 退出函数', 'D. 继续下次']),
                ],
                'post': [
                    ('continue作用', 'continue 的作用是？', 'B',
                     ['A. 退出循环', 'B. 跳过本次迭代', 'C. 退出程序', 'D. 重新开始']),
                    ('循环else', 'for...else 中 else 何时执行？', 'C',
                     ['A. 每次迭代', 'B. 第一次', 'C. 正常结束未break', 'D. 永不执行']),
                ],
            },
        ],
    },
    {
        'title': '第3章 函数与模块',
        'sort_order': 3,
        'has_pre': True,
        'objectives': [
            {
                'title': '定义与调用函数',
                'pre': [
                    ('def语法', '函数定义关键字是？', 'A',
                     ['A. def', 'B. func', 'C. function', 'D. fn']),
                    ('return作用', '无return语句函数返回？', 'C',
                     ['A. 0', 'B. False', 'C. None', 'D. 报错']),
                ],
                'post': [
                    ('默认参数', '默认参数应放在？', 'B',
                     ['A. 任意位置', 'B. 必选参数之后', 'C. 最前面', 'D. 不能定义']),
                    ('多返回值', 'return a, b 返回类型是？', 'C',
                     ['A. list', 'B. dict', 'C. tuple', 'D. 两个值']),
                ],
            },
            {
                'title': '理解参数传递机制',
                'pre': [
                    ('形参与实参', '函数定义中的参数称为？', 'A',
                     ['A. 形参', 'B. 实参', 'C. 全局变量', 'D. 常量']),
                    ('可变对象', '传递 list 给函数修改会影响外部？', 'A',
                     ['A. 会', 'B. 不会', 'C. 仅append', 'D. 仅pop']),
                ],
                'post': [
                    ('*args', '*args 收集？', 'B',
                     ['A. 关键字参数', 'B. 多余位置参数', 'C. 全局变量', 'D. 返回值']),
                    ('**kwargs', '**kwargs 的类型是？', 'C',
                     ['A. list', 'B. tuple', 'C. dict', 'D. set']),
                ],
            },
            {
                'title': '导入与使用模块',
                'pre': [
                    ('import语法', '导入 math 模块？', 'A',
                     ['A. import math', 'B. include math', 'C. using math', 'D. require math']),
                    ('from import', 'from math import pi 后使用？', 'B',
                     ['A. math.pi', 'B. pi', 'C. Math.PI', 'D. PI']),
                ],
                'post': [
                    ('模块搜索', 'Python 模块搜索路径包含？', 'D',
                     ['A. 当前目录', 'B. PYTHONPATH', 'C. 标准库', 'D. 以上都是']),
                    ('__name__', '脚本直接运行时 __name__ 等于？', 'A',
                     ['A. __main__', 'B. 模块名', 'C. None', 'D. 0']),
                ],
            },
        ],
    },
    {
        'title': '第4章 文件与异常',
        'sort_order': 4,
        'has_pre': True,
        'objectives': [
            {
                'title': '读写文本文件',
                'pre': [
                    ('open模式', '只读模式是？', 'A',
                     ['A. r', 'B. w', 'C. a', 'D. x']),
                    ('with语句', 'with open(...) 的优势？', 'C',
                     ['A. 更快', 'B. 更大缓冲', 'C. 自动关闭文件', 'D. 加密']),
                ],
                'post': [
                    ('write方法', 'w 模式打开已存在文件会？', 'B',
                     ['A. 追加', 'B. 覆盖', 'C. 报错', 'D. 跳过']),
                    ('readlines', 'readlines() 返回？', 'C',
                     ['A. 字符串', 'B. 字节', 'C. 列表', 'D. 迭代器']),
                ],
            },
            {
                'title': '捕获与处理异常',
                'pre': [
                    ('try except', 'ZeroDivisionError 应捕获？', 'A',
                     ['A. try/except', 'B. if/else', 'C. for', 'D. while']),
                    ('异常类型', '1/0 抛出？', 'B',
                     ['A. ValueError', 'B. ZeroDivisionError', 'C. TypeError', 'D. IOError']),
                ],
                'post': [
                    ('finally', 'finally 块何时执行？', 'C',
                     ['A. 仅异常时', 'B. 仅正常时', 'C. 总是执行', 'D. 从不']),
                    ('raise作用', 'raise 用于？', 'A',
                     ['A. 主动抛出异常', 'B. 忽略异常', 'C. 记录日志', 'D. 退出程序']),
                ],
            },
        ],
    },
    {
        'title': '第5章 综合项目',
        'sort_order': 5,
        'has_pre': False,
        'objectives': [
            {
                'title': '综合运用编程知识',
                'post': [
                    ('项目设计', '综合项目首先应？', 'B',
                     ['A. 写代码', 'B. 分析需求', 'C. 选框架', 'D. 部署']),
                    ('代码组织', '大型脚本应？', 'C',
                     ['A. 单文件', 'B. 无函数', 'C. 模块化拆分', 'D. 全全局变量']),
                ],
            },
            {
                'title': '调试与测试程序',
                'post': [
                    ('调试方法', 'print 调试属于？', 'A',
                     ['A. 输出调试', 'B. 单元测试', 'C. 性能分析', 'D. 静态检查']),
                    ('测试意义', '编写测试用例的目的？', 'D',
                     ['A. 加快运行', 'B. 减少代码', 'C. 美化界面', 'D. 验证正确性']),
                ],
            },
        ],
    },
]


def _make_question(title, content, answer, options, teacher_id, objective_id):
    return Question(
        title=title, content=content, type='single_choice',
        options=options, correct_answer=answer, score=2,
        teacher_id=teacher_id, objective_id=objective_id,
    )


def _generate_score(is_pre, attempt, max_score, seed):
    rng = random.Random(seed)
    base = rng.uniform(0.30, 0.55) if is_pre else rng.uniform(0.50, 0.75)
    improvement = (attempt - 1) * rng.uniform(0.04, 0.10)
    ratio = min(base + improvement + rng.uniform(-0.05, 0.05), 1.0)
    return max(int(max_score * ratio), 0)


def _generate_answers(questions, target_ratio, seed):
    rng = random.Random(seed)
    answers = {}
    for q in questions:
        if rng.random() < target_ratio:
            answers[str(q.id)] = q.correct_answer
        else:
            opts = q.options or []
            wrong = [o[0] for o in opts if not o.startswith(q.correct_answer + '.')]
            answers[str(q.id)] = wrong[rng.randint(0, len(wrong) - 1)] if wrong else q.correct_answer
    return answers


def seed():
    app = create_app()
    with app.app_context():
        now = datetime.now(timezone.utc)

        teacher = User(username='teacher', display_name='张老师', role='teacher')
        teacher.set_password('teacher123')
        db.session.add(teacher)
        db.session.flush()

        students = {}
        for username, name in STUDENTS:
            s = User(username=username, display_name=name, role='student')
            s.set_password('student123')
            db.session.add(s)
            students[username] = s
        db.session.flush()

        tc = TeachingClass(
            name=CLASS_CONFIG['name'],
            semester=CLASS_CONFIG['semester'],
            description=CLASS_CONFIG['description'],
            teacher_id=teacher.id,
        )
        db.session.add(tc)
        db.session.flush()

        for s in students.values():
            db.session.add(ClassEnrollment(class_id=tc.id, student_id=s.id))

        submission_count = 0

        for uc in UNITS_CONFIG:
            unit = TeachingUnit(
                class_id=tc.id, title=uc['title'],
                sort_order=uc['sort_order'],
                description=f'{uc["title"]} — 平行前测后测单元',
            )
            db.session.add(unit)
            db.session.flush()

            pre_q_ids, post_q_ids = [], []

            for oi, oc in enumerate(uc['objectives']):
                obj = LearningObjective(
                    unit_id=unit.id, title=oc['title'],
                    sort_order=oi + 1,
                    description=f'学习目标：{oc["title"]}',
                )
                db.session.add(obj)
                db.session.flush()

                if uc['has_pre'] and 'pre' in oc:
                    for qt in oc['pre']:
                        q = _make_question(qt[0], qt[1], qt[2], qt[3], teacher.id, obj.id)
                        db.session.add(q)
                        db.session.flush()
                        pre_q_ids.append(q.id)

                for qt in oc.get('post', []):
                    q = _make_question(qt[0], qt[1], qt[2], qt[3], teacher.id, obj.id)
                    db.session.add(q)
                    db.session.flush()
                    post_q_ids.append(q.id)

            window_start = now - timedelta(days=90 - uc['sort_order'] * 10)
            window_end = now + timedelta(days=60)

            if uc['has_pre'] and pre_q_ids:
                pre_a = Assessment(
                    unit_id=unit.id,
                    title=f'{uc["title"]} · 前测',
                    description='诊断性前测，不计入成绩，可多次提交摸底。',
                    type='pre_test', teacher_id=teacher.id,
                    is_published=True, counts_toward_grade=False,
                    start_time=window_start, end_time=window_end,
                    questions=pre_q_ids, max_attempts=3,
                )
                db.session.add(pre_a)
                db.session.flush()
            else:
                pre_a = None

            post_a = Assessment(
                unit_id=unit.id,
                title=f'{uc["title"]} · 后测',
                description='总结性后测，计入成绩。',
                type='post_test', teacher_id=teacher.id,
                is_published=True, counts_toward_grade=True,
                start_time=window_start + timedelta(days=14),
                end_time=window_end,
                questions=post_q_ids, max_attempts=2,
            )
            db.session.add(post_a)
            db.session.flush()

            for s in students.values():
                for assessment, is_pre, max_att in [
                    (pre_a, True, 3),
                    (post_a, False, 2),
                ]:
                    if assessment is None:
                        continue
                    qs = assessment.get_questions()
                    max_score = sum(q.score for q in qs)
                    num_att = min(max_att, random.Random(s.id + assessment.id).randint(1, max_att))

                    for attempt in range(1, num_att + 1):
                        seed = s.id * 10000 + assessment.id * 100 + attempt
                        target = _generate_score(is_pre, attempt, max_score, seed)
                        ratio = target / max_score if max_score else 0
                        answers = _generate_answers(qs, ratio, seed + 7)
                        sub_time = window_start + timedelta(
                            days=(14 if not is_pre else 0) + attempt * 3
                        )
                        sub = Submission(
                            student_id=s.id, assessment_id=assessment.id,
                            attempt_number=attempt, answers=answers,
                            submitted_at=sub_time,
                        )
                        db.session.add(sub)
                        db.session.flush()
                        sub.grade()
                        submission_count += 1

        db.session.commit()

        q_count = Question.query.count()
        u_count = TeachingUnit.query.count()
        a_count = Assessment.query.count()
        pre_count = Assessment.query.filter_by(type='pre_test').count()
        post_count = Assessment.query.filter_by(type='post_test').count()

        print('\n' + '=' * 60)
        print('  DEMO DATA GENERATION COMPLETE (new schema)')
        print('=' * 60)
        print(f'  教学班: {tc.name} ({tc.semester})')
        print(f'  学生: {len(students)}  |  教学单元: {u_count}')
        print(f'  题目: {q_count}  |  测评: {a_count} (前测 {pre_count} + 后测 {post_count})')
        print(f'  提交记录: {submission_count}')
        print(f'  教师: teacher / teacher123')
        print(f'  学生: student1 / student123')
        print('=' * 60)


if __name__ == '__main__':
    seed()
