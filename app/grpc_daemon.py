"""Local gRPC sidecar daemon entrypoint."""

from __future__ import annotations

import asyncio
import logging
import os

from app.transport.grpc.server import serve

logger = logging.getLogger(__name__)


async def _run() -> None:
    bind_address = os.getenv("SIDECAR_GRPC_BIND", "127.0.0.1:50051")
    server = await serve(bind_address=bind_address)
    await server.wait_for_termination()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
