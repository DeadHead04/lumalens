import json
import os
import tempfile
import unittest
from pathlib import Path

import httpx

from luma_scraper import LumaClient, LumaError, load_session
from luma_scraper.client import window
from luma_scraper.cli import csv_text, output


class ClientTests(unittest.TestCase):
    def client(self, handler, **kwargs):
        return LumaClient(transport=httpx.MockTransport(handler), interval=0, **kwargs)

    def test_pagination_deduplicates(self):
        requests = []
        def handler(req):
            requests.append(req)
            if req.url.params.get('pagination_cursor'):
                return httpx.Response(200, json={'entries': [{'api_id': 'a'}, {'api_id': 'b'}], 'has_more': False})
            return httpx.Response(200, json={'entries': [{'api_id': 'a'}], 'has_more': True, 'next_cursor': 'next'})
        with self.client(handler) as c:
            r = c.paginate('/test')
        self.assertEqual(len(r['entries']), 2)
        self.assertTrue(r['complete'])
        self.assertEqual(requests[1].url.params['pagination_cursor'], 'next')

    def test_page_cap_explicit(self):
        with self.client(lambda r: httpx.Response(200, json={'entries': [], 'has_more': True, 'next_cursor': 'x'})) as c:
            result = c.paginate('/test', max_pages=1)
        self.assertFalse(result['complete'])
        self.assertEqual(result['next_cursor'], 'x')

    def test_cursor_loop(self):
        with self.client(lambda r: httpx.Response(200, json={'entries': [], 'has_more': True, 'next_cursor': 'x'})) as c:
            with self.assertRaises(LumaError) as error:
                c.paginate('/test')
            self.assertEqual(error.exception.code, 'PAGINATION_STALLED')

    def test_missing_entries_is_not_empty_success(self):
        with self.client(lambda r: httpx.Response(200, json={'message': 'changed'})) as c:
            with self.assertRaises(LumaError):
                c.paginate('/test')

    def test_http_error_does_not_leak_body_or_ticket(self):
        with self.client(lambda r: httpx.Response(403, json={'message': 'private-ticket'})) as c:
            with self.assertRaises(LumaError) as error:
                c.request('/test', ticket_key='secret')
            self.assertEqual(error.exception.code, 'FORBIDDEN')
            self.assertNotIn('secret', str(error.exception))
            self.assertNotIn('private-ticket', str(error.exception))

    def test_retry_after(self):
        calls = []
        def handler(req):
            calls.append(req)
            if len(calls) == 1:
                return httpx.Response(429, headers={'Retry-After': '0'})
            return httpx.Response(200, json={'ok': True})
        with self.client(handler) as c:
            self.assertTrue(c.request('/test')['ok'])
        self.assertEqual(len(calls), 2)

    def test_non_json(self):
        with self.client(lambda r: httpx.Response(200, text='<html>challenge</html>')) as c:
            with self.assertRaises(LumaError):
                c.request('/test')

    def test_no_cross_origin_or_redirect(self):
        with self.client(lambda r: httpx.Response(302, headers={'Location': 'https://evil.example'})) as c:
            with self.assertRaises(ValueError):
                c.request('https://evil.example')
            with self.assertRaises(LumaError):
                c.request('/test')
            with self.assertRaises(ValueError):
                c.event('https://evil.example/event')

    def test_ticket_propagation(self):
        requests = []
        def handler(req):
            requests.append(req)
            if req.url.path == '/event/get':
                return httpx.Response(200, json={'event': {'name': 'test'}, 'guest_data': {'ticket_key': 'ticket'}})
            return httpx.Response(200, json={'entries': [], 'has_more': False})
        with self.client(handler) as c:
            c.guests('evt-test')
        self.assertEqual(requests[1].url.params['ticket_key'], 'ticket')

    def test_missing_session(self):
        with self.client(lambda r: httpx.Response(200, json={'user': None})) as c:
            with self.assertRaises(LumaError):
                c.history()

    def test_timezone_inclusive_start_exclusive_end(self):
        rows = [{'event': {'start_at': t}} for t in ['2026-10-29T18:29:59Z', '2026-10-29T18:30:00Z', '2026-10-30T18:29:59Z', '2026-10-30T18:30:00Z']]
        self.assertEqual(window(rows, '2026-10-30', '2026-10-31', 'Asia/Kolkata'), rows[1:3])
        with self.assertRaises(ValueError):
            window([], '2026-10-31', '2026-10-30')

    def test_csv_formula_and_quotes(self):
        text = csv_text({'entries': [{'user': {'name': '=HYPERLINK("bad")', 'bio': 'a,b\nc'}}]})
        self.assertIn("'=HYPERLINK", text)
        self.assertIn('"a,b\nc"', text)

    def test_export_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'test.json'
            output({'entries': []}, path)
            if os.name != 'nt':
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                output({'entries': []}, path)


class SessionTests(unittest.TestCase):
    def load(self, payload):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'cookies.json'
            path.write_text(json.dumps(payload))
            return load_session(path)

    def test_storage_state_filters_domains_and_expiry(self):
        jar = self.load({'cookies': [
            {'domain': '.luma.com', 'name': 'luma.auth-session-key', 'value': 'ok', 'expires': -1},
            {'domain': 'evil-luma.com', 'name': 'secret', 'value': 'no'},
            {'domain': '.lu.ma', 'name': 'expired', 'value': 'no', 'expires': 1},
        ]})
        self.assertEqual({c.name for c in jar.jar}, {'luma.auth-session-key'})
        self.assertEqual(jar.get('luma.auth-session-key', domain='api.lu.ma'), 'ok')

    def test_cookie_map(self):
        jar = self.load({'luma.auth-session-key': 'ok'})
        self.assertEqual(jar.get('luma.auth-session-key'), 'ok')

    def test_multiple_accounts_rejected(self):
        with self.assertRaises(ValueError):
            self.load([{'domain': d, 'name': 'luma.auth-session-key', 'value': v} for d,v in [('luma.com','a'),('lu.ma','b')]])

    def test_netscape_httponly(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'cookies.txt'
            path.write_text('# Netscape HTTP Cookie File\n#HttpOnly_.lu.ma\tTRUE\t/\tTRUE\t0\tluma.auth-session-key\tok\n')
            self.assertEqual(load_session(path).get('luma.auth-session-key', domain='api.lu.ma'), 'ok')


class ExampleTests(unittest.TestCase):
    def test_batch_skips_invites_and_records_forbidden(self):
        from examples.export_registered_guests import collect
        class FakeClient:
            def history(self, **kwargs):
                return {'complete': True, 'entries': [
                    {'event': {'api_id': 'evt-invited'}, 'guest_info': {'approval_status': 'invited'}},
                    {'event': {'api_id': 'evt-approved'}, 'guest_info': {'approval_status': 'approved'}},
                    {'event': {'api_id': 'evt-hidden'}, 'guest_info': {'approval_status': 'approved'}},
                ]}
            def guests(self, event_id):
                if event_id == 'evt-hidden':
                    raise LumaError('FORBIDDEN', 'Hidden')
                if event_id != 'evt-approved':
                    raise AssertionError('Unapproved registration requested')
                return {'complete': True, 'entries': [], 'count': 0}
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / 'exports'
            self.assertEqual(collect(FakeClient(), folder), 2)
            summary = json.loads((folder / 'summary.json').read_text())
            self.assertEqual(len(summary['events']), 2)
            self.assertEqual(summary['events'][1]['error'], 'FORBIDDEN')
            self.assertFalse((folder / 'evt-invited.json').exists())
            with self.assertRaises(FileExistsError):
                collect(FakeClient(), folder)


if __name__ == '__main__':
    unittest.main()
