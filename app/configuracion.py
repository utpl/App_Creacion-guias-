from typing import Literal

from pydantic import PostgresDsn, RedisDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    """Configuracion de la aplicacion.

    Se lee del entorno al arrancar. Si falta una variable obligatoria
    o sobra una desconocida, el proceso no arranca.
    """

    entorno: Literal["desarrollo", "pruebas", "produccion"]
    url_base_datos: PostgresDsn
    url_redis: RedisDsn
    clave_secreta: SecretStr
    url_publica: str = "http://localhost:8000"
    smtp_host: str = "localhost"
    smtp_puerto: int = 1025
    smtp_usuario: str = ""
    smtp_password: SecretStr | None = None
    smtp_tls: bool = False
    remitente_correo: str = "no-responder@utpl.edu.ec"
    remitente_nombre: str = "App-EdiLoja"
  

    # Solo la usa docker-compose para crear la base en desarrollo.
    # Se declara para que extra="forbid" no la rechace.
    db_password: SecretStr | None = None

    horas_sesion: int = 8
    minutos_inactividad: int = 60
    minutos_token_recuperacion: int = 15

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        case_sensitive=False,
    )

    @field_validator("clave_secreta")
    @classmethod
    def clave_suficientemente_larga(cls, valor: SecretStr) -> SecretStr:
        if len(valor.get_secret_value()) < 32:
            raise ValueError("clave_secreta debe tener al menos 32 caracteres")
        return valor


configuracion = Configuracion()
