"""Release regressions: CLI contracts, failures, exports, and login lifecycle."""
import contextlib
import io
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from luma_scraper import LumaClient, LumaError, load_session
from luma_scraper.cli import main, output
from luma_scraper.sessions import login


class ReleaseTests(unittest.TestCase):
    def client(self, handler):
        return LumaClient(transport=httpx.MockTransport(handler), interval=0, retries=0)

    def cli(self, args, handler):
        with self.client(handler) as client, patch('luma_scraper.cli.LumaClient', return_value=client):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                status = main(args)
        return status, out.getvalue(), err.getvalue()

    def test_whoami_only_returns_identity(self):
        status, out, _ = self.cli(['whoami'], lambda r: httpx.Response(200, json={'user': {'name': 'Test User', 'api_id': 'usr-test', 'private': 'not-exported'}}))
        self.assertEqual(status, 0)
        self.assertNotIn('private', out)
        self.assertEqual(json.loads(out)['name'], 'Test User')

    def test_cli_auth_error(self):
        status, out, err = self.cli(['history'], lambda r: httpx.Response(401))
        self.assertEqual(status, 1)
        self.assertEqual(out, '')
        self.assertIn('AUTH_REQUIRED', err)

    def test_cli_truncation_exit_and_json(self):
        def handler(req):
            if req.url.path == '/event/get':
                return httpx.Response(200, json={'event': {'name': 'Test'}})
            return httpx.Response(200, json={'entries': [{'api_id': 'g-one'}], 'has_more': True, 'next_cursor': 'next'})
        status, out, err = self.cli(['guests', '--event', 'evt-test', '--max-pages', '1'], handler)
        self.assertEqual(status, 2)
        self.assertFalse(json.loads(out)['complete'])
        self.assertIn('incomplete', err)

    def test_invalid_inputs_do_not_make_requests(self):
        def forbidden(req):
            self.fail('Invalid input caused network activity')
        for args in [
            ['history','--timezone','Not/AZone'],
            ['guests','--event','evt-test','--page-size','0'],
            ['discover','--city','london','--radius-km','nan'],
            ['discover','--city','london','--max-pages','0'],
            ['guests'],
        ]:
            with self.subTest(args=args):
                code, _, err = self.cli(args, forbidden)
                self.assertEqual(code, 1)
                self.assertNotIn('Traceback', err)

    def test_malformed_page(self):
        with self.client(lambda r: httpx.Response(200, text='<script id="__NEXT_DATA__">{"props":null}</script>')) as c:
            with self.assertRaises(LumaError) as error:
                c.place('london')
            self.assertEqual(error.exception.code, 'SCHEMA_CHANGED')

    def test_null_event_user_and_bad_identifier(self):
        with self.client(lambda r: httpx.Response(200, json={'entries': [{'event': None, 'user': None}], 'has_more': False})) as c:
            self.assertTrue(c.paginate('/test')['complete'])
        with self.client(lambda r: httpx.Response(200, json={'entries': [{'api_id': []}], 'has_more': False})) as c:
            # Empty identifiers are absent, while nonempty structured IDs must fail.
            self.assertTrue(c.paginate('/test')['complete'])
        with self.client(lambda r: httpx.Response(200, json={'entries': [{'api_id': ['bad']}], 'has_more': False})) as c:
            with self.assertRaises(LumaError):
                c.paginate('/test')

    def test_csv_sidecar_conflict_rolls_back(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'guests.csv'
            meta = Path(str(path) + '.meta.json')
            meta.write_text('original', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                output({'entries': []}, path, 'csv')
            self.assertFalse(path.exists())
            self.assertEqual(meta.read_text(encoding='utf-8'), 'original')

    def test_unicode_exports_and_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'guests.csv'
            output({'entries': [{'user': {'name': 'नमस्ते 東京 👋'}}], 'complete': False}, path, 'csv')
            self.assertIn('नमस्ते 東京 👋', path.read_text(encoding='utf-8'))
            self.assertFalse(json.loads(Path(str(path)+'.meta.json').read_text(encoding='utf-8'))['complete'])

    def test_null_user_csv(self):
        with tempfile.TemporaryDirectory() as d:
            output({'entries': [{'user': None}]}, Path(d)/'empty.csv', 'csv')

    def test_session_bom_and_bad_shapes(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'session.json'
            p.write_text(json.dumps({'luma.auth-session-key': 'synthetic'}), encoding='utf-8-sig')
            self.assertTrue(list(load_session(p).jar))
            for payload in [{'cookies': None}, [None], [{'domain':'lu.ma','name':'x','value':'y','path':None}], [{'domain':'lu.ma','name':'x','value':'y','expires':float('nan')}]]:
                p.write_text(json.dumps(payload), encoding='utf-8')
                with self.subTest(payload=payload), self.assertRaises(ValueError):
                    load_session(p)

    def test_no_retry_auth_or_forbidden(self):
        for status in [401,403]:
            calls=[]
            def handler(req):
                calls.append(req)
                return httpx.Response(status)
            with LumaClient(transport=httpx.MockTransport(handler), interval=0) as c:
                with self.assertRaises(LumaError):
                    c.request('/test')
            self.assertEqual(len(calls),1)

    def test_transport_timeout_sanitized(self):
        def handler(req):
            raise httpx.ReadTimeout('private-url-and-cookie')
        with self.client(handler) as c:
            with self.assertRaises(LumaError) as error:
                c.request('/test')
            self.assertEqual(error.exception.code,'NETWORK')
            self.assertNotIn('private',str(error.exception))

    def test_long_retry_after_does_not_sleep(self):
        with LumaClient(transport=httpx.MockTransport(lambda r: httpx.Response(429, headers={'Retry-After':'120'})), interval=0) as c:
            with patch('luma_scraper.client.time.sleep') as sleep, self.assertRaises(LumaError):
                c.request('/test')
            self.assertTrue(all(call.args[0] < 1 for call in sleep.call_args_list))

    def test_client_parameter_validation(self):
        for params in [{'retries':-1},{'timeout':0},{'interval':float('nan')}]:
            with self.subTest(params=params), self.assertRaises(ValueError):
                LumaClient(**params)


class LoginTests(unittest.TestCase):
    def setup_browser(self):
        module = types.ModuleType('playwright.sync_api')
        module.Error = type('BrowserError',(Exception,),{})
        browser = MagicMock()
        runtime = MagicMock()
        runtime.chromium.launch.return_value = browser
        module.sync_playwright = MagicMock()
        module.sync_playwright.return_value.__enter__.return_value = runtime
        return module, browser, runtime

    def test_login_verifies_and_saves_only_luma(self):
        module, browser, runtime = self.setup_browser()
        browser.new_context.return_value.cookies.return_value = [
            {'domain':'.luma.com','name':'luma.auth-session-key','value':'synthetic'},
            {'domain':'other.example','name':'other','value':'never-save'},
        ]
        with tempfile.TemporaryDirectory() as d, patch.dict('sys.modules', {'playwright.sync_api':module}), patch('luma_scraper.client.LumaClient.me',return_value={'user':{'api_id':'usr-test'}}) as me:
            path = Path(d)/'session.json'
            login(path)
            self.assertEqual(len(json.loads(path.read_text())['cookies']),1)
            me.assert_called_once()
            browser.close.assert_called_once()
            runtime.chromium.launch.assert_called_once_with(channel='chrome',headless=False)

    def test_login_timeout_does_not_save(self):
        module,browser,_ = self.setup_browser()
        with tempfile.TemporaryDirectory() as d, patch.dict('sys.modules',{'playwright.sync_api':module}), patch('luma_scraper.sessions.time.monotonic',side_effect=[0,301]):
            path=Path(d)/'session.json'
            with self.assertRaisesRegex(ValueError,'timed out'):
                login(path)
            self.assertFalse(path.exists())
            browser.close.assert_called_once()

    def test_login_browser_failure_sanitized(self):
        module,_,runtime=self.setup_browser()
        runtime.chromium.launch.side_effect=module.Error('private-runtime-detail')
        with tempfile.TemporaryDirectory() as d, patch.dict('sys.modules',{'playwright.sync_api':module}):
            with self.assertRaises(ValueError) as error:
                login(Path(d)/'session.json')
            self.assertNotIn('private',str(error.exception))
