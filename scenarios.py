"""Server-only stakeholder dossiers. Never embed answers in the public HTML."""
import copy
import hashlib
import json
import re

CORE_AREAS = {'ctx-process', 'ctx-actors', 'ctx-trigger', 'ctx-goal', 'ctx-success', 'ctx-acceptance'}


def validate_context(card):
    value = card.get('privateContext')
    if value is None:
        return None  # Backward-compatible fixtures/older cards.
    if not isinstance(value, dict) or value.get('version') != 1:
        raise ValueError('Некорректное досье кейса')
    areas = value.get('areas')
    if not isinstance(areas, list) or not 4 <= len(areas) <= 20:
        raise ValueError('Неполный контекст кейса')
    ids = {f['id'] for f in card.get('facts', []) if not f['id'].startswith('ctx-')}
    for area in areas:
        if (not isinstance(area, dict) or not isinstance(area.get('id'), str)
                or not re.fullmatch(r'ctx-[a-z0-9-]{1,60}', area['id']) or area['id'] in ids
                or not isinstance(area.get('label'), str) or not 1 <= len(area['label']) <= 200
                or not isinstance(area.get('answer'), str) or not 40 <= len(area['answer']) <= 6000
                or type(area.get('essential')) is not bool
                or not isinstance(area.get('keywords'), list) or len(area['keywords']) > 20
                or not all(isinstance(k, str) and 1 <= len(k) <= 100 for k in area['keywords'])):
            raise ValueError('Некорректная область досье')
        ids.add(area['id'])
    unresolved = value.get('unresolved', [])
    if not isinstance(unresolved, list) or len(unresolved) > 3:
        raise ValueError('Слишком много неопределённостей в досье')
    for item in unresolved:
        if (not isinstance(item, dict) or not isinstance(item.get('id'), str)
                or not re.fullmatch(r'ctx-open-[a-z0-9-]{1,60}', item['id']) or item['id'] in ids
                or not isinstance(item.get('question'), str) or not item['question'].strip()
                or not isinstance(item.get('reason'), str) or not item['reason'].strip()):
            raise ValueError('Некорректный открытый вопрос досье')
        ids.add(item['id'])
    return value


def expanded_card(card):
    value = validate_context(card)
    result = copy.deepcopy(card)
    if value:
        known = {f['id'] for f in result['facts']}
        result['facts'].extend({'id':a['id'], 'label':a['label'], 'question':a['label'], 'answer':a['answer']}
                               for a in value['areas'] if a['id'] not in known)
    return result


def public_card(card):
    result = copy.deepcopy(card)
    result.pop('privateContext', None)
    result['facts'] = [f for f in result.get('facts', []) if not f['id'].startswith('ctx-')]
    return result


def revision(card):
    value = card.get('privateContext')
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16] if value else 'legacy'


def discovery_areas(card, revealed):
    """Topics only: the coach never receives undisclosed answers or numerical thresholds."""
    known = set(revealed)
    original = [f for f in card['facts'] if not f['id'].startswith('ctx-')]
    micro = card.get('format') == 'micro'
    return [{'id':a['id'], 'label':a['label'],
             'essential':a['essential'] and a['id'] in (CORE_AREAS if not micro else {'ctx-process','ctx-actors'}),
             'explored':a['id'] in known or any(f['id'] in known and f['answer'] in a['answer'] for f in original)}
            for a in card.get('privateContext', {}).get('areas', [])]
