import collections
import json
import pathlib

root = pathlib.Path(__file__).parent
all_ids = set()
skill_tags = {
    'skill:requirements', 'skill:capacity', 'skill:data', 'skill:contracts',
    'skill:reliability', 'skill:security', 'skill:tradeoffs', 'skill:communication',
}
skill_ids = {tag.removeprefix('skill:') for tag in skill_tags}

for name, prefix in [('api', 'api'), ('integration', 'int'), ('design', 'sys')]:
    cards = json.loads((root / 'data' / f'{name}.json').read_text(encoding='utf-8'))
    assert len(cards) == 60
    assert collections.Counter(c['difficulty'] for c in cards) == {1: 20, 2: 20, 3: 20}
    for i, card in enumerate(cards, 1):
        assert card['id'] == f'{prefix}-{i:03d}' and card['pool'] == name
        assert card['id'] not in all_ids
        all_ids.add(card['id'])
        assert len(card['brief']) > 100 and 3 <= len(card['deliverables']) <= 5
        assert 4 <= len(card['facts']) <= 6
        fact_ids = {fact['id'] for fact in card['facts']}
        assert len(fact_ids) == len(card['facts'])
        assert all(len(f['answer']) > 10 and len(f['question']) > 10 for f in card['facts'])
        assert len(card['rubric']) == 5
        assert len({r['id'] for r in card['rubric']}) == 5
        assert all(r.get('publicExpectation') and r.get('severity') in {'critical', 'major', 'minor'} for r in card['rubric'])
        assert all(set(r.get('factIds', [])) <= fact_ids for r in card['rubric'])
        assert all(set(r.get('detailFactIds', [])) <= fact_ids for r in card['rubric'])
        assert all(r.get('skillIds') and set(r['skillIds']) <= skill_ids for r in card['rubric'])
        assert sum(not r['factIds'] for r in card['rubric']) >= 2
        rubric_skills = {skill for r in card['rubric'] for skill in r['skillIds']}
        assert {tag.removeprefix('skill:') for tag in card['tags'] if tag.startswith('skill:')} == rubric_skills
        assert 3 <= len(card['reference']['decisions']) <= 5
        assert 1 <= len(card['reference']['alternatives']) <= 2
        assert len(card['pitfalls']) == 3 and card['twist']
        assert len(set(card['tags']) & skill_tags) >= 2
    assert len({c['reference']['summary'] for c in cards}) == 60
    print(f'{name}: 60 cards, IDs, facts, traceable rubric, skill tags PASS')

micro = json.loads((root / 'data' / 'micro.json').read_text(encoding='utf-8'))
assert len(micro) == 36
for card in micro:
    assert len(card['facts']) in (3, 4)
    fact_ids = {fact['id'] for fact in card['facts']}
    assert len(card['rubric']) == 5
    assert all(r.get('publicExpectation') and r.get('severity') in {'critical', 'major', 'minor'} for r in card['rubric'])
    assert all(set(r.get('factIds', [])) <= fact_ids for r in card['rubric'])
    assert all(set(r.get('detailFactIds', [])) <= fact_ids for r in card['rubric'])
    assert all(r.get('skillIds') and set(r['skillIds']) <= skill_ids for r in card['rubric'])
    assert sum(not r['factIds'] for r in card['rubric']) >= 2
    rubric_skills = {skill for r in card['rubric'] for skill in r['skillIds']}
    assert {tag.removeprefix('skill:') for tag in card['tags'] if tag.startswith('skill:')} == rubric_skills
    assert len(set(card['tags']) & skill_tags) >= 2
assert len(all_ids) == 180
print('all pools: rubric fact links resolve; 180 IDs unique')
