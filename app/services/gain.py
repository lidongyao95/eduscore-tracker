"""Learning gain calculations based on pre/post test pairs within teaching units."""

from ..extensions import cache


def score_rate(submission):
    if submission is None or submission.total_score == 0:
        return None
    return submission.score / submission.total_score * 100


def absolute_gain(pre_rate, post_rate):
    if pre_rate is None or post_rate is None:
        return None
    return round(post_rate - pre_rate, 1)


def normalized_gain(pre_rate, post_rate):
    """Hake g-factor: (post - pre) / (100 - pre).  Returns None when incalculable."""
    if pre_rate is None or post_rate is None:
        return None
    if pre_rate >= 100:
        return None
    return round((post_rate - pre_rate) / (100 - pre_rate), 3)


def best_submission(submissions):
    """Pick the submission with the highest score rate."""
    best = None
    best_rate = -1
    for sub in submissions:
        rate = score_rate(sub)
        if rate is None:
            continue
        if rate > best_rate:
            best_rate = rate
            best = sub
    return best


def objective_breakdown(submission, objectives):
    """Per-objective score for one submission."""
    if submission is None:
        return []
    answers = submission.answers or {}
    results = []
    for obj in objectives:
        obj_score = 0
        obj_total = 0
        for q in obj.questions:
            obj_total += q.score
            ans = answers.get(str(q.id), '')
            if q.type == 'single_choice':
                if ans and ans.strip().upper() == (q.correct_answer or '').strip().upper():
                    obj_score += q.score
            elif q.type == 'multi_choice':
                correct_set = set(x.strip().upper() for x in (q.correct_answer or '').split(',')) - {''}
                student_set = set(x.strip().upper() for x in ans.split(',')) if ans else set()
                if correct_set and correct_set == student_set:
                    obj_score += q.score
        rate = round(obj_score / obj_total * 100, 1) if obj_total else None
        results.append({
            'objective': obj,
            'score': obj_score,
            'total': obj_total,
            'rate': rate,
        })
    return results


def _bulk_load_units_data(units, student_ids=None):
    """Preload assessments, submissions, and objectives for a list of units.

    Returns a dict keyed by (unit.id, student_id) -> list of pre/post submissions,
    plus dicts for assessments and objectives.
    """
    from sqlalchemy.orm import joinedload
    from ..models import Assessment, Submission, LearningObjective, Question

    unit_ids = [u.id for u in units]

    # Load all assessments for these units in one query
    assessments = Assessment.query.filter(
        Assessment.unit_id.in_(unit_ids),
        Assessment.type.in_(['pre_test', 'post_test']),
    ).all()
    assessments_by_unit = {}
    for a in assessments:
        assessments_by_unit.setdefault(a.unit_id, {})[a.type] = a

    # Load all objectives with questions eagerly for these units
    all_objectives = (
        LearningObjective.query
        .filter(LearningObjective.unit_id.in_(unit_ids))
        .order_by(LearningObjective.sort_order)
        .all()
    )
    obj_ids = [o.id for o in all_objectives]
    all_questions = Question.query.filter(Question.objective_id.in_(obj_ids)).all() if obj_ids else []
    questions_by_obj = {}
    for q in all_questions:
        questions_by_obj.setdefault(q.objective_id, []).append(q)
    # Attach questions to objectives so objective.questions works without DB
    for o in all_objectives:
        o.questions = questions_by_obj.get(o.id, [])
    objectives_by_unit = {}
    for o in all_objectives:
        objectives_by_unit.setdefault(o.unit_id, []).append(o)

    # Load all submissions for these assessments in one query
    assessment_ids = [a.id for a in assessments]
    submissions_filter = Submission.query.filter(Submission.assessment_id.in_(assessment_ids))
    if student_ids is not None:
        submissions_filter = submissions_filter.filter(Submission.student_id.in_(student_ids))
    all_submissions = submissions_filter.options(
        joinedload(Submission.assessment)
    ).all()

    # Index submissions by (assessment_id, student_id)
    submissions_by_assessment_student = {}
    for s in all_submissions:
        key = (s.assessment_id, s.student_id)
        submissions_by_assessment_student.setdefault(key, []).append(s)

    return {
        'assessments_by_unit': assessments_by_unit,
        'objectives_by_unit': objectives_by_unit,
        'submissions_by_key': submissions_by_assessment_student,
    }


def unit_gain_for_student_cached(unit, student_id, preloaded):
    """Gain report using preloaded data (no DB queries)."""
    assessments = preloaded['assessments_by_unit'].get(unit.id, {})
    pre_a = assessments.get('pre_test')
    post_a = assessments.get('post_test')
    objectives = preloaded['objectives_by_unit'].get(unit.id, [])
    subs_by_key = preloaded['submissions_by_key']

    pre_subs = subs_by_key.get((pre_a.id, student_id), []) if pre_a else []
    post_subs = subs_by_key.get((post_a.id, student_id), []) if post_a else []

    pre_best = best_submission(pre_subs)
    post_best = best_submission(post_subs)
    pre_rate = score_rate(pre_best)
    post_rate = score_rate(post_best)

    objective_gains = []
    if objectives:
        pre_obj = objective_breakdown(pre_best, objectives) if pre_best else [
            {'objective': o, 'score': 0, 'total': sum(q.score for q in o.questions), 'rate': None}
            for o in objectives
        ]
        post_obj = objective_breakdown(post_best, objectives) if post_best else [
            {'objective': o, 'score': 0, 'total': sum(q.score for q in o.questions), 'rate': None}
            for o in objectives
        ]
        for pre_item, post_item in zip(pre_obj, post_obj):
            objective_gains.append({
                'objective_title': pre_item['objective'].title,
                'pre_rate': pre_item['rate'],
                'post_rate': post_item['rate'],
                'gain': absolute_gain(pre_item['rate'], post_item['rate']),
            })

    return {
        'unit': unit,
        'has_pre': pre_a is not None,
        'has_post': post_a is not None,
        'pre_rate': round(pre_rate, 1) if pre_rate is not None else None,
        'post_rate': round(post_rate, 1) if post_rate is not None else None,
        'absolute_gain': absolute_gain(pre_rate, post_rate),
        'normalized_gain': normalized_gain(pre_rate, post_rate),
        'objective_gains': objective_gains,
        'pre_submission': pre_best,
        'post_submission': post_best,
    }


def unit_gain_for_student(unit, student_id):
    """Full gain report for one student on one teaching unit.

    Prefer class_gain_summary / build_student_growth_context which use the
    cached version with bulk-preloaded data to avoid N+1 queries.
    """
    from ..models import Submission

    pre_a = unit.get_pre_assessment()
    post_a = unit.get_post_assessment()
    objectives = unit.objectives

    pre_subs = Submission.query.filter_by(student_id=student_id, assessment_id=pre_a.id).all() if pre_a else []
    post_subs = Submission.query.filter_by(student_id=student_id, assessment_id=post_a.id).all() if post_a else []

    pre_best = best_submission(pre_subs)
    post_best = best_submission(post_subs)
    pre_rate = score_rate(pre_best)
    post_rate = score_rate(post_best)

    objective_gains = []
    if objectives:
        pre_obj = objective_breakdown(pre_best, objectives) if pre_best else [
            {'objective': o, 'score': 0, 'total': sum(q.score for q in o.questions), 'rate': None}
            for o in objectives
        ]
        post_obj = objective_breakdown(post_best, objectives) if post_best else [
            {'objective': o, 'score': 0, 'total': sum(q.score for q in o.questions), 'rate': None}
            for o in objectives
        ]
        for pre_item, post_item in zip(pre_obj, post_obj):
            objective_gains.append({
                'objective_title': pre_item['objective'].title,
                'pre_rate': pre_item['rate'],
                'post_rate': post_item['rate'],
                'gain': absolute_gain(pre_item['rate'], post_item['rate']),
            })

    return {
        'unit': unit,
        'has_pre': pre_a is not None,
        'has_post': post_a is not None,
        'pre_rate': round(pre_rate, 1) if pre_rate is not None else None,
        'post_rate': round(post_rate, 1) if post_rate is not None else None,
        'absolute_gain': absolute_gain(pre_rate, post_rate),
        'normalized_gain': normalized_gain(pre_rate, post_rate),
        'objective_gains': objective_gains,
        'pre_submission': pre_best,
        'post_submission': post_best,
    }


@cache.memoize(timeout=60)
def class_gain_summary(teaching_class, student_ids):
    """Aggregate gain stats across all units for a class (uses bulk preload)."""
    units = teaching_class.units
    unit_summaries = []
    abs_gains = []
    norm_gains = []

    total_students = len(student_ids)

    # Bulk preload all data to avoid N+1 queries
    preloaded = _bulk_load_units_data(units, student_ids=student_ids) if units else {}

    for unit in units:
        post_a = preloaded['assessments_by_unit'].get(unit.id, {}).get('post_test')
        if not post_a:
            continue
        unit_abs = []
        unit_norm = []
        students_without_pre = 0
        for sid in student_ids:
            report = unit_gain_for_student_cached(unit, sid, preloaded)
            if report['absolute_gain'] is not None:
                unit_abs.append(report['absolute_gain'])
                if report['normalized_gain'] is not None:
                    unit_norm.append(report['normalized_gain'])
            else:
                students_without_pre += 1
        avg_abs = round(sum(unit_abs) / len(unit_abs), 1) if unit_abs else None
        avg_norm = round(sum(unit_norm) / len(unit_norm), 3) if unit_norm else None
        if avg_abs is not None:
            abs_gains.extend(unit_abs)
            norm_gains.extend(unit_norm)
        unit_summaries.append({
            'unit': unit,
            'total_students': total_students,
            'student_count': len(unit_abs),
            'students_without_pre': students_without_pre,
            'avg_absolute_gain': avg_abs,
            'avg_normalized_gain': avg_norm,
            'objective_count': len(preloaded['objectives_by_unit'].get(unit.id, [])),
        })

    return {
        'unit_summaries': unit_summaries,
        'overall_avg_absolute_gain': round(sum(abs_gains) / len(abs_gains), 1) if abs_gains else None,
        'overall_avg_normalized_gain': round(sum(norm_gains) / len(norm_gains), 3) if norm_gains else None,
    }
