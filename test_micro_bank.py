import json
import unittest
from collections import Counter
from pathlib import Path

BANK = Path(__file__).parent / 'data' / 'micro.json'
PREFIX = {'api': 'api', 'integration': 'int', 'design': 'sys'}


class MicroBankContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cards = json.loads(BANK.read_text(encoding='utf-8'))

    def test_card_count_ids_and_pool_distribution(self):
        self.assertEqual(len(self.cards), 36)
        self.assertEqual(len({card['id'] for card in self.cards}), 36)
        for pool, prefix in PREFIX.items():
            cards = [card for card in self.cards if card['pool'] == pool]
            self.assertEqual(len(cards), 12)
            self.assertEqual({card['id'] for card in cards}, {f'{prefix}-{n}' for n in range(101, 113)})
            self.assertEqual(Counter(card['difficulty'] for card in cards), {1: 4, 2: 4, 3: 4})

    def test_every_card_has_micro_shape_and_timebox(self):
        expected_keys = {'id', 'pool', 'title', 'difficulty', 'minutes', 'tags', 'brief', 'deliverables', 'facts', 'rubric', 'pitfalls', 'reference', 'twist', 'format'}
        for card in self.cards:
            with self.subTest(card=card['id']):
                self.assertEqual(set(card), expected_keys | {'privateContext'})
                self.assertEqual(card['format'], 'micro')
                self.assertIn(card['minutes'], (5, 10))
                self.assertTrue(card['title'].strip())
                self.assertTrue(card['brief'].strip())
                self.assertIn(len(card['deliverables']), (2, 3))
                self.assertIn(len(card['facts']), (3, 4))
                self.assertEqual(len(card['rubric']), 5)
                self.assertEqual(len(card['pitfalls']), 3)
                self.assertTrue(3 <= len(card['reference']['decisions']) <= 5)
                self.assertIn(len(card['reference']['alternatives']), (1, 2))
                self.assertTrue(card['reference']['summary'].strip())
                self.assertTrue(card['twist'].strip())

    def test_fact_and_rubric_answers_are_concrete_and_card_specific(self):
        for card in self.cards:
            with self.subTest(card=card['id']):
                fact_ids = [fact['id'] for fact in card['facts']]
                self.assertEqual(len(set(fact_ids)), len(fact_ids))
                self.assertTrue(all(fact['question'].strip() and fact['answer'].strip() for fact in card['facts']))
                self.assertTrue(all(item.get('publicExpectation') for item in card['rubric']))
                self.assertTrue(all(set(item.get('factIds', [])) <= set(fact_ids) for item in card['rubric']))
                self.assertTrue(all(item.get('severity') in ('critical', 'major', 'minor') for item in card['rubric']))
                self.assertGreaterEqual(sum(not item['factIds'] for item in card['rubric']), 2)
                rubric_skills = {skill for item in card['rubric'] for skill in item['skillIds']}
                self.assertEqual({tag.removeprefix('skill:') for tag in card['tags'] if tag.startswith('skill:')}, rubric_skills)
                # Hidden fact answers must live only in the facts panel, never in evaluator-visible rubric text.
                rubric_text = ' '.join(item['publicExpectation'] for item in card['rubric'])
                self.assertFalse(any(fact['answer'] in rubric_text for fact in card['facts']))


if __name__ == '__main__':
    unittest.main()
