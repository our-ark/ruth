"""Exercise both SDKs with a headless notes app and no agent runtime or UI."""
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
SDK_PATHS = [str(ROOT / 'libraries' / name / 'src') for name in ('agent-sdk', 'app-sdk')]
sys.path[:0] = SDK_PATHS

from our_ark_agent_sdk import AgentOutput, AppClient, UAAPError
from our_ark_app_sdk import APIError, AppServer, MessageStore


class NotesStore(MessageStore):
    def message_metadata(self, body):
        return {'share_language': body.get('share_language') is True}

    def validate_shared_context(self, source, shared):
        if set(shared) - {'language'}:
            raise APIError(400, 'Only language is supported by this notes app')
        if shared and not source.get('share_language'):
            raise APIError(403, 'Language disclosure was not authorized')


class UAAPSDKTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'notes.sqlite'
        self.store = NotesStore(self.path, 'notes')
        self.server = AppServer(('127.0.0.1', 0), store=self.store,
                                agent_token='test-agent-credential', public_origin='http://127.0.0.1:0')
        self.server.public_origin = f'http://127.0.0.1:{self.server.server_port}'
        self.run_server(self.server)
        self.app = AppClient('notes', 'Notes', self.server.public_origin, 'test-agent-credential')
        self.session = self.store.session('test-user')['session_id']

    def run_server(self, server):
        threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

    def message(self, *, share=False):
        # These are app-backend calls after the app authenticates its own user.
        return self.store.message('test-user', {
            'id': 'note-message', 'session_id': self.session, 'text': 'Explain this paragraph.',
            'context': {'document_id': 'doc-1', 'selection': {'text': 'A selected paragraph.'}},
            'share_language': share,
        })

    def test_headless_round_trip_context_disclosure_and_restart(self):
        event = self.message(share=True)
        event['context']['selection']['text'] = 'Changed after submission'
        batch = self.app.events()
        self.assertEqual(batch['events'][0]['context']['selection']['text'], 'A selected paragraph.')
        self.assertNotIn('product_id', batch['events'][0]['context'])
        output: AgentOutput = {'id': 'reply-1', 'in_reply_to': 'note-message', 'text': 'Here is an explanation.',
                  'shared_context': {'language': 'en'}}
        self.assertEqual(self.app.output(self.session, output), output)
        self.assertEqual(self.app.output(self.session, output), output)
        reopened = NotesStore(self.path, 'notes')
        transcript = reopened.transcript('test-user', self.session)
        self.assertEqual(transcript['outputs'], [output])
        self.assertEqual(self.app.events(batch['cursor']), {'events': [], 'cursor': batch['cursor']})
        with self.assertRaises(UAAPError):
            self.app.output(self.session, dict(output, text='Conflicting retry'))

    def test_auth_routing_and_disclosure_are_independent_of_ui(self):
        self.message()
        with self.assertRaises(UAAPError) as caught:
            replace(self.app, token='wrong').events()
        self.assertFalse(caught.exception.retryable)
        output = {'id': 'reply-1', 'in_reply_to': 'note-message', 'text': 'Hello',
                  'shared_context': {'language': 'en'}}
        with self.assertRaises(UAAPError):
            self.app.output(self.session, output)
        other_session = self.store.session('another-user')['session_id']
        with self.assertRaises(UAAPError):
            self.app.output(other_session, dict(output, shared_context={}))
        with self.assertRaises(APIError):
            self.store.transcript('another-user', self.session)
        with self.assertRaises(APIError):
            self.store.message('another-user', {'id': 'forged', 'session_id': self.session,
                                                'text': 'Hi', 'context': {}})
        for path in ('/', '/sdk/agent-chat.js', '/ui/sessions', '/products'):
            with self.assertRaises(HTTPError) as caught:
                urlopen(self.app.base_url + path, timeout=3)
            self.assertEqual(caught.exception.code, 404)
            caught.exception.close()

    def test_generic_store_requires_explicit_return_context_policy(self):
        store = MessageStore(Path(self.temp.name) / 'plain.sqlite', 'plain')
        session = store.session('test-user')['session_id']
        context = {'page': {'selection': ['original']}}
        body = {'id': 'm1', 'session_id': session, 'text': 'Explain', 'context': context}
        store.message('test-user', body)
        context['page']['selection'].append('changed')
        self.assertEqual(store.events(0)['events'][0]['context']['page']['selection'], ['original'])
        reply = {'id': 'r1', 'in_reply_to': 'm1', 'text': 'Explanation', 'shared_context': {'secret': 'no'}}
        with self.assertRaises(APIError) as caught:
            store.output(session, reply)
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(store.output(session, dict(reply, shared_context={})), dict(reply, shared_context={}))

    def test_client_rejects_redirects_and_classifies_http_errors(self):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                requests.append(self.path)
                if self.path == '/redirect':
                    self.send_response(302)
                    self.send_header('Location', '/sink')
                    self.end_headers()
                else:
                    self.send_response(503)
                    self.end_headers()
                    self.wfile.write(b'{"error":"temporarily unavailable"}')

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.run_server(server)
        app = replace(self.app, base_url=f'http://127.0.0.1:{server.server_port}')
        with self.assertRaises(UAAPError) as caught:
            app.request('/redirect')
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(requests, ['/redirect'])
        with self.assertRaises(UAAPError) as caught:
            app.request('/unavailable')
        self.assertTrue(caught.exception.retryable)
        self.assertNotIn(app.token, repr(app))
        with self.assertRaises(ValueError):
            app.request('https://elsewhere.example/events')

    def test_invalid_batches_cannot_advance_saved_position(self):
        for batch in (
            {'events': [], 'cursor': 8},
            {'events': [{'cursor': 2, 'context': {}}, {'cursor': 2, 'context': {}}], 'cursor': 2},
            {'events': [{'cursor': 2, 'context': {}}], 'cursor': 3},
            {'events': [{'cursor': True, 'context': {}}], 'cursor': True},
        ):
            with self.subTest(batch=batch), patch.object(AppClient, 'request', return_value=batch):
                with self.assertRaises(UAAPError):
                    self.app.events(1)

    def test_context_envelopes_reject_missing_or_invalid_shapes(self):
        for fields in ({}, {'context': None}, {'context': []}, {'context': 'paragraph'}):
            batch = {'events': [{'cursor': 1, **fields}], 'cursor': 1}
            with self.subTest(fields=fields), patch.object(AppClient, 'request', return_value=batch):
                with self.assertRaisesRegex(UAAPError, 'context snapshot'):
                    self.app.events()
        for shared in (None, [], 'en'):
            with self.subTest(shared=shared), patch.object(AppClient, 'request') as request:
                with self.assertRaisesRegex(ValueError, 'shared_context'):
                    self.app.output(self.session, {'id': 'reply', 'in_reply_to': 'message',
                                                  'text': 'Hello', 'shared_context': shared})
                request.assert_not_called()

    def test_sdk_imports_are_independent_of_ruth_and_frontend(self):
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(SDK_PATHS))
        code = "import sys; import our_ark_agent_sdk, our_ark_app_sdk; assert 'ruth' not in sys.modules"
        subprocess.run([sys.executable, '-S', '-c', code], env=env, cwd=self.temp.name, check=True)

    def test_activity_extension_is_optional_and_backward_compatible(self):
        self.assertEqual(self.app.capabilities()['extensions'], [])
        with self.assertRaises(UAAPError) as caught:
            self.app.activity()
        self.assertEqual(caught.exception.status_code, 404)
        with patch.object(AppClient, 'request', side_effect=UAAPError('old app', status_code=404)):
            self.assertEqual(self.app.capabilities(), {'extensions': []})
        with patch.object(AppClient, 'request', side_effect=UAAPError('unauthorized', status_code=401)):
            with self.assertRaises(UAAPError):
                self.app.capabilities()

    def test_activity_sequence_leases_coalescing_and_message_snapshot(self):
        self.store.activity_enabled = True
        self.assertIn('context-presence/1', self.app.capabilities()['extensions'])
        self.message()
        context = {'event_id': 'context-1', 'session_id': self.session, 'sequence': 1,
                   'type': 'context.updated', 'context': {'document_id': 'doc-2'}}
        self.store.activity('test-user', context)
        body = {'event_id': 'presence-1', 'session_id': self.session, 'sequence': 1,
                'type': 'presence.updated', 'state': 'active'}
        with patch('our_ark_app_sdk.store.time.time', return_value=1000):
            original = self.store.activity('test-user', body)
        with patch('our_ark_app_sdk.store.time.time', return_value=1100):
            self.assertEqual(self.store.activity('test-user', body), original)
        self.assertEqual(original['event']['expires_at'], 1045, 'retries do not extend a lease')
        with self.assertRaises(APIError) as caught:
            self.store.activity('test-user', dict(body, state='inactive'))
        self.assertEqual(caught.exception.status, 409)
        for sequence in range(2, 102):
            self.store.activity('test-user', dict(body, sequence=sequence, event_id=f'p-{sequence}'))
        self.assertFalse(self.store.activity('test-user', body)['accepted'])
        batch = self.app.activity()
        self.assertEqual(len(batch['events']), 2, 'heartbeats coalesce instead of growing a backlog')
        self.assertEqual(self.app.activity(batch['cursor'])['events'], [])
        self.assertEqual(self.app.events()['events'][0]['context']['document_id'], 'doc-1')
        self.assertEqual(len(self.store.transcript('test-user', self.session)['messages']), 1)
        reopened = NotesStore(self.path, 'notes', activity_enabled=True)
        self.assertEqual(reopened.activity_events(0)['events'], batch['events'])
        self.assertFalse(reopened.activity('test-user', body)['accepted'])
        with self.assertRaises(UAAPError):
            self.app.output(self.session, {'id': 'bad-reply', 'in_reply_to': 'context-1', 'text': 'No'})

    def test_activity_account_scope_and_validation(self):
        self.store.activity_enabled = True
        body = {'event_id': 'p1', 'session_id': self.session, 'sequence': 1,
                'type': 'presence.updated', 'state': 'active'}
        with self.assertRaises(APIError) as caught:
            self.store.activity('someone-else', body)
        self.assertEqual(caught.exception.status, 404)
        for fields in ({'sequence': True}, {'sequence': 0}, {'sequence': -1}, {'sequence': 1.5},
                       {'state': 'maybe'}, {'type': 'message'}, {'event_id': '../bad'},
                       {'type': 'context.updated', 'context': []}):
            with self.subTest(fields=fields), self.assertRaises(APIError):
                self.store.activity('test-user', dict(body, **fields))
        self.store.activity('test-user', body)
        with self.assertRaises(UAAPError):
            replace(self.app, token='wrong').activity()
        other = self.store.session('someone-else')['session_id']
        self.store.activity('someone-else', dict(body, session_id=other, state='inactive'))
        self.assertEqual(len(self.app.activity()['events']), 2)

    def test_activity_sdk_rejects_malformed_and_foreign_events(self):
        self.store.activity_enabled = True
        self.store.activity('test-user', {'event_id': 'p1', 'session_id': self.session, 'sequence': 1,
                                         'type': 'presence.updated', 'state': 'active'})
        batch = self.app.activity()
        for fields in ({'app_id': 'another-app'}, {'cursor': True}, {'sequence': 0},
                       {'expires_at': float('nan')}, {'expires_at': 1e30}, {'state': 'maybe'},
                       {'type': 'context.updated', 'context': None}):
            invalid = dict(batch, events=[dict(batch['events'][0], **fields)])
            with self.subTest(fields=fields), patch.object(AppClient, 'request', return_value=invalid):
                with self.assertRaises(UAAPError):
                    self.app.activity()


if __name__ == '__main__':
    unittest.main()
