from contextlib import contextmanager

import pytest

import gevent.server
from geventhttpclient.connectionpool import ConnectionPool, ProxyError

listener = ('127.0.0.1', 54323)


@contextmanager
def server(handler):
    server = gevent.server.StreamServer(
        listener,
        handle=handler)
    server.start()
    try:
        yield
    finally:
        server.stop()


def make_proxy_response(on_connect_response=None, proxy_response=None):

    def _handle(sock, addr):
        sock.recv(1024)
        if on_connect_response is not None:
            sock.sendall(on_connect_response)
            if proxy_response:
                gevent.sleep(1)
                sock.sendall(proxy_response)
                sock.close()

    return _handle


def closed_socket(sock, addr):
    sock.close()


@pytest.fixture()
def connection_pool():
    return ConnectionPool(*listener,
                          request_host='test',
                          request_port=443,
                          use_proxy=True)


class TestRaiseProxyError:
    def test_not_200_code(self, connection_pool):
        with server(make_proxy_response(b"HTTP/1.1 429 \r\n\r\n")):
            with pytest.raises(ProxyError):
                connection_pool.get_socket()

    def test_empty_response_from_proxy(self, connection_pool):
        with server(make_proxy_response(b"")):
            with pytest.raises(ProxyError):
                connection_pool.get_socket()

    def test_proxy_does_not_respond(self, connection_pool):
        with server(make_proxy_response()):
            with pytest.raises(ProxyError):
                connection_pool.get_socket()

    def test_invalid_response_from_proxy(self, connection_pool):
        with server(make_proxy_response(b"qwertyuiop")):
            with pytest.raises(ProxyError):
                connection_pool.get_socket()

    def test_invalid_status_code_from_proxy(self, connection_pool):
        with server(make_proxy_response(b"HTTP/1.1 qwerty \r\n\r\n")):
            with pytest.raises(ProxyError):
                connection_pool.get_socket()

    def test_sock_was_closed(self, connection_pool):
        with server(closed_socket):
            with pytest.raises(ProxyError):
                connection_pool.get_socket()


class TestConnectionPool:
    def test_use_proxy(self, connection_pool):
        with server(
                make_proxy_response(b"HTTP/1.1 200 \r\n\r\n",
                                    b"some response"),
        ):
            socket = connection_pool.get_socket()
            assert b"some response" == socket.recv(1024)
