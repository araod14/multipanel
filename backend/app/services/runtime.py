"""Docker-backed lifecycle for per-user Freqtrade containers.

Wraps the Docker SDK behind a small interface so the provisioning service does not
talk to Docker directly. Containers join a private bridge network and publish NO
host ports — only the control plane (also on that network in production) reaches
them, by container name on port 8080.
"""

from dataclasses import dataclass, field
from typing import Any

import docker
from docker.errors import NotFound
from docker.models.containers import Container


@dataclass
class ContainerSpec:
    """Everything needed to launch one Freqtrade container."""

    name: str
    image: str
    command: list[str]
    environment: dict[str, str]
    # host_path -> container_path bind mounts
    binds: dict[str, str] = field(default_factory=dict)
    network: str = "control-plane-bots"


class BotRuntime:
    """Thin wrapper over the Docker SDK for bot container lifecycle."""

    def __init__(self) -> None:
        self.client = docker.from_env()

    # --- network ---
    def ensure_network(self, name: str) -> None:
        """Create the private bot network if it does not already exist."""
        try:
            self.client.networks.get(name)
        except NotFound:
            self.client.networks.create(name, driver="bridge", internal=False)

    # --- lifecycle ---
    def run(self, spec: ContainerSpec) -> str:
        """Create and start a container from ``spec``, returning its id.

        Any pre-existing container with the same name is removed first so that
        re-provisioning is idempotent.
        """
        self.ensure_network(spec.network)
        self.remove(spec.name, ignore_missing=True)

        volumes = {
            host: {"bind": container, "mode": "rw"} for host, container in spec.binds.items()
        }
        container = self.client.containers.run(
            image=spec.image,
            command=spec.command,
            name=spec.name,
            environment=spec.environment,
            volumes=volumes,
            network=spec.network,
            detach=True,
            restart_policy={"Name": "unless-stopped"},
        )
        return container.id

    def start(self, name: str) -> None:
        """Start a stopped container."""
        self._get(name).start()

    def stop(self, name: str, timeout: int = 15) -> None:
        """Stop a running container (graceful, then kill after ``timeout``)."""
        self._get(name).stop(timeout=timeout)

    def remove(self, name: str, *, ignore_missing: bool = False) -> None:
        """Force-remove a container by name."""
        try:
            self._get(name).remove(force=True)
        except NotFound:
            if not ignore_missing:
                raise

    # --- introspection ---
    def status(self, name: str) -> str | None:
        """Return the container status string, or ``None`` if it does not exist."""
        try:
            return self._get(name).status
        except NotFound:
            return None

    def ip_address(self, name: str, network: str) -> str | None:
        """Return the container's IP on ``network`` (for host-side dev access)."""
        try:
            container = self._get(name)
        except NotFound:
            return None
        container.reload()
        nets = container.attrs["NetworkSettings"]["Networks"]
        net = nets.get(network)
        return net["IPAddress"] if net else None

    def logs(self, name: str, tail: int = 200) -> str:
        """Return the last ``tail`` lines of a container's logs."""
        return self._get(name).logs(tail=tail).decode("utf-8", errors="replace")

    def pull(self, image: str) -> None:
        """Pull an image if not present locally."""
        self.client.images.pull(image)

    def _get(self, name: str) -> Container:
        return self.client.containers.get(name)
