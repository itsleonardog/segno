from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.infrastruttura.configurazione import leggi_configurazione_sicurezza

ALGORITMO_JWT = "HS256"
TIPO_ACCESS = "access"
TIPO_REFRESH = "refresh"

DURATA_ACCESS_TOKEN_SECONDI = 15 * 60
DURATA_REFRESH_TOKEN_GIORNI = 30
DURATA_TOKEN_VERIFICA_ORE = 24
DURATA_TOKEN_RESET_ORE = 1

LUNGHEZZA_MINIMA_PASSWORD = 12
BYTE_TOKEN_OPACO = 48

PASSWORD_COMUNI = frozenset(
    {
        "123456789012",
        "password1234",
        "password12345",
        "password123456",
        "qwerty123456",
        "qwertyuiop12",
        "1234567890ab",
        "1q2w3e4r5t6y",
        "q1w2e3r4t5y6",
        "abc123456789",
        "password123!",
        "password1234!",
        "passwordpassword",
        "letmein12345",
        "welcome12345",
        "iloveyou1234",
        "admin1234567",
        "administrator",
        "monkey123456",
        "dragon123456",
        "football1234",
        "baseball1234",
        "superman1234",
        "trustno1super",
        "sunshine1234",
        "princess1234",
        "shadow123456",
        "master123456",
        "michael12345",
        "jennifer1234",
        "jordan123456",
        "harley123456",
        "ranger123456",
        "buster123456",
        "thomas123456",
        "robert123456",
        "daniel123456",
        "andrew123456",
        "joshua123456",
        "matthew12345",
        "computer1234",
        "starwars1234",
        "whatever1234",
        "freedom12345",
        "creative1234",
        "internet1234",
        "samsung12345",
        "google123456",
        "michelle1234",
        "jessica12345",
        "pepper123456",
        "cookie123456",
        "chocolate123",
        "testtest1234",
        "test12345678",
        "changeme1234",
        "default12345",
        "secret123456",
        "iloveyou12345",
        "qwerty12345!",
        "zaq12wsxcde3",
        "1qaz2wsx3edc",
        "asdfghjkl123",
        "poiuytrewq12",
        "qazwsxedcrfv",
        "1234qwerasdf",
        "000000000000",
        "111111111111",
        "121212121212",
        "123123123123",
        "112233445566",
        "987654321000",
        "qwertyuiopas",
        "password0000",
        "password1111",
        "password2222",
        "password3333",
        "password4444",
        "password5555",
        "password6666",
        "password7777",
        "password8888",
        "password9999",
        "passw0rd1234",
        "p@ssw0rd1234",
        "p@ssword1234",
        "passwort1234",
        "contraseña12",
        "contraseña123",
        "senha1234567",
        "motdepasse12",
        "motdepasse123",
        "motdepasse1234",
        "benvenuto123",
        "benvenuti123",
        "passwordestate",
        "passwordinverno",
        "passwordprimavera",
        "passwordautunno",
        "password2024",
        "password2025",
        "password2026",
        "passwordestate2024",
        "passwordestate2025",
        "passwordestate2026",
        "passwordinverno2024",
        "passwordinverno2025",
        "passwordinverno2026",
        "giuseppe1234",
        "giovanni1234",
        "francesco123",
        "alessandro12",
        "alessandro123",
        "antonio12345",
        "marco1234567",
        "luca12345678",
        "andrea123456",
        "stefano12345",
        "roberto12345",
        "salvatore123",
        "domenico1234",
        "federico1234",
        "lorenzo12345",
        "leonardo1234",
        "matteo123456",
        "simone123456",
        "pietro123456",
        "chiara123456",
        "federica1234",
        "valentina123",
        "alessia12345",
        "martina12345",
        "giorgia12345",
        "elena1234567",
        "sara12345678",
        "laura1234567",
        "paola1234567",
        "cristina1234",
        "silvia123456",
        "simona123456",
        "elisa1234567",
        "irene1234567",
        "marta1234567",
        "claudia12345",
        "letizia12345",
        "beatrice1234",
        "aurora123456",
        "eleonora1234",
        "vittoria1234",
        "serena123456",
        "veronica1234",
        "miriam123456",
        "stella123456",
        "civicreporting",
        "segnalazione1",
        "segnalazione12",
        "segnalazioni1",
        "comune123456",
        "cittadino123",
        "amministratore",
        "moderatore123",
        "portfolio123",
        "sunflower123",
        "butterfly123",
        "barcelona123",
        "liverpool123",
        "chelsea12345",
        "juventus1234",
        "milaninter12",
        "napolicalcio",
        "romatiamo123",
        "ferrari12345",
        "lamborghini1",
        "mercedes1234",
        "volkswagen12",
        "motoguzzi123",
        "harleydavid1",
        "cheeseburger",
        "pineapple123",
        "orange123456",
        "banana123456",
        "strawberry12",
        "chocolate12!",
        "vanilla12345",
        "cappuccino12",
        "espresso1234",
    }
)

_password_hasher = PasswordHasher()


@dataclass(frozen=True, slots=True)
class AccessToken:
    user_id: uuid.UUID
    jti: uuid.UUID


@dataclass(frozen=True, slots=True)
class RefreshToken:
    id: uuid.UUID
    user_id: uuid.UUID
    family_id: uuid.UUID
    token_hash: str
    issued_at: datetime
    expires_at: datetime


class TokenNonValido(Exception):  # noqa: N818
    """Segnala un token assente, malformato o scaduto."""


class ErroreRiusoToken(Exception):  # noqa: N818
    """Segnala il riuso di un refresh token già revocato."""


class PasswordNonValida(ValueError):  # noqa: N818
    """Segnala una password che non rispetta i requisiti minimi."""


def hash_password(password: str) -> str:
    """Restituisce l'hash argon2id della password."""
    return _password_hasher.hash(password)


def verifica_password(password: str, password_hash: str) -> bool:
    """Restituisce True se la password corrisponde all'hash argon2id."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def valida_password(password: str) -> None:
    """Solleva PasswordNonValida se la password è troppo corta o troppo comune."""
    if len(password) < LUNGHEZZA_MINIMA_PASSWORD:
        raise PasswordNonValida(
            f"La password deve contenere almeno {LUNGHEZZA_MINIMA_PASSWORD} caratteri."
        )
    if password.strip().lower() in PASSWORD_COMUNI:
        raise PasswordNonValida(
            "La password scelta è troppo comune. Scegline una più difficile "
            "da indovinare."
        )


def crea_access_token(user_id: uuid.UUID) -> str:
    """Restituisce un access token JWT firmato valido per 15 minuti."""
    istante = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "iat": int(istante.timestamp()),
        "exp": int(
            (istante + timedelta(seconds=DURATA_ACCESS_TOKEN_SECONDI)).timestamp()
        ),
        "jti": str(uuid.uuid4()),
        "typ": TIPO_ACCESS,
    }
    return _firma(claims)


def crea_refresh_token(
    user_id: uuid.UUID,
    family_id: uuid.UUID | None = None,
) -> tuple[str, RefreshToken]:
    """Restituisce il refresh token e i dati da persistere come hash."""
    istante = datetime.now(UTC)
    identificativo = uuid.uuid4()
    famiglia = family_id or uuid.uuid4()
    scadenza = istante + timedelta(days=DURATA_REFRESH_TOKEN_GIORNI)
    claims = {
        "sub": str(user_id),
        "family_id": str(famiglia),
        "iat": int(istante.timestamp()),
        "exp": int(scadenza.timestamp()),
        "jti": str(identificativo),
        "typ": TIPO_REFRESH,
    }
    token = _firma(claims)
    return token, RefreshToken(
        id=identificativo,
        user_id=user_id,
        family_id=famiglia,
        token_hash=hash_token_opaco(token),
        issued_at=istante,
        expires_at=scadenza,
    )


def valida_access_token(token: str) -> AccessToken:
    """Restituisce l'utente dell'access token o solleva TokenNonValido."""
    claims = _decodifica(token)
    if claims.get("typ") != TIPO_ACCESS:
        raise TokenNonValido("Il token non è un access token.")
    return AccessToken(
        user_id=_uuid_da_claim(claims, "sub"),
        jti=_uuid_da_claim(claims, "jti"),
    )


def valida_refresh_token(token: str) -> RefreshToken:
    """Restituisce i dati del refresh token o solleva TokenNonValido."""
    claims = _decodifica(token)
    if claims.get("typ") != TIPO_REFRESH:
        raise TokenNonValido("Il token non è un refresh token.")
    return RefreshToken(
        id=_uuid_da_claim(claims, "jti"),
        user_id=_uuid_da_claim(claims, "sub"),
        family_id=_uuid_da_claim(claims, "family_id"),
        token_hash=hash_token_opaco(token),
        issued_at=_istante_da_claim(claims, "iat"),
        expires_at=_istante_da_claim(claims, "exp"),
    )


def genera_token_opaco() -> str:
    """Restituisce un token opaco casuale per verifica email o reset password."""
    return secrets.token_urlsafe(BYTE_TOKEN_OPACO)


def hash_token_opaco(token: str) -> str:
    """Restituisce l'hash SHA-256 esadecimale di un token opaco o refresh."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def maschera_email(email: str) -> str:
    """Restituisce l'email mascherata con la prima lettera di locale e dominio."""
    locale, _, dominio = email.partition("@")
    iniziale_locale = locale[:1]
    iniziale_dominio = dominio[:1]
    parti_dominio = dominio.split(".")
    if len(parti_dominio) > 1:
        return f"{iniziale_locale}***@{iniziale_dominio}***.{parti_dominio[-1]}"
    return f"{iniziale_locale}***@{iniziale_dominio}***"


def _firma(claims: dict[str, object]) -> str:
    configurazione = leggi_configurazione_sicurezza()
    return jwt.encode(claims, configurazione.segreto_jwt, algorithm=ALGORITMO_JWT)


def _decodifica(token: str) -> dict[str, object]:
    configurazione = leggi_configurazione_sicurezza()
    try:
        claims = jwt.decode(
            token,
            configurazione.segreto_jwt,
            algorithms=[ALGORITMO_JWT],
        )
    except jwt.ExpiredSignatureError as errore:
        raise TokenNonValido("Il token è scaduto.") from errore
    except jwt.InvalidTokenError as errore:
        raise TokenNonValido("Il token non è valido.") from errore
    return claims


def _uuid_da_claim(claims: dict[str, object], nome: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(claims[nome]))
    except (KeyError, TypeError, ValueError) as errore:
        raise TokenNonValido(f"Il claim {nome} non è un UUID valido.") from errore


def _istante_da_claim(claims: dict[str, object], nome: str) -> datetime:
    valore = claims.get(nome)
    if not isinstance(valore, int | float):
        raise TokenNonValido(f"Il claim {nome} non è un timestamp valido.")
    return datetime.fromtimestamp(valore, UTC)
