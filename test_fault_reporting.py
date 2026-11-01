import unittest,sys,types,smtplib
from unittest.mock import Mock,patch
from utils.faults import FaultReporter

class Tests(unittest.TestCase):
 def test_heartbeat_and_positive_recovery(self):
  now=[0];emit=Mock(return_value=True);r=FaultReporter('test',emit,lambda:now[0])
  r.observe('TEST','a',True,'failed')
  for i in range(1,60):now[0]=i;r.observe('TEST','a',True,'failed')
  self.assertEqual(emit.call_count,1)
  now[0]=60;r.observe('TEST','a',True,'failed');self.assertEqual(emit.call_count,2)
  now[0]=61;r.observe('TEST','a',False,'healthy');self.assertEqual(emit.call_args.args[2],'recovered')
  r.observe('TEST','a',False,'healthy');self.assertEqual(emit.call_count,3)
 def test_retry_failure_and_restart_recovery(self):
  now=[0];emit=Mock(return_value=False);r=FaultReporter('test',emit,lambda:now[0])
  r.observe('TEST','a',False,'healthy');self.assertEqual(emit.call_count,1)
  now[0]=29;r.observe('TEST','a',False,'healthy');self.assertEqual(emit.call_count,1)
  now[0]=30;emit.return_value=True;r.observe('TEST','a',False,'healthy');self.assertEqual(emit.call_count,2)
  r.observe('TEST','a',True,'failed');self.assertEqual(emit.call_count,3)
  r.observe('TEST','a',True,'failed',critical=True);self.assertEqual(emit.call_count,4)
 def test_reporting_exception_does_not_stop_control(self):
  r=FaultReporter('test',Mock(side_effect=ValueError('sample')))
  self.assertFalse(r.observe('TEST','a',True,'failed'))
 def mail(self):
  # No authentication module or actual event transport is loaded by mail tests.
  fake=types.ModuleType('utils.event');fake.Event=Mock();fake.EventSeverity=Mock();fake.EventType=Mock()
  logger=types.ModuleType('utils.logging');logger.get_module_logger=Mock(return_value=Mock())
  with patch.dict(sys.modules,{'utils.event':fake,'utils.logging':logger}):
   sys.modules.pop('utils.mail',None)
   from utils.mail import EmailSender,Email
  sender=EmailSender('smtp.invalid',587,'user','do-not-persist')
  sender._faults=FaultReporter('Mail Util',Mock(return_value=True))
  return sender,Email('test subject','private body',['recipient@example.invalid'])
 def test_mail_auth_and_recovery_without_live_email(self):
  sender,email=self.mail();server=Mock();server.login.side_effect=smtplib.SMTPAuthenticationError(535,b'do-not-persist')
  with patch('utils.mail.smtplib.SMTP') as smtp:
   smtp.return_value.__enter__.return_value=server
   sender.send_email(email)
   args=sender._faults.emit.call_args.args
   self.assertEqual(args[0],'MAIL_AUTH');self.assertNotIn('do-not-persist',str(args))
   server.login.side_effect=None;server.sendmail.return_value={}
   sender.send_email(email)
   self.assertTrue(any(c.args[0]=='MAIL_AUTH' and c.args[2]=='recovered' for c in sender._faults.emit.call_args_list))
   self.assertEqual(smtp.call_args.kwargs['timeout'],15)
   before=server.sendmail.call_count;sender.send_email(email);self.assertEqual(server.sendmail.call_count,before)
 def test_partial_rejection_is_not_success_and_does_not_resend_accepted_recipients(self):
  sender,email=self.mail();server=Mock();server.sendmail.return_value={'recipient@example.invalid':(550,b'private response')}
  with patch('utils.mail.smtplib.SMTP') as smtp:
   smtp.return_value.__enter__.return_value=server;sender.send_email(email)
   report=next(c.args for c in sender._faults.emit.call_args_list if c.args[0]=='MAIL_RECIPIENT')
   self.assertEqual(report[2],'fault');self.assertNotIn('recipient@example.invalid',str(report))
   sender.send_email(email);self.assertEqual(server.sendmail.call_count,1)

if __name__=='__main__':unittest.main(verbosity=2)
