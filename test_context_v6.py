"""Regressions for domain contamination found during the complete bank audit."""
import json,pathlib,unittest
import scenarios
ROOT=pathlib.Path(__file__).resolve().parent
CARDS={c['id']:c for p in (ROOT/'data').glob('*.json') for c in json.loads(p.read_text(encoding='utf-8'))}
def dossier(cid):return ' '.join(a['answer'] for a in CARDS[cid]['privateContext']['areas'])
def facts(cid):return ' '.join(f['answer'] for f in CARDS[cid]['facts'])
class ContextQualityRegressions(unittest.TestCase):
 def test_all_216_contexts_are_valid_and_private(self):
  self.assertEqual(len(CARDS),216)
  for c in CARDS.values():
   with self.subTest(card=c['id']):
    scenarios.validate_context(c)
    self.assertNotIn('privateContext',scenarios.public_card(c))
    self.assertEqual({f['id'] for f in scenarios.expanded_card(c)['facts']},{f['id'] for f in c['facts']}|{a['id'] for a in c['privateContext']['areas']})
 def test_employee_import_does_not_acquire_product_inventory(self):
  self.assertNotRegex(facts('api-005')+' '+dossier('api-005'),r'(?i)\bSKU\b')
  self.assertIn('сотрудник',dossier('api-005').lower())
 def test_equipment_scenario_has_no_meeting_room_rules(self):
  self.assertNotRegex(dossier('sys-009'),r'(?i)room.?id|переговорн|для комнат|брони.*интервал')
  self.assertRegex(dossier('sys-009'),r'(?i)asset|инвентарн')
 def test_public_locales_are_not_gated_by_tenant_membership(self):
  access=next(f['answer'] for f in CARDS['api-020']['facts'] if f['id']=='access')
  self.assertIn('не требует',access)
  self.assertNotIn('quote',facts('api-020').lower())
 def test_api_key_does_not_inherit_refresh_token_family(self):
  self.assertNotRegex(facts('api-056')+' '+dossier('api-056'),r'(?i)refresh|token family')
 def test_edited_numbers_are_consistent_with_original_brief(self):
  self.assertNotIn('60 раз',facts('sys-027')+' '+dossier('sys-027'))
  self.assertNotRegex(dossier('sys-029'),r'10%|30 минут')
  self.assertNotIn('45 секунд',dossier('sys-030'))
 def test_cash_register_context_can_answer_validation_source_followup(self):
  text=dossier('int-001').lower()
  self.assertIn('карточк',text)
  self.assertIn('checksum',text)
  self.assertIn('применённ',text)
  self.assertIn('не доказыва',text)
 def test_micro_webhook_distinguishes_event_and_delivery_time(self):
  self.assertIn('попытк',dossier('api-110'))
  self.assertIn('event_id',dossier('api-110'))
 def test_micro_late_delivery_has_an_existing_manual_reconciliation_route(self):
  text=dossier('sys-111')
  self.assertIn('кабинет',text)
  self.assertIn('72',text)
  self.assertIn('7 дней',text)
if __name__=='__main__':unittest.main()
