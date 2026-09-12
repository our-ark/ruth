"""App-switch announcements use durable keys and never need a model turn."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ruth.shopping.activity import AppActivity


class ActivityAnnouncementTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.apps = {app: SimpleNamespace(name=name) for app, name in
                     [('dayform', 'DAYFORM'), ('stride', 'STRIDE STUDIO')]}
        self.tracker = self.reopen()
        self.now = 1000
        timer = patch('ruth.shopping.activity.time.time', side_effect=lambda: self.now)
        timer.start()
        self.addCleanup(timer.stop)
        self.sent = []

    def reopen(self):
        return AppActivity(self.root, self.apps)

    def focus(self, app, product='Day One', *, ambiguous=False):
        state = self.tracker.load()
        state['apps'] = {}
        if app:
            state['apps'][app] = {'sessions': {'tab': {
                'state': 'active', 'expires_at': self.now + 45,
                'context': {'product': {'name': product}}}}}
        if ambiguous:
            state['apps']['stride'] = {'sessions': {'other': {'state': 'active', 'expires_at': self.now + 45}}}
        self.tracker.save(state)

    def send(self, *args):
        self.sent.append(args)
        return True

    def tick(self, seconds=0, sender=None):
        self.now += seconds
        return self.tracker.announce(42, sender or self.send)

    def settle(self, app, product='Day One'):
        self.focus(app, product)
        self.tick()
        self.tick(2)

    def test_first_arrival_and_switch_are_debounced_but_heartbeats_are_silent(self):
        self.focus('dayform')
        self.tick()
        self.tick(1)
        self.assertEqual(self.sent, [])
        self.tick(1)
        self.assertIn('Active app: DAYFORM', self.sent[0][1])
        self.assertIn('Viewing: Day One', self.sent[0][1])
        self.assertEqual(self.sent[0][0], 42)
        self.focus('dayform', 'Day One Lite')
        self.tick(15)
        self.tracker = self.reopen()
        self.tick(1)
        self.assertEqual(len(self.sent), 1, 'product change, heartbeat and restart must not announce again')
        self.settle('stride', 'Arc 02')
        self.assertEqual(len(self.sent), 2)
        self.assertIn('DAYFORM → STRIDE STUDIO', self.sent[-1][1])
        self.assertIn('Viewing: Arc 02', self.sent[-1][1])
        self.settle('dayform')
        self.assertEqual(len(self.sent), 3)
        self.assertIn('STRIDE STUDIO → DAYFORM', self.sent[-1][1])
        self.assertEqual(len({s[2] for s in self.sent}), 3)

    def test_quick_switch_ambiguity_and_expiry_do_not_announce(self):
        self.settle('dayform')
        self.focus('stride')
        self.tick()
        self.focus('dayform')
        self.tick(1)
        self.focus('dayform', ambiguous=True)
        self.tick(3)
        self.tick(46)
        self.focus(None)
        self.tick(5)
        self.assertEqual(len(self.sent), 1)
        # Returning to the same last announced app after unknown is quiet.
        self.focus('dayform')
        self.tick()
        self.tick(2)
        self.assertEqual(len(self.sent), 1)

    def test_multiple_sessions_on_one_app_can_announce_without_guessing_product(self):
        self.focus('dayform')
        state = self.tracker.load()
        state['apps']['dayform']['sessions']['second'] = {
            'state': 'active', 'expires_at': self.now + 45,
            'context': {'product': {'name': 'A different pair'}}}
        self.tracker.save(state)
        self.assertEqual(self.tracker.snapshot()['status'], 'ambiguous', 'the exact session remains uncertain')
        self.tick()
        self.tick(2)
        self.assertEqual(len(self.sent), 1)
        self.assertIn('Active app: DAYFORM', self.sent[0][1])
        self.assertNotIn('Viewing:', self.sent[0][1])

    def test_failure_retries_identical_key_and_original_observation_after_restart(self):
        attempts = []
        def unavailable(*args):
            attempts.append(args)
            return False
        self.focus('dayform')
        self.tick()
        self.assertFalse(self.tick(2, unavailable))
        self.tracker = self.reopen()
        self.focus('stride', 'Arc 02')
        self.assertTrue(self.tick(10))
        self.assertEqual(self.sent, attempts, 'retry preserves original text, time and deduplication key')
        self.tick()
        self.tick(2)
        self.assertEqual(len(self.sent), 2)
        self.assertIn('DAYFORM → STRIDE STUDIO', self.sent[-1][1])

    def test_crash_after_delivery_reuses_durable_sender_key(self):
        delivered, attempts = {}, []
        def durable_sender(chat, text, key):
            attempts.append(key)
            delivered.setdefault(key, text)
            return True
        self.focus('dayform')
        self.tick()
        real_save = self.tracker.save
        def crash_after_send(state):
            if state.get('announcements', {}).get('42', {}).get('last_app'):
                raise OSError('simulated crash after send')
            real_save(state)
        with patch.object(self.tracker, 'save', side_effect=crash_after_send):
            with self.assertRaises(OSError):
                self.tick(2, durable_sender)
        self.tracker = self.reopen()
        self.tick(1, durable_sender)
        self.assertEqual(len(delivered), 1)
        self.assertEqual(attempts[0], attempts[1])
        self.tick(5, durable_sender)
        self.assertEqual(len(attempts), 2)


if __name__ == '__main__':
    unittest.main()
