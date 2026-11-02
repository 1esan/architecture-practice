import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parent
SKILLS = {
    'skill:requirements', 'skill:capacity', 'skill:data', 'skill:contracts',
    'skill:reliability', 'skill:security', 'skill:tradeoffs', 'skill:communication',
}


class BankQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.banks = {
            path.stem: json.loads(path.read_text(encoding='utf-8'))
            for path in (ROOT / 'data').glob('*.json')
        }

    def test_rubrics_are_public_and_fact_traceable(self):
        for bank_name, cards in self.banks.items():
            for card in cards:
                with self.subTest(bank=bank_name, card=card['id']):
                    fact_ids = {fact['id'] for fact in card['facts']}
                    self.assertEqual(len(card['rubric']), 5)
                    self.assertEqual(len({item['id'] for item in card['rubric']}), 5)
                    for item in card['rubric']:
                        self.assertTrue(item['label'].strip())
                        self.assertTrue(item['publicExpectation'].strip())
                        self.assertIn(item['severity'], {'critical', 'major', 'minor'})
                        self.assertLessEqual(set(item['factIds']), fact_ids)
                        self.assertLessEqual(set(item.get('detailFactIds', [])), fact_ids)
                        self.assertGreaterEqual(len(item['skillIds']), 1)
                        self.assertLessEqual(set(item['skillIds']), {tag.removeprefix('skill:') for tag in SKILLS})
                        self.assertIn(card['title'], item['publicExpectation'])
                        self.assertNotIn('expectation', item)
                    self.assertGreaterEqual(sum(not item['factIds'] for item in card['rubric']), 2)
                    rubric_skills = {skill for item in card['rubric'] for skill in item['skillIds']}
                    self.assertEqual({tag.removeprefix('skill:') for tag in card['tags'] if tag in SKILLS or tag.startswith('skill:')}, rubric_skills)
                    text = ' '.join(item['publicExpectation'] for item in card['rubric'])
                    self.assertFalse(any(fact['answer'] in text for fact in card['facts']))

    def test_integration_expert_failure_checks_facts_without_inventing_offline_limits(self):
        cards = [card for card in self.banks['integration'] if card['difficulty'] == 3]
        self.assertEqual(len(cards), 20)
        for card in cards:
            failure = next(item for item in card['rubric'] if item['id'] == 'failure')
            availability = next(fact for fact in card['facts'] if fact['label'].lower() == 'доступность')
            delivery = next(fact for fact in card['facts'] if fact['label'].lower() == 'доставка')
            self.assertIn(availability['id'], failure['detailFactIds'])
            self.assertIn(delivery['id'], failure['detailFactIds'])
            self.assertIn('не вводите неподтверждённые сроки', failure['publicExpectation'].lower())

    def test_skill_tags_use_shared_taxonomy_and_are_card_specific(self):
        used = set()
        for cards in self.banks.values():
            for card in cards:
                tags = set(card['tags'])
                card_skills = tags & SKILLS
                self.assertGreaterEqual(len(card_skills), 2)
                used.update(card_skills)
        self.assertEqual(used, SKILLS)

    def test_each_pool_keeps_two_answer_independent_criteria(self):
        always_active = {
            'api': {'contract', 'errors'},
            'integration': {'choice', 'contract'},
            'design': {'boundaries', 'proportionality'},
            'micro': {'decision', 'tradeoff'},
        }
        for bank_name, cards in self.banks.items():
            for card in cards:
                active = {item['id'] for item in card['rubric'] if not item['factIds']}
                with self.subTest(bank=bank_name, card=card['id']):
                    self.assertGreaterEqual(len(active), 2)
                    self.assertTrue(always_active[bank_name] <= active)

    def test_prompt_core_criteria_are_not_gated_by_unrevealed_facts(self):
        for bank_name in ('api', 'integration', 'design'):
            for card in self.banks[bank_name]:
                with self.subTest(bank=bank_name, card=card['id']):
                    self.assertTrue(all(not item['factIds'] for item in card['rubric']))
        for card in self.banks['micro']:
            with self.subTest(card=card['id']):
                self.assertEqual({item['id'] for item in card['rubric'] if item['factIds']}, {'case_fact'})


if __name__ == '__main__':
    unittest.main()
