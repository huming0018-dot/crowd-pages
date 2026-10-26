"""Temp-only terminal source proof; no Native IPC, source execution or cloud calls."""
import copy
import fcntl
import json
import sqlite3
import unittest
import test_pro_binding_continuation as fixture
B, C = fixture.B, fixture.C

class TerminalSourceUpgrade(unittest.TestCase):
    setUp = fixture.Binding.setUp
    put = fixture.Binding.put
    tx = fixture.Binding.tx
    preserve = fixture.Binding.preserve

    def source(self):
        self.run_id = '33333333-3333-4333-8333-333333333333'
        self.run = self.root/'runs'/self.run_id
        self.run.mkdir(parents=True)
        binding = {'profile':'native-messaging', 'transport':'native', 'generation':17,
                   'subject':'44444444-4444-4444-8444-444444444444',
                   'installation_id':'55555555-5555-4555-8555-555555555555',
                   'native_session':'66666666-6666-4666-8666-666666666666'}
        request = {'platform':'xhs', 'source_executor':'pro', 'session_id':self.session_id,
                   'mode':'search', 'targets':['fixture'], 'purpose':'noncommercial_research', 'max_api_requests':60}
        digest = B.sha(json.dumps(request,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
        self.context = {'schema':'crowd-participant-pro-local-v1', 'binding':binding,
                        'task_id':31, 'installation_id':binding['installation_id'], 'request_sha256':digest,
                        'native_start':{'subject':binding['subject'], 'installation_id':binding['installation_id'],
                                        'task_id':31, 'intent':'77777777-7777-4777-8777-777777777777'}}
        self.manifest = {'run_id':self.run_id, 'request':request, 'executor':{'backend':'pro'},
                         'participant_pro':copy.deepcopy(self.context)}
        self.context['captured_at'] = '2026-10-26T00:00:00+00:00'
        self.status = {'run_id':self.run_id, 'state':'completed', 'phase':'completed',
                       'exit_code':0, 'session_id':self.session_id, 'platform':'xhs'}
        self.put(self.run/'manifest.json',self.manifest); self.put(self.run/'status.json',self.status)
        self.put(self.helper/'pro-state.json',{'busy':False,'state':'stopped'})
        self.db = self.root/'cloud-outbox/outbox.sqlite3'; self.db.parent.mkdir()
        with sqlite3.connect(self.db) as db:
            db.execute('CREATE TABLE participant_runs(task INTEGER PRIMARY KEY,state TEXT,run_id TEXT,context TEXT)')
            db.execute('CREATE TABLE participant_delivery(request TEXT PRIMARY KEY,task INTEGER,content_id TEXT,params TEXT,state TEXT,receipt TEXT)')
            db.execute('INSERT INTO participant_runs VALUES(?,?,?,?)',(31,'running',self.run_id,json.dumps(self.context)))
            db.execute('INSERT INTO participant_delivery VALUES(?,?,?,?,?,?)',('original-request',31,'content','{}','delivered','original receipt'))

    def upgraded(self, tx):
        try:
            return tx.install(C.configure)
        except ValueError as error:
            self.fail(f'same-binding terminal runtime upgrade refused: {error}')

    def snapshot(self):
        paths = [self.db,self.run/'manifest.json',self.run/'status.json',self.settings,self.account]
        return {str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in paths}

    def test_same_binding_upgrade_preserves_running_row_sources_and_receipts(self):
        self.source(); before=self.snapshot()
        self.assertTrue(self.upgraded(self.tx())['configured'])
        self.assertEqual(self.snapshot(),before); self.assertEqual(len(self.calls),1); self.preserve()
        with sqlite3.connect(self.db) as db:self.assertEqual(db.execute('SELECT state FROM participant_runs').fetchone()[0],'running')

    def test_capacity_change_still_refused_but_explicit_same_value_allowed(self):
        self.source(); before=self.snapshot()
        tx=B.BindingContinuation(self.deps,self.prepared,self.plan,self.settings,self.runtime,self.helper,max_api_requests=60)
        with self.assertRaisesRegex(ValueError,'native_pending'):tx.install(C.configure)
        self.assertEqual(self.snapshot(),before)
        tx=B.BindingContinuation(self.deps,self.prepared,self.plan,self.settings,self.runtime,self.helper,max_api_requests=14)
        self.assertTrue(self.upgraded(tx)['configured']); self.assertEqual(self.snapshot(),before)

    def test_binding_request_and_terminal_negatives(self):
        self.source()
        mutations = [
            ('missing_native_start',lambda m,s:m['participant_pro'].pop('native_start')),
            ('missing_request',lambda m,s:m.pop('request')),
            ('other_session',lambda m,s:m['request'].update(session_id='88888888-8888-4888-8888-888888888888')),
            ('request_changed',lambda m,s:m['request'].update(max_api_requests=99)),
            ('other_task',lambda m,s:m['participant_pro'].update(task_id=32)),
            ('other_subject',lambda m,s:m['participant_pro']['native_start'].update(subject='88888888-8888-4888-8888-888888888888')),
            ('unknown_source',lambda m,s:s.update(state='unknown')),
            ('failed_source',lambda m,s:s.update(state='failed',exit_code=1)),
            ('finishing_source',lambda m,s:s.update(state='finishing')),
            ('unknown_upstream',lambda m,s:s.update(upstream_status='unknown')),
            ('bool_exit',lambda m,s:s.update(exit_code=False)),
            ('other_run',lambda m,s:s.update(run_id='88888888-8888-4888-8888-888888888888')),
            ('stop_evidence',lambda m,s:s.update(stop_context={'origin':'user'})),
        ]
        for name, mutate in mutations:
            with self.subTest(name=name):
                manifest,status=copy.deepcopy(self.manifest),copy.deepcopy(self.status)
                mutate(manifest,status);self.put(self.run/'manifest.json',manifest);self.put(self.run/'status.json',status)
                with self.assertRaises(ValueError):self.tx().install(C.configure)
                self.assertFalse((self.helper/'pro-config.json').exists())

    def test_stop_marker_pending_delivery_and_missing_host_refused(self):
        self.source(); marker=self.run/'stop.json';self.put(marker,{'origin':'user'})
        with self.assertRaises(ValueError):self.tx().install(C.configure)
        marker.unlink()
        with sqlite3.connect(self.db) as db:db.execute("UPDATE participant_delivery SET state='pending'")
        with self.assertRaisesRegex(ValueError,'native_pending'):self.tx().install(C.configure)
        with sqlite3.connect(self.db) as db:db.execute("UPDATE participant_delivery SET state='delivered'")
        (self.helper/'pro-state.json').unlink()
        with self.assertRaises(ValueError):self.tx().install(C.configure)

    def test_session_lock_obtained_and_proof_rechecked_inside_it(self):
        self.source();lock=self.session/'active.lock';lock.touch()
        with lock.open('r+') as held:
            fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):self.tx().install(C.configure)
        tx=self.tx()
        def changed(*args,**kwargs):
            self.put(self.run/'status.json',{**self.status,'state':'unknown'})
            return C.configure(*args,**kwargs)
        with self.assertRaises(ValueError):tx.install(changed)
        self.assertFalse((self.helper/'pro-config.json').exists()); self.preserve()

    def test_other_pending_states_and_old_incomplete_schema_still_refused(self):
        self.source()
        for state in ['unknown','finish_unknown','partial','launching','source_unknown']:
            with self.subTest(state=state):
                with sqlite3.connect(self.db) as db:db.execute('UPDATE participant_runs SET state=?',(state,))
                with self.assertRaises(ValueError):self.tx().install(C.configure)
        with sqlite3.connect(self.db) as db:
            db.execute('DROP TABLE participant_runs');db.execute('CREATE TABLE participant_runs(state TEXT)')
            db.execute("INSERT INTO participant_runs VALUES('running')")
        with self.assertRaises(ValueError):self.tx().install(C.configure)

    def test_missing_historical_binding_even_in_both_copies_refused(self):
        self.source()
        for key in ['native_start','request_sha256','binding']:
            with self.subTest(key=key):
                context=copy.deepcopy(self.context);context.pop(key)
                manifest=copy.deepcopy(self.manifest);manifest['participant_pro'].pop(key)
                self.put(self.run/'manifest.json',manifest)
                with sqlite3.connect(self.db) as db:db.execute('UPDATE participant_runs SET context=?',(json.dumps(context),))
                with self.assertRaises(ValueError):self.tx().install(C.configure)

    def test_delivery_schema_and_missing_receipt_cannot_prove_no_unknown(self):
        self.source()
        with sqlite3.connect(self.db) as db:db.execute('UPDATE participant_delivery SET receipt=NULL')
        with self.assertRaises(ValueError):self.tx().install(C.configure)
        with sqlite3.connect(self.db) as db:
            db.execute('DROP TABLE participant_delivery')
            db.execute('CREATE TABLE participant_delivery(state TEXT)')
            db.execute("INSERT INTO participant_delivery VALUES('delivered')")
        with self.assertRaises(ValueError):self.tx().install(C.configure)

if __name__=='__main__':unittest.main()
