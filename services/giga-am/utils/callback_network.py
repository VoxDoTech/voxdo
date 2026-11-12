"""Restrict callback destinations and pin TCP connections to approved IPs."""
import asyncio
import ipaddress
import socket

import httpcore
import httpx

from config import settings


def validate_callback_url(value: str) -> httpx.URL:
    try:
        url = httpx.URL(value)
        if (url.scheme not in ("http", "https") or not url.host
                or url.userinfo or url.fragment
                or url.host.lower() not in {h.lower() for h in settings.callback_allowed_hosts}):
            raise ValueError("Callback URL is not allowed")
        return url
    except (httpx.InvalidURL, ValueError) as exc:
        raise ValueError("Invalid or disallowed callback URL") from exc


def allowed_ip(value: str) -> bool:
    address = ipaddress.ip_address(value)
    # Treat IPv4-mapped IPv6 addresses as IPv4 for policy matching.
    address = getattr(address, "ipv4_mapped", None) or address
    return any(address in ipaddress.ip_network(net) for net in settings.callback_allowed_networks)


class CallbackBackend(httpcore.AsyncNetworkBackend):
    def __init__(self):
        self.backend = httpcore.AnyIOBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if host.lower() not in {h.lower() for h in settings.callback_allowed_hosts}:
            raise ValueError("Callback host is not allowed")
        async with asyncio.timeout(timeout):
            addresses = await asyncio.get_running_loop().getaddrinfo(
                host, port, type=socket.SOCK_STREAM
            )
            if not addresses or any(not allowed_ip(item[4][0]) for item in addresses):
                raise ValueError("Callback IP is not allowed")
            # Numeric destination prevents a second DNS lookup; HTTP Host and TLS
            # server_hostname still come from the original request URL.
            stream = await self.backend.connect_tcp(
                addresses[0][4][0], port, timeout=timeout,
                local_address=local_address, socket_options=socket_options,
            )
            peer = stream.get_extra_info("server_addr")
            if not peer or not allowed_ip(peer[0]):
                await stream.aclose()
                raise ValueError("Callback peer IP is not allowed")
            return stream

    async def connect_unix_socket(self, *args, **kwargs):
        raise ValueError("Unix socket callbacks are not allowed")

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


class CallbackTransport(httpx.AsyncHTTPTransport):
    def __init__(self):
        super().__init__(retries=0)
        # HTTPX exposes custom transports but no network-backend argument.
        # Keep its response adapter and supply HTTP Core's backend-aware pool.
        self._pool = httpcore.AsyncConnectionPool(network_backend=CallbackBackend())
