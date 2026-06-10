"""Growth trajectory data builders for student and teacher views."""

import logging

from ..extensions import cache
from ..models import TeachingClass, TeachingUnit
from .gain import unit_gain_for_student_cached, score_rate, best_submission, _bulk_load_units_data

logger = logging.getLogger(__name__)


# ── helpers ────────────────────────────────────────────────────────────

def _chapter_number(unit, fallback_index):
    return unit.sort_order if unit.sort_order and unit.sort_order > 0 else fallback_index


def _discover_class_ids_from_submissions(student_id):
    """When a student is not formally enrolled, discover their classes via
    existing submissions (assessment → unit → class)."""
    from ..models import Submission, Assessment

    rows = (
        Submission.query
        .with_entities(Submission.assessment_id)
        .filter_by(student_id=student_id)
        .distinct()
        .all()
    )
    if not rows:
        return []

    assessment_ids = [r[0] for r in rows]
    rows = (
        Assessment.query
        .with_entities(Assessment.unit_id)
        .filter(Assessment.id.in_(assessment_ids))
        .distinct()
        .all()
    )
    unit_ids = [r[0] for r in rows if r[0] is not None]
    if not unit_ids:
        return []

    rows = (
        TeachingUnit.query
        .with_entities(TeachingUnit.class_id)
        .filter(TeachingUnit.id.in_(unit_ids))
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


# ── unified chart-point factory ───────────────────────────────────────

# Every chart point (regardless of group_type) has these 7 common fields.
_CP_COMMON = {'group_type', 'group_id', 'group_label', 'type', 'type_order',
              'total', 'pct'}

# Assessment-only extras — set to None on unit points for safe access.
_CP_ASSESSMENT_EXTRAS = {'assessment_id', 'assessment_title', 'unit_title',
                         'attempt', 'score', 'submitted_at'}


def _make_chart_point(*, group_type, group_id, group_label, point_type,
                      type_order, pct, total=100,
                      assessment_id=None, assessment_title=None,
                      unit_title=None, attempt=None, score=None,
                      submitted_at=None, **_):
    """Create a single chart data point with a unified schema.

    group_type  = 'unit' | 'assessment'
    point_type  = 'pre_test' | 'post_test'
    """
    return {
        'group_type':       group_type,
        'group_id':         group_id,
        'group_label':      group_label,
        'type':             point_type,
        'type_order':       type_order,
        'total':            total,
        'pct':              pct,
        # extended fields (None for unit points)
        'assessment_id':    assessment_id,
        'assessment_title': assessment_title,
        'unit_title':       unit_title,
        'attempt':          attempt,
        'score':            score,
        'submitted_at':     submitted_at,
    }


# ── unit chart-item helpers (used by student growth table) ────────────

def _unit_chart_item(teaching_class, unit, report, chapter_number, num_classes=1):
    base_label = f'{chapter_number}. {unit.title}'
    group_label = f'[{teaching_class.name}] {base_label}' if num_classes > 1 else base_label
    return {
        'group_type':    'unit',
        'group_id':      unit.id,
        'group_label':   group_label,
        'group_order':   chapter_number,
        'class_id':      teaching_class.id,
        'class_name':    teaching_class.name,
        'unit_id':       unit.id,
        'title':         unit.title,
        'unit_title':    base_label,
        'chapter_number': chapter_number,
        'chapter_label': f'第{chapter_number}章',
        'pre_rate':      report['pre_rate'],
        'post_rate':     report['post_rate'],
        'display_label': group_label,
    }


# ── main builder ──────────────────────────────────────────────────────

@cache.memoize(timeout=60)
def build_student_growth_context(student_id, class_ids=None):
    """Single source of truth for all growth data — unit-level and assessment-level.

    Returns a dict whose `chart_payload` is a *merged* list: every item has
    `group_type` ('unit' | 'assessment') and a uniform field schema so the
    frontend can filter/pivot by group_type without field-access errors.
    """
    empty = {
        'unit_reports':      [],
        'chart_items':       [],
        'chart_payload':     [],   # ← unified: unit + assessment points
        'chart_mode':        'unit',
        'has_data':          False,
        'submissions':       [],
    }

    if not class_ids:
        logger.warning(
            '[growth] student=%s class_ids empty → auto-discovering',
            student_id)
        class_ids = _discover_class_ids_from_submissions(student_id)
        logger.info('[growth] auto-discovered class_ids=%s', class_ids)
    if not class_ids:
        return empty

    classes = (
        TeachingClass.query
        .filter(TeachingClass.id.in_(class_ids))
        .order_by(TeachingClass.created_at.asc(), TeachingClass.id.asc())
        .all()
    )
    logger.info('[growth] student=%s classes=%s',
                student_id, [(c.id, c.name) for c in classes])
    if not classes:
        return empty

    # Collect units
    all_units = []
    for tc in classes:
        units = list(tc.units)
        all_units.extend(units)
    logger.info('[growth] total units=%s', len(all_units))
    if not all_units:
        return empty

    # ── one bulk DB round-trip ────────────────────────────────────────
    preloaded = _bulk_load_units_data(all_units, student_ids=[student_id])
    logger.info(
        '[growth] preloaded assessments=%s units, '
        'objectives=%s units, submissions=%s total',
        len(preloaded['assessments_by_unit']),
        len(preloaded['objectives_by_unit']),
        sum(len(v) for v in preloaded['submissions_by_key'].values()))

    # ── materialise to avoid lazy-load side-effects on preloaded dicts ──
    assessments_by_unit = preloaded['assessments_by_unit']
    objectives_by_unit = preloaded['objectives_by_unit']
    subs_by_key = preloaded['submissions_by_key']

    # ── build unit-level view ─────────────────────────────────────────
    unit_reports = []
    chart_items = []
    unified_payload = []

    for tc in classes:
        units = list(tc.units)
        for idx, unit in enumerate(units, start=1):
            report = unit_gain_for_student_cached(unit, student_id, preloaded)
            chapter_number = _chapter_number(unit, idx)
            report['class_name'] = tc.name
            report['chapter_number'] = chapter_number
            report['chapter_label'] = f'第{chapter_number}章'
            report['unit_title'] = f'{chapter_number}. {unit.title}'
            unit_reports.append(report)

            item = _unit_chart_item(tc, unit, report, chapter_number,
                                    num_classes=len(classes))
            chart_items.append(item)

            # expand to two chart points (pre / post) in unified payload
            if report['pre_rate'] is not None:
                unified_payload.append(_make_chart_point(
                    group_type='unit', group_id=unit.id,
                    group_label=item['group_label'],
                    point_type='pre_test', type_order=0,
                    pct=report['pre_rate']))
            if report['post_rate'] is not None:
                unified_payload.append(_make_chart_point(
                    group_type='unit', group_id=unit.id,
                    group_label=item['group_label'],
                    point_type='post_test', type_order=1,
                    pct=report['post_rate']))

    # ── build assessment-level view (same preloaded data) ─────────────
    all_submissions = []
    assessment_map = {}
    assessment_subs = {}
    assessment_rates = []
    pre_rates = []
    post_rates = []

    for unit_id, ass_dict in assessments_by_unit.items():
        for a_type, assessment in ass_dict.items():
            assessment_map[assessment.id] = assessment
            subs = subs_by_key.get((assessment.id, student_id), [])
            if subs:
                assessment_subs[assessment.id] = subs
                all_submissions.extend(subs)

    for a_id, subs in assessment_subs.items():
        assessment = assessment_map[a_id]
        best = best_submission(subs)
        rate = score_rate(best)
        if rate is not None:
            assessment_rates.append(rate)
            if assessment.type == 'pre_test':
                pre_rates.append(rate)
            elif assessment.type == 'post_test':
                post_rates.append(rate)
        unified_payload.append(_make_chart_point(
            group_type='assessment',
            group_id=a_id,
            group_label=assessment.title,
            point_type=assessment.type,
            type_order=0 if assessment.type == 'pre_test' else 1,
            pct=round(rate, 1) if rate is not None else None,
            # assessment-specific extras
            assessment_id=a_id,
            assessment_title=assessment.title,
            unit_title=assessment.unit.title if assessment.unit else assessment.title,
            attempt=best.attempt_number if best else None,
            score=best.score if best else None,
            submitted_at=best.submitted_at.strftime('%Y-%m-%d %H:%M:%S')
                          if best and best.submitted_at else '',
        ))

    unit_gains = [r.get('absolute_gain') for r in unit_reports if r.get('absolute_gain') is not None]
    weak_units = sorted(
        [r for r in unit_reports if r.get('post_rate') is not None and r.get('post_rate') < 60],
        key=lambda r: r['post_rate']
    )[:5]
    avg_assessment_rate = round(sum(assessment_rates) / len(assessment_rates), 1) if assessment_rates else None
    avg_pre_rate = round(sum(pre_rates) / len(pre_rates), 1) if pre_rates else None
    avg_post_rate = round(sum(post_rates) / len(post_rates), 1) if post_rates else None
    avg_gain = round(sum(unit_gains) / len(unit_gains), 1) if unit_gains else None

    # 风险等级：后测绝对值优先，但高增益也纳入考量
    if avg_post_rate is not None and avg_post_rate < 60:
        risk_level = '预警（有进步）' if (avg_gain is not None and avg_gain >= 10) else '预警'
    elif avg_post_rate is not None and avg_post_rate < 75:
        risk_level = '待提升（有进步）' if (avg_gain is not None and avg_gain >= 10) else '待提升'
    elif avg_gain is not None and avg_gain >= 10:
        risk_level = '进步显著'
    else:
        risk_level = '正常'

    recommendations = []
    if weak_units:
        recommendations.append(f'优先复习 {weak_units[0]["unit_title"]} 对应单元')
    if (avg_pre_rate is not None and avg_post_rate is not None
            and avg_post_rate >= avg_pre_rate and avg_post_rate >= 60):
        recommendations.append('继续保持当前教学节奏，并在后测后补充巩固练习')
    if not recommendations:
        recommendations.append('建议结合错题回顾与目标达成情况安排针对性练习')

    return {
        'unit_reports':  unit_reports,
        'chart_items':   chart_items,
        'chart_payload': unified_payload,
        'chart_mode':    'unit',
        'has_data':      len(unified_payload) > 0,
        'submissions':   all_submissions,
        'trend_series': assessment_rates,
        'avg_assessment_rate': avg_assessment_rate,
        'avg_pre_rate': avg_pre_rate,
        'avg_post_rate': avg_post_rate,
        'avg_gain': avg_gain,
        'risk_level': risk_level,
        'recommendations': recommendations,
        'weak_units': weak_units,
    }
