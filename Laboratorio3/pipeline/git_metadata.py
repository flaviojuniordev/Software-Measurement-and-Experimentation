"""Coleta eficiente de metadados Git sem checkout nem blobs de arquivos."""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence


class GitCollectionError(RuntimeError):
    """Indica que os metadados Git não puderam ser coletados localmente."""


@dataclass(frozen=True)
class GitCommandResult:
    stdout: str
    stderr: str


CommandRunner = Callable[[Sequence[str]], GitCommandResult]

_FETCH_BATCH_SIZE = 50
_FETCH_BATCH_MAX_CHARS = 24_000


class GitMetadataCollector:
    """Mantém repositórios bare parciais para consultar commits e tags.

    Somente os objetos alcançáveis pelas tags solicitadas são buscados. O filtro
    ``blob:none`` evita baixar o conteúdo dos arquivos, que não participa das
    métricas do laboratório.
    """

    def __init__(
        self,
        cache_dir: str | Path,
        *,
        runner: CommandRunner | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._runner = runner or _run_git
        self._available_refs: dict[Path, set[str]] = {}

    def collect_tags(self, full_name: str) -> list[dict[str, Any]]:
        """Lista tags com uma única negociação leve, sem clonar o projeto."""

        result = self._runner(
            ["git", "ls-remote", "--tags", self._remote_url(full_name)]
        )
        references: dict[str, dict[str, str]] = {}
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            try:
                object_id, reference = line.split("\t", 1)
            except ValueError as exc:
                raise GitCollectionError(
                    f"Saída inválida de git ls-remote para {full_name}."
                ) from exc
            if not reference.startswith("refs/tags/"):
                continue
            peeled = reference.endswith("^{}")
            tag_name = reference.removeprefix("refs/tags/").removesuffix("^{}")
            entry = references.setdefault(tag_name, {})
            entry["peeled" if peeled else "object"] = object_id

        return [
            {
                "name": name,
                "commit": {"sha": values.get("peeled") or values.get("object")},
            }
            for name, values in sorted(references.items())
        ]

    def commits_between(
        self,
        full_name: str,
        base_tag: str,
        head_tag: str,
    ) -> list[dict[str, Any]]:
        """Retorna SHA, data do autor e mensagem no intervalo ``base..head``."""

        repository = self._ensure_repository(full_name)
        base_ref = self._fetch_tag(repository, base_tag)
        head_ref = self._fetch_tag(repository, head_tag)
        result = self._runner(
            [
                "git",
                "--git-dir",
                str(repository),
                "log",
                "--reverse",
                "--format=%H%x00%aI%x00%B%x00%x1e",
                f"{base_ref}..{head_ref}",
            ]
        )
        commits: list[dict[str, Any]] = []
        for raw_record in result.stdout.split("\x1e"):
            record = raw_record.strip("\r\n\x00")
            if not record:
                continue
            parts = record.split("\x00", 2)
            if len(parts) != 3:
                raise GitCollectionError(
                    f"Metadados de commit inválidos para {full_name}: "
                    f"{base_tag}..{head_tag}."
                )
            sha, author_date, message = parts
            commits.append(
                {
                    "sha": sha,
                    "author_date": author_date,
                    "message": message.rstrip("\r\n\x00"),
                }
            )
        return commits

    def prepare_tags(self, full_name: str, tag_names: Iterable[str]) -> None:
        """Busca antecipadamente apenas as tags ausentes, em lotes limitados.

        As referencias persistem no repositorio bare. Em uma retomada, uma unica
        consulta local identifica tudo que ja foi obtido e evita repetir milhares
        de negociacoes com o remoto.
        """

        repository = self._ensure_repository(full_name)
        available = self._available_references(repository)
        missing: list[tuple[str, str]] = []
        for tag_name in dict.fromkeys(tag_names):
            local_ref = self._local_ref(tag_name)
            if local_ref not in available:
                missing.append((f"refs/tags/{tag_name}", local_ref))

        for batch in self._fetch_batches(missing):
            self._fetch_batch_with_isolation(
                repository,
                batch,
                available,
            )

    def _ensure_repository(self, full_name: str) -> Path:
        digest = hashlib.sha256(full_name.encode("utf-8")).hexdigest()[:20]
        repository = self.cache_dir / f"{digest}.git"
        if not repository.exists():
            repository.mkdir(parents=True)
            self._runner(["git", "init", "--bare", str(repository)])
            self._runner(
                [
                    "git",
                    "--git-dir",
                    str(repository),
                    "remote",
                    "add",
                    "origin",
                    self._remote_url(full_name),
                ]
            )
        return repository

    def _fetch_tag(self, repository: Path, tag_name: str) -> str:
        local_ref = self._local_ref(tag_name)
        available = self._available_references(repository)
        if local_ref in available:
            return local_ref

        self._fetch_refs(
            repository,
            [(f"refs/tags/{tag_name}", local_ref)],
        )
        available.add(local_ref)
        return local_ref

    def _available_references(self, repository: Path) -> set[str]:
        cached = self._available_refs.get(repository)
        if cached is not None:
            return cached

        available = self._list_references(repository)
        self._available_refs[repository] = available
        return available

    def _fetch_batch_with_isolation(
        self,
        repository: Path,
        references: list[tuple[str, str]],
        available: set[str],
    ) -> None:
        if not references:
            return
        try:
            self._fetch_refs(repository, references)
        except GitCollectionError:
            # Um unico nome de tag invalido nao deve impedir o lote inteiro. O
            # Git pode ter atualizado parte das referencias antes de falhar.
            available.update(self._list_references(repository))
            remaining = [item for item in references if item[1] not in available]
            if len(remaining) <= 1:
                return
            middle = len(remaining) // 2
            self._fetch_batch_with_isolation(
                repository, remaining[:middle], available
            )
            self._fetch_batch_with_isolation(
                repository, remaining[middle:], available
            )
        else:
            available.update(local_ref for _, local_ref in references)

    def _list_references(self, repository: Path) -> set[str]:
        result = self._runner(
            [
                "git",
                "--git-dir",
                str(repository),
                "for-each-ref",
                "--format=%(refname)",
                "refs/lab03/",
            ]
        )
        return {
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip()
        }

    def _fetch_refs(
        self,
        repository: Path,
        references: Sequence[tuple[str, str]],
    ) -> None:
        self._runner(
            [
                "git",
                "--git-dir",
                str(repository),
                "fetch",
                "--quiet",
                "--force",
                "--filter=blob:none",
                "--no-tags",
                "--no-write-fetch-head",
                "origin",
                *(
                    f"{remote_ref}:{local_ref}"
                    for remote_ref, local_ref in references
                ),
            ]
        )

    @staticmethod
    def _fetch_batches(
        references: Sequence[tuple[str, str]],
    ) -> Iterator[list[tuple[str, str]]]:
        batch: list[tuple[str, str]] = []
        command_chars = 0
        for reference in references:
            reference_chars = len(reference[0]) + len(reference[1]) + 2
            if batch and (
                len(batch) >= _FETCH_BATCH_SIZE
                or command_chars + reference_chars > _FETCH_BATCH_MAX_CHARS
            ):
                yield batch
                batch = []
                command_chars = 0
            batch.append(reference)
            command_chars += reference_chars
        if batch:
            yield batch

    @staticmethod
    def _local_ref(tag_name: str) -> str:
        local_name = hashlib.sha256(tag_name.encode("utf-8")).hexdigest()
        return f"refs/lab03/{local_name}"

    @staticmethod
    def _remote_url(full_name: str) -> str:
        if full_name.count("/") != 1 or any(
            part in {"", ".", ".."} for part in full_name.split("/")
        ):
            raise ValueError(f"Nome de repositório inválido: {full_name}")
        return f"https://github.com/{full_name}.git"


def _run_git(command: Sequence[str]) -> GitCommandResult:
    try:
        completed = subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitCollectionError(f"Não foi possível executar Git: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise GitCollectionError(
            f"Comando Git falhou ({completed.returncode}): {detail[:500]}"
        )
    return GitCommandResult(completed.stdout, completed.stderr)
