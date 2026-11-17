from __future__ import annotations

import ast
import re
from pathlib import Path

RADICE_REPOSITORY = Path(__file__).resolve().parents[2]
CARTELLE_ESCLUSE = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}
NOMI_VIETATI = {"data", "result", "item", "obj", "handle", "process"}
PATTERN_TODO = re.compile(r"TODO(?![^\n]*(?:#\d+|https?://\S+))")
AZIONI_LOG = {"critical", "debug", "error", "exception", "info", "warning"}


# Il controllo è volutamente grossolano: esclude test e tooling per non
# segnalare se stesso e per non trasformare la guardia in un linter.
def _file_python_sorgente() -> list[Path]:
    file_sorgente = []
    for percorso in RADICE_REPOSITORY.rglob("*.py"):
        parti = percorso.relative_to(RADICE_REPOSITORY).parts
        if any(parte in CARTELLE_ESCLUSE for parte in parti):
            continue
        if "tests" in parti:
            continue
        file_sorgente.append(percorso)
    return file_sorgente


def _albero_sintattico(percorso: Path) -> ast.Module:
    return ast.parse(percorso.read_text(encoding="utf-8"))


def _chiamate_print(albero: ast.Module) -> list[int]:
    return [
        nodo.lineno
        for nodo in ast.walk(albero)
        if isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Name)
        and nodo.func.id == "print"
    ]


def _gestori_exception_senza_azione(albero: ast.Module) -> list[int]:
    righe = []
    for nodo in ast.walk(albero):
        if not isinstance(nodo, ast.ExceptHandler):
            continue
        gestisce_exception = nodo.type is None or (
            isinstance(nodo.type, ast.Name) and nodo.type.id == "Exception"
        )
        if not gestisce_exception:
            continue
        if not any(_contiene_reraise_o_log(istruzione) for istruzione in nodo.body):
            righe.append(nodo.lineno)
    return righe


def _contiene_reraise_o_log(istruzione: ast.stmt) -> bool:
    for nodo in ast.walk(istruzione):
        if isinstance(nodo, ast.Raise):
            return True
        if isinstance(nodo, ast.Call) and _e_chiamata_di_log(nodo):
            return True
    return False


def _e_chiamata_di_log(chiamata: ast.Call) -> bool:
    if isinstance(chiamata.func, ast.Attribute):
        nome_mittente = _nome_mittente(chiamata.func.value)
        return chiamata.func.attr in AZIONI_LOG and "log" in nome_mittente.lower()
    return isinstance(chiamata.func, ast.Name) and chiamata.func.id in {
        "log",
        "logger",
    }


def _nome_mittente(espressione: ast.expr) -> str:
    if isinstance(espressione, ast.Name):
        return espressione.id
    if isinstance(espressione, ast.Attribute):
        return espressione.attr
    return ""


def _nomi_assegnati(albero: ast.Module) -> set[str]:
    nomi = set()
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Name) and isinstance(nodo.ctx, ast.Store):
            nomi.add(nodo.id)
        elif isinstance(nodo, ast.arg):
            nomi.add(nodo.arg)
        elif isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef):
            nomi.add(nodo.name)
    return nomi


def test_modulo_fuori_dai_test_non_usa_print() -> None:
    violazioni = []
    for percorso in _file_python_sorgente():
        for numero_riga in _chiamate_print(_albero_sintattico(percorso)):
            posizione = f"{percorso.relative_to(RADICE_REPOSITORY)}:{numero_riga}"
            violazioni.append(posizione)
    assert not violazioni, "Uso di print fuori dai test: " + ", ".join(violazioni)


def test_except_exception_ha_reraise_o_log() -> None:
    violazioni = []
    for percorso in _file_python_sorgente():
        righe = _gestori_exception_senza_azione(_albero_sintattico(percorso))
        for numero_riga in righe:
            posizione = f"{percorso.relative_to(RADICE_REPOSITORY)}:{numero_riga}"
            violazioni.append(posizione)
    assert (
        not violazioni
    ), "except Exception senza raise o log contestualizzato: " + ", ".join(violazioni)


def test_todo_ha_riferimento_a_un_issue() -> None:
    violazioni = []
    for percorso in _file_python_sorgente():
        righe = percorso.read_text(encoding="utf-8").splitlines()
        for numero_riga, riga in enumerate(righe, start=1):
            if PATTERN_TODO.search(riga):
                posizione = f"{percorso.relative_to(RADICE_REPOSITORY)}:{numero_riga}"
                violazioni.append(posizione)
    assert not violazioni, "TODO senza riferimento: " + ", ".join(violazioni)


def test_nomi_generici_vietati() -> None:
    violazioni = []
    for percorso in _file_python_sorgente():
        nomi_vietati = _nomi_assegnati(_albero_sintattico(percorso)) & NOMI_VIETATI
        for nome in sorted(nomi_vietati):
            posizione = f"{percorso.relative_to(RADICE_REPOSITORY)}:{nome}"
            violazioni.append(posizione)
    assert not violazioni, "Nomi generici vietati: " + ", ".join(violazioni)
