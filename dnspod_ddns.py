#!/usr/bin/env python
#-*- coding: utf-8 -*-

'''
Usage:
  dnspod_ddns.py [options]

Options:
  -h --help      Show this screen.
  -t TIME        Check IP change every TIME seconds [default: 60].
  -l LOG_PATH    Program log file [default: /var/log/dnspod_ddns.log].
  -p PID_FILE    Use PID_FILE as daemon's pid file [default: /var/run/dnspod_ddns.pid].
  -d ACTION      Run this script as a daemon (e.g. start,stop,restart).

'''

def handle_import_error():
    print 'Please install 3rd-party modules required by dnspod_ddns.py with following command:'
    print '  sudo pip install -r requirements.txt'
    import sys
    sys.exit()

try:
    from daemon import runner
except ImportError:
    handle_import_error()
import docopt
import logging
import logging.handlers
import os
import socket
import sys
import time

try:
    from dnspod.base import BaseAPI
    from dnspod.domain import DomainAPI
    from dnspod.record import Record, RecordAPI
except ImportError:
    handle_import_error()

import config

class App(object):
    '''
    main application called by daemon.runner
    '''

    def __init__(self, args):
        self.stdin_path = os.devnull
        self.stdout_path = os.devnull
        self.stderr_path = os.devnull
        self.pidfile_path = args['-p']
        self.pidfile_timeout = 3

        self._args = args

    def run(self):
        # Set up logger
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s %(levelname)s] %(message)s')
        if self._args['-d'] == None:
            handler = logging.StreamHandler()
        else:
            handler = logging.handlers.RotatingFileHandler(self._args['-l'],
                                                           maxBytes=1*1024*1024,
                                                           backupCount=1)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        bapi = BaseAPI(config.LOGIN_EMAIL, config.LOGIN_PASSWORD)
        dapi = DomainAPI(bapi)
        rapi = RecordAPI(bapi)
        domain = dapi.info(domain=config.DOMAIN)
        record_list = rapi.list(domain.id)
        record = None
        for rec in record_list:
            if rec.sub_domain == config.SUB_DOMAIN and \
               rec.record_type == Record.TYPE_A:
                record = rec
                break
        if record == None:
            logger.error("Couldn't get A record of domain: %s.%s",
                         config.SUB_DOMAIN, config.DOMAIN)
            return

        last_ip = record.value
        while True:
            try:
                current_ip = get_ip()
            except socket.error, e:
                logger.error('Get current IP error: %s', e)
            else:
                if current_ip != last_ip:
                    logger.info('IP change from %s to %s, update DNS record',
                                last_ip, current_ip)
                    rapi.ddns(record.domain_id, record.id, record.sub_domain,
                              record.record_line, current_ip)
                    last_ip = current_ip
                else:
                    logger.info('IP not change, check after %d seconds',
                                int(self._args['-t']))
            time.sleep(int(self._args['-t']))

def get_ip():
    sock = socket.create_connection(('ns1.dnspod.net', 6666), timeout=30)
    ip = sock.recv(16)
    sock.close()
    return ip

def main():
    try:
        arguments = docopt.docopt(__doc__)
    except docopt.DocoptExit:
        print __doc__.strip()
        return
    app = App(arguments)
    action = arguments['-d']
    if action != None:
        if action in ['start', 'stop', 'restart']:
            sys.argv[1] = action
            daemon_runner = runner.DaemonRunner(app)
            daemon_runner.do_action()
        else:
            print __doc__.strip()
            return
    else:
        app.run()

if __name__ == '__main__':
    main()
