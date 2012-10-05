import logging
import re
import subprocess
from setproctitle import setproctitle
from statsd_ostools import parser

log = logging.getLogger(__name__)
workers = []

re_space = re.compile(r'\s+')
re_slash = re.compile(r'/+')
re_nonalphanum = re.compile(r'[^a-zA-Z_\-0-9\.]')

class Worker(object):
    def __init__(self, statsd, interval):
        self.statsd = statsd
        self.interval = interval

    def clean_key(self, key):
        return \
        re_nonalphanum.sub('',
           re_slash.sub('-',
               re_space.sub('_', key.replace('%', 'p'))
            )
        )

    def get_cmd_string(self):
        return ' '.join(self.get_cmd_argv())

    def run(self):
        setproctitle('statsd-ostools: %s' % self.get_cmd_string())
        try:
            p = subprocess.Popen(self.get_cmd_argv(), stdout=subprocess.PIPE)
            parser = self.parser(p.stdout)
            while True:
                data = parser.parse_one()
                self.send(data)

        except KeyboardInterrupt:
            pass

        return 0

@workers.append
class IOStatWorker(Worker):
    name = 'iostat'
    parser = parser.IOStatParser

    def get_cmd_argv(self):
        return ['iostat', '-xk', str(self.interval)]

    def send(self, data):
        for row in data:
            dev = row[0][1]
            prefix = '%s.%s.' % (self.name, dev)
            for k, v in row[1:]:
                key = prefix + self.clean_key(k)
                log.debug('%s: %s' % (key, v))
                self.statsd.gauge(key, v)

@workers.append
class MPStatWorker(Worker):
    name = 'mpstat'
    parser = parser.MPStatParser

    def get_cmd_argv(self):
        return ['mpstat', '-P', 'ALL', str(self.interval)]

    def send(self, data):
        for row in data:
            cpu = row[0][1]
            prefix = '%s.%s.' % (self.name, cpu)
            for k, v in row[1:]:
                key = prefix + self.clean_key(k)
                log.debug('%s: %s' % (key, v))
                self.statsd.gauge(key, v)

@workers.append
class VMStatWorker(Worker):
    name = 'vmstat'
    parser = parser.VMStatParser

    def get_cmd_argv(self):
        return ['vmstat', str(self.interval)]

    def send(self, data):
        prefix = '%s.' % self.name
        for k, v in data:
            key = prefix + self.clean_key(k)
            log.debug('%s: %s' % (key, v))
            self.statsd.gauge(key, v)