import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from store_parsers.ribasmith import RibaSmithParser


class RibaSmithTests(unittest.TestCase):
    def test_robot_search_does_not_report_missing_deep_pagination(self):
        from price_robot import fetch_store_candidates
        with patch.object(self.parser, "_fetch_page", return_value={"items": [], "has_more": False}):
            candidates, error = fetch_store_candidates(self.parser, "ARROZ 2 LB", None, {}, ["arroz"])
        self.assertEqual(candidates, [])
        self.assertEqual(error, "")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parser = RibaSmithParser(Path(self.temp.name) / "cache.sqlite3", max_retries=1)
        self.addCleanup(self.parser.close)
        self.payload = {"ok": True, "productos": [
            {"sku": "123", "nombre": "ARROZ", "size": "2 LB",
             "precio_base": 2.50, "preciofinal": 2.25}
        ]}

    def flight(self, payload):
        return '1:"$Sreact.fragment"\n4:I[123,[],"default"]\n6:' + json.dumps(
            ["$", "$L4", None, {"children": ["$", "$L5", None,
             {"frase": "arroz", "initialData": payload}]}])

    def test_nested_flight_and_direct_json(self):
        for text in (self.flight(self.payload), json.dumps(self.payload),
                     "a:" + json.dumps(self.payload),
                     json.dumps({"initialData": self.payload}, indent=2)):
            with self.subTest(text=text[:50]):
                self.assertEqual(self.parser._extract_payload(text), self.payload)

    def test_empty_results_are_distinct_from_missing_payload(self):
        empty = {"ok": True, "productos": []}
        self.assertEqual(self.parser._extract_payload(self.flight(empty)), empty)
        for text in ('0:{"loading":true}', '<html>Unavailable</html>', '1:{invalid}'):
            self.assertEqual(self.parser._extract_payload(text), {})

    def test_search_needs_no_action_id_or_prefetch(self):
        headers = self.parser._headers()
        self.assertEqual(headers["rsc"], "1")
        self.assertNotIn("next-router-prefetch", headers)
        self.assertNotIn("next-action", headers)
        session = Mock()
        session.get.return_value = Mock(status_code=200, text=self.flight(self.payload))
        with patch.object(self.parser, "_session", return_value=session):
            result = self.parser._search_page("arroz", 1)
        self.assertEqual(result["items"][0]["sku"], "123")
        self.assertEqual(result["items"][0]["regular_price"], 2.50)
        self.assertEqual(result["items"][0]["final_price"], 2.25)
        self.assertEqual(session.get.call_args.kwargs["params"], {"q": "arroz"})
        session.post.assert_not_called()

    def test_broken_responses_are_not_cached_as_empty_searches(self):
        session = Mock()
        for body in ('0:{"loading":true}', self.flight({"ok": False, "productos": []})):
            session.get.return_value = Mock(status_code=200, text=body)
            with patch.object(self.parser, "_session", return_value=session):
                with self.assertRaisesRegex(RuntimeError, "Riba Smith request failed"):
                    self.parser._search_page("arroz", 1)
            self.assertIsNone(self.parser._disk_cache_get(self.parser._cache_key("arroz", 1)))

    def test_valid_empty_search(self):
        session = Mock()
        session.get.return_value = Mock(status_code=200, text=self.flight({"ok": True, "productos": []}))
        with patch.object(self.parser, "_session", return_value=session):
            self.assertEqual(self.parser._fetch_page("no matches", 1), {"items": [], "has_more": False})


if __name__ == "__main__":
    unittest.main()
