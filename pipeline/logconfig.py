"""Logging set-up (ADR 0064): the program's own log lines to standard output, and to a syslog server when one is set.

`SYSLOG_HOST` turns syslog on; `SYSLOG_PORT` (default 514) and `SYSLOG_PROTOCOL` (`udp` or `tcp`, default `udp`)
say where and how. The three loggers `app`, `pipeline` and `library` are the program's: uvicorn's access lines
are not sent. Nothing here reads or prints a key.
"""

import logging
import logging.handlers
import socket
import sys
from collections.abc import Mapping

LOGGERS = ('app', 'pipeline', 'library')
MARK = '_tagwright_handler'
IDENT = 'tagwright: '


class _Line(logging.Formatter):
	"""The same message with an end-of-line, as syslog over TCP frames its lines."""

	def format(self, record: logging.LogRecord) -> str:
		return super().format(record) + '\n'


def _syslog_handler(host: str, port: int, tcp: bool) -> logging.Handler:
	handler = logging.handlers.SysLogHandler(
		address=(host, port), socktype=socket.SOCK_STREAM if tcp else socket.SOCK_DGRAM
	)
	handler.ident = IDENT
	handler.append_nul = False
	fmt = '%(levelname)s %(name)s: %(message)s'
	handler.setFormatter(_Line(fmt) if tcp else logging.Formatter(fmt))
	return handler


def settings_of(env: Mapping[str, str]) -> tuple[str, int, bool] | None:
	"""(host, port, tcp) when SYSLOG_HOST is set; a bad port or protocol is a start-up error."""
	host = env.get('SYSLOG_HOST', '').strip()
	if not host:
		return None
	protocol = env.get('SYSLOG_PROTOCOL', 'udp').strip().lower()
	if protocol not in ('udp', 'tcp'):
		raise SystemExit(f'SYSLOG_PROTOCOL must be udp or tcp, not {protocol!r}')
	try:
		port = int(env.get('SYSLOG_PORT', '514'))
	except ValueError:
		port = 0
	if not 0 < port < 65536:
		raise SystemExit(f'SYSLOG_PORT must be a port number, not {env.get("SYSLOG_PORT")!r}')
	return host, port, protocol == 'tcp'


def configure(env: Mapping[str, str]) -> None:
	"""Attach the handlers to the program's loggers; calling it again replaces them."""
	out = logging.StreamHandler(sys.stdout)
	out.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
	handlers: list[logging.Handler] = [out]
	where = settings_of(env)
	problem = ''
	if where:
		try:
			handlers.append(_syslog_handler(*where))
		except OSError as e:  # a TCP server that is not there yet: the program still starts
			problem = f'syslog {where[0]}:{where[1]} is not reachable ({e}); logging to standard output only'
	for name in LOGGERS:
		logger = logging.getLogger(name)
		logger.setLevel(logging.INFO)
		for old in [h for h in logger.handlers if getattr(h, MARK, False)]:
			logger.removeHandler(old)
			old.close()
		for h in handlers:
			setattr(h, MARK, True)
			logger.addHandler(h)
	log = logging.getLogger('app')
	if problem:
		log.warning(problem)
	elif where:
		log.info(
			'logging to syslog %s:%d over %s', where[0], where[1], 'tcp' if where[2] else 'udp'
		)
