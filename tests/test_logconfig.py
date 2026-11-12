"""Logging to standard output and, when SYSLOG_HOST is set, to a syslog server (ADR 0064)."""

import logging
import socket
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import app as tagwright
from pipeline import logconfig


@pytest.fixture(autouse=True)
def clean_loggers() -> Iterator[None]:
	yield
	for name in logconfig.LOGGERS:  # leave no handlers behind for the other tests
		logger = logging.getLogger(name)
		for h in [h for h in logger.handlers if getattr(h, logconfig.MARK, False)]:
			logger.removeHandler(h)
			h.close()


def test_without_syslog_host_only_standard_output_is_used(
	capsys: pytest.CaptureFixture[str],
) -> None:
	logconfig.configure({})
	logging.getLogger('app').info('hello %s', 'world')
	out = capsys.readouterr().out
	assert 'INFO app: hello world' in out
	handlers = logging.getLogger('app').handlers
	assert not any(isinstance(h, logging.handlers.SysLogHandler) for h in handlers)


def test_a_line_goes_to_a_udp_syslog_server_with_priority_and_ident() -> None:
	server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	server.bind(('127.0.0.1', 0))
	server.settimeout(3)
	env = {'SYSLOG_HOST': '127.0.0.1', 'SYSLOG_PORT': str(server.getsockname()[1])}
	logconfig.configure(env)
	logging.getLogger('pipeline.run').warning('step failed')
	first = server.recv(4096)
	data = server.recv(4096)
	server.close()
	assert b'logging to syslog 127.0.0.1' in first  # the set-up announces itself
	assert data == b'<12>tagwright: WARNING pipeline.run: step failed'  # user facility, warning


def test_tcp_lines_end_with_a_newline() -> None:
	server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	server.bind(('127.0.0.1', 0))
	server.listen(1)
	server.settimeout(3)
	env = {
		'SYSLOG_HOST': '127.0.0.1',
		'SYSLOG_PORT': str(server.getsockname()[1]),
		'SYSLOG_PROTOCOL': 'TCP',
	}
	logconfig.configure(env)
	conn, _ = server.accept()
	conn.settimeout(3)
	logging.getLogger('library.executor').info('moved 2 files')
	data = b''
	while b'moved 2 files' not in data:
		data += conn.recv(4096)
	conn.close()
	server.close()
	lines = data.split(b'\n')
	assert lines[0].startswith(b'<14>tagwright: INFO app: logging to syslog')
	assert lines[1] == b'<14>tagwright: INFO library.executor: moved 2 files' and lines[2] == b''


@pytest.mark.parametrize(
	('env', 'message'),
	[
		({'SYSLOG_HOST': 'h', 'SYSLOG_PROTOCOL': 'icmp'}, 'udp or tcp'),
		({'SYSLOG_HOST': 'h', 'SYSLOG_PORT': 'x'}, 'port number'),
		({'SYSLOG_HOST': 'h', 'SYSLOG_PORT': '70000'}, 'port number'),
	],
)
def test_a_bad_setting_is_a_startup_error(env: dict[str, str], message: str) -> None:
	with pytest.raises(SystemExit, match=message):
		logconfig.configure(env)


def test_an_unreachable_tcp_server_does_not_stop_the_program(
	capsys: pytest.CaptureFixture[str],
) -> None:
	probe = socket.socket()
	probe.bind(('127.0.0.1', 0))
	port = probe.getsockname()[1]
	probe.close()  # nobody listens there now
	logconfig.configure(
		{'SYSLOG_HOST': '127.0.0.1', 'SYSLOG_PORT': str(port), 'SYSLOG_PROTOCOL': 'tcp'}
	)
	logging.getLogger('app').info('still here')
	out = capsys.readouterr().out
	assert 'still here' in out


def test_configuring_twice_does_not_duplicate_lines(capsys: pytest.CaptureFixture[str]) -> None:
	logconfig.configure({})
	logconfig.configure({})
	logging.getLogger('app').info('once')
	assert capsys.readouterr().out.count('once') == 1


def test_saving_the_settings_logs_the_event_but_never_a_key(
	client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
	secret = 'dsc_SECRET_KEY_123'
	with caplog.at_level(logging.INFO, logger='app'):
		r = client.post(
			'/api/settings',
			json={
				'input': str(tagwright.ROOT),
				'output': str(tagwright.INGEST),
				'discogs_api_key': secret,
			},
		)
	assert r.status_code == 200
	assert 'settings saved' in caplog.text and secret not in caplog.text
